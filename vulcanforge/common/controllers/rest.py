"""
@group ISIS - Vanderbilt University
@author Gabor Pap

The VF
U{REST<http://en.wikipedia.org/wiki/Representational_state_transfer>}
interface.

To access this interface use
https://B{<domain>}/rest/

@undocumented
"""
import json
import logging
import urllib
import oauth2 as oauth

from datetime import datetime

from paste.util.converters import asbool
from webob import exc
from tg import expose, flash, redirect, config, TGController
from pylons import tmpl_context as c, app_globals as g, request
import pymongo
from ming.odm import session
from ming.utils import LazyProperty

from vulcanforge.artifact.model import ArtifactReference
from vulcanforge.artifact.widgets import short_artifact_link_data
from vulcanforge.auth.model import (
    ServiceToken,
    ApiTicket,
    ApiToken
)
from vulcanforge.common.exceptions import AJAXNotFound
from vulcanforge.auth.oauth.model import (
    OAuthConsumerToken,
    OAuthAccessToken,
    OAuthRequestToken
)
from vulcanforge.common.util import (
    nonce,
    get_client_ip,
    re_path_portion
)
from vulcanforge.artifact.controllers import ArtifactRestController
from vulcanforge.exchange.controllers.rest import GlobalExchangeRestController
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.model import AppConfig, Project
from vulcanforge.websocket.controllers import WebSocketAPIController
from vulcanforge.common.util.counts import (
    get_artifact_counts, get_exchange_counts
)

LOG = logging.getLogger(__name__)


class RestController(TGController):

    def __init__(self):
        self.user = UserRestController()
        self.artifact = ArtifactRestController(index_only=True)
        self.webapi = WebAPIController()
        self.exchange = GlobalExchangeRestController()

    def _check_security(self):
        api_token = self._authenticate_request()
        c.api_token = api_token
        if api_token and not api_token.user.disabled:
            c.user = api_token.user
            LOG.info('user is %s', c.user.username)

    def _authenticate_request(self):
        """Based on request.params or oauth, authenticate the request"""
        if 'oauth_token' in request.params:
            return self.oauth._authenticate()
        elif 'service_token' in request.params:
            LOG.info("Using service token %s", request.params['service_token'])
            token = ServiceToken.query.get(
                api_key=request.params['service_token'])
            if not token or not token.authenticate_request(request.environ):
                LOG.info('denied: %s', token)
                raise exc.HTTPForbidden
            return token
        elif 'api_key' in request.params:
            api_key = request.params.get('api_key')
            token = ApiTicket.get(api_key)
            if not token:
                token = ApiToken.get(api_key)
            else:
                LOG.info('Authenticating with API ticket')
            if token is not None and \
                    token.authenticate_request(request.path, request.params):
                return token
            else:
                LOG.info('API authentication failure')
                raise exc.HTTPForbidden
        else:
            return None

    @expose()
    def _lookup(self, name, *remainder):
        neighborhood = Neighborhood.query.get(url_prefix='/' + name + '/')
        if not neighborhood:
            raise exc.HTTPNotFound, name
        c.neighborhood = neighborhood
        controller = neighborhood.rest_controller_class
        return controller(neighborhood), remainder


class OAuthNegotiator(object):
    """

    @undocumented: server, do_authorize
    """

    @LazyProperty
    def server(self):
        result = oauth.Server()
        result.add_signature_method(oauth.SignatureMethod_PLAINTEXT())
        result.add_signature_method(oauth.SignatureMethod_HMAC_SHA1())
        return result

    def _authenticate(self):
        req = oauth.Request.from_request(
            request.method,
            request.url.split('?')[0],
            headers=request.headers,
            parameters=dict(request.params),
            query_string=request.query_string
            )
        consumer_token = OAuthConsumerToken.query.get(
            api_key=req['oauth_consumer_key'])
        access_token = OAuthAccessToken.query.get(
            api_key=req['oauth_token'])
        if consumer_token is None:
            LOG.error('Invalid consumer token')
            return None
            raise exc.HTTPForbidden
        if access_token is None:
            LOG.error('Invalid access token')
            raise exc.HTTPForbidden
        consumer = consumer_token.consumer
        try:
            self.server.verify_request(req, consumer, access_token.as_token())
        except:
            LOG.error('Invalid signature')
            raise exc.HTTPForbidden
        return access_token

    @expose()
    def request_token(self, **kw):
        req = oauth.Request.from_request(
            request.method,
            request.url.split('?')[0],
            headers=request.headers,
            parameters=dict(request.params),
            query_string=request.query_string
            )
        consumer_token = OAuthConsumerToken.query.get(
            api_key=req['oauth_consumer_key'])
        if consumer_token is None:
            LOG.error('Invalid consumer token')
            raise exc.HTTPForbidden
        consumer = consumer_token.consumer
        try:
            self.server.verify_request(req, consumer, None)
        except:
            LOG.error('Invalid signature')
            raise exc.HTTPForbidden
        req_token = OAuthRequestToken(
            consumer_token_id=consumer_token._id,
            callback=req.get('oauth_callback', 'oob')
            )
        session(req_token).flush()
        LOG.info('Saving new request token with key: %s', req_token.api_key)
        return req_token.to_string()

    @expose('jinja:vulcanforge:auth/oauth/templates/oauth_authorize.html')
    def authorize(self, oauth_token=None):
        g.security.require_authenticated()
        rtok = OAuthRequestToken.query.get(api_key=oauth_token)
        rtok.user_id = c.user._id
        if rtok is None:
            LOG.error('Invalid token %s', oauth_token)
            raise exc.HTTPForbidden
        return dict(
            oauth_token=oauth_token,
            consumer=rtok.consumer_token)

    @expose('jinja:vulcanforge:auth/oauth/templates/oauth_authorize_ok.html')
    def do_authorize(self, yes=None, no=None, oauth_token=None):
        g.security.require_authenticated()
        rtok = OAuthRequestToken.query.get(api_key=oauth_token)
        if no:
            rtok.delete()
            flash('%s NOT AUTHORIZED' % rtok.consumer_token.name, 'error')
            redirect('/auth/oauth/')
        if rtok.callback == 'oob':
            rtok.validation_pin = nonce(6)
            return dict(rtok=rtok)
        rtok.validation_pin = nonce(20)
        if '?' in rtok.callback:
            url = rtok.callback + '&'
        else:
            url = rtok.callback + '?'
        url += 'oauth_token=%s&oauth_verifier=%s' % (
            rtok.api_key, rtok.validation_pin)
        redirect(url)

    @expose()
    def access_token(self, **kw):
        req = oauth.Request.from_request(
            request.method,
            request.url.split('?')[0],
            headers=request.headers,
            parameters=dict(request.params),
            query_string=request.query_string
            )
        consumer_token = OAuthConsumerToken.query.get(
            api_key=req['oauth_consumer_key'])
        request_token = OAuthRequestToken.query.get(
            api_key=req['oauth_token'])
        if consumer_token is None:
            LOG.error('Invalid consumer token')
            raise exc.HTTPForbidden
        if request_token is None:
            LOG.error('Invalid request token')
            raise exc.HTTPForbidden
        pin = req['oauth_verifier']
        if pin != request_token.validation_pin:
            LOG.error('Invalid verifier')
            raise exc.HTTPForbidden
        rtok = request_token.as_token()
        rtok.set_verifier(pin)
        consumer = consumer_token.consumer
        try:
            self.server.verify_request(req, consumer, rtok)
        except:
            LOG.error('Invalid signature')
            return None
        acc_token = OAuthAccessToken(
            consumer_token_id=consumer_token._id,
            request_token_id=request_token._id,
            user_id=request_token.user_id)
        return acc_token.to_string()


class UserLinkBinRestController(object):

    def _check_security(self):
        g.security.require_authenticated()

    @expose('json')
    def index(self, **kwargs):
        # TODO: speed this up by making a multi_artifact_by_index_id method
        ref_ids = c.user.workspace_references
        references = {}
        for ref_id in ref_ids:
            artifact = g.artifact.get_artifact_by_index_id(ref_id)
            if artifact:
                references[ref_id] = short_artifact_link_data(artifact)
        return {
            'references': references
        }

    @expose('json')
    def add(self, ref_id=None, **kwargs):
        if not ref_id:
            raise exc.HTTPNotFound("ref_id is a required parameter")
        ref_id = urllib.unquote(ref_id)
        artifact = g.artifact.get_artifact_by_index_id(ref_id)
        if artifact is None:
            raise exc.HTTPNotFound("artifact does not exist")
        if ref_id in c.user.workspace_references:
            raise exc.HTTPConflict("already in link bin")
        c.user.workspace_references.append(ref_id)
        ArtifactReference.from_artifact(artifact)
        return {
            'status': "successful"
        }

    @expose('json')
    def remove(self, ref_id=None, **kwargs):
        if not ref_id:
            raise exc.HTTPNotFound("ref_id is a required parameter")
        ref_id = urllib.unquote(ref_id)
        if ref_id not in c.user.workspace_references:
            raise exc.HTTPNotFound(ref_id)
        c.user.workspace_references.remove(ref_id)
        return {
            'status': "successful"
        }


class UserRestController(object):
    """
    B{Description}: Controller that exposes user related endpoints, such as:

        - GET L{rest/user/get_user_profile
        <vulcanforge.common.controllers.rest.UserRestController.get_user_profile>}

    @undocumented: get_user_trust_history

    """
    linkbin = UserLinkBinRestController()

    def _check_security(self):
        c.project = c.user.private_project()

    def _before(self, *args, **kwargs):
        self.user = c.user

    @expose('json')
    def get_user_profile(self, **kw):
        """
        B{Description}: Returns a User's profile information.

        B{Requires authentication}

        B{Example request}

        GET I{rest/user/get_user_profile}

        @return:
            { "fullName": str,
            "profileImage": str url,
            "username": str,
            "trustInfo": {
                "score": float [0-1],
                "percentile" float [0-1]
            },
            "skypeName": str / null}
        @rtype: JSON document

        """
        return self.user.get_profile_info()

    @expose('json')
    def get_user_trust_history(self, **kw):
        return dict(history=self.user.get_trust_history())

    @expose('json')
    def get_user_tools(self, tool_name=None, permission="read", **kw):
        tools = []

        project_ids = set(
            role.project_id for role in self.user.get_roles() if role.name)
        query = {
            "project_id": {"$in": list(project_ids)}
        }
        if tool_name:
            query["tool_name"] = tool_name

        for ac in AppConfig.query.find(query):
            if ac.has_access(permission, self.user):
                tools.append({
                    "url": ac.url(),
                    "id": str(ac._id),
                    "tool_name": ac.tool_name,
                    "mount_label": ac.options.mount_label,
                    "project_shortname": ac.project.shortname,
                    "project_name": ac.project.name
                })

        return {'tools': tools}

    @expose('json')
    def get_artifact_count(self, project_shortname=None, permission="read", **kw):
        if c.user.is_anonymous:
            return

        return get_artifact_counts(self.user, project_shortname, permission)

    @expose('json')
    def get_exchange_counts(self, xchng_name):
        if c.user.is_anonymous:
            return

        c.exchange = g.exchange_manager.get_exchange_by_uri(xchng_name)
        if c.exchange is None:
            raise AJAXNotFound()

        return get_exchange_counts(self.user, xchng_name)


class ProjectRestController(object):

    @expose()
    def _lookup(self, name, *remainder):
        if not re_path_portion.match(name):
            raise exc.HTTPNotFound, name
        app = c.project.app_instance(name)
        if app is None:
            raise exc.HTTPNotFound, name
        c.app = app
        if app.api_root is None:
            raise exc.HTTPNotFound, name

        return app.api_root, remainder


class WebServiceAuthController(object):

    def _before(self, *args, **kw):
        msg = "Token-based web service request headers: {}"
        LOG.debug(msg.format(request.headers))
        token = request.headers.get('WS-TOKEN')
        if not token or token != config.get('auth.ws.token'):
            LOG.warn('Invalid web service token %s', str(token))
            raise exc.HTTPNotFound()


class WebServiceRestController(object):
    auth = WebServiceAuthController()
    websocket = WebSocketAPIController()


class WebAPIController(TGController):

    @expose('json')
    def navdata(self, **kwargs):
        if not g.cache:
            return self._make_navdata()
        cache_hash_name = 'navdata'
        hash_key = c.user.username
        cached = g.cache.hget_json(cache_hash_name, hash_key)
        if cached:
            return cached
        new_navdata = self._make_navdata()
        timeout = (10 * 60) if g.production_mode else 10
        g.cache.hset_json(cache_hash_name, hash_key, new_navdata, timeout)
        return new_navdata

    def _make_navdata(self):
        """
        Special icons and labels configuration:

        config parameter:`masternav.special_neighborhoods`
        config value: JSON structure, example (expanded to show structure)
            {
                "/projects/": {
                    "label": "",
                    "icon": "images/fang_logo.png",
                    "icon_is_resource": true
                }
            }
        """
        SPECIAL_ICONS = {}
        SPECIAL_LABELS = {}
        specials_key = 'masternav.special_neighborhoods'
        try:
            specials_config = json.loads(config.get(specials_key, '{}'))
        except ValueError:
            LOG.exception("Could not parse config parameter %r", specials_key)
        else:
            for k, v in specials_config.items():
                if 'icon' in v:
                    if v.get('icon_is_resource', False):
                        SPECIAL_ICONS[k] = g.resource_manager.\
                            absurl(v.get('icon'))
                    else:
                        SPECIAL_ICONS[k] = v.get('icon')
                if 'label' in v:
                    SPECIAL_LABELS[k] = v.get('label')

        hood_id_map = {}
        project_id_map = {}

        hood_items = []

        hood_query_params = {
            'url_prefix': {'$nin': ['/u/', '//']}
        }
        for hood in Neighborhood.query.find(hood_query_params):
            if not g.security.has_access(hood, 'read'):
                continue
            project = hood.neighborhood_project
            hood_data = {
                'label': SPECIAL_LABELS.get(hood.url_prefix, hood.name),
                'url': hood.url(),
                'icon': SPECIAL_ICONS.get(hood.url_prefix, hood.icon_url()),
                'shortname': hood.url_prefix,
                'children': [],
                'tools': self._get_global_nav_tools_for_project(project),
                'actions': self._get_global_nav_actions_for_hood(hood),
                'specialIcon': hood.url_prefix in SPECIAL_ICONS
            }
            hood_id_map[hood._id] = hood_data
            hood_items.append(hood_data)

        # if authenticated, get projects using named roles
        has_user = c.user is not None
        if has_user:
            project_cursor = [x for x in c.user.my_projects()
                              if x.neighborhood_id in hood_id_map]
            project_cursor.sort(key=lambda x: x.sortable_name)
        else:
            project_query_params = {
                'neighborhood_id': {
                    '$in': hood_id_map.keys()
                }
            }
            project_cursor = Project.query.find(project_query_params)
            project_cursor.sort('sortable_name', pymongo.ASCENDING)
        for project in project_cursor:
            # if authenticated, avoid superfluous access checking
            if has_user:
                if project.deleted:
                    continue
            elif ( project.deleted and
                    not g.security.has_access(project, 'write') or
                    not g.security.has_access(project, 'read') or
                    not project.first_mount('read')
                ):
                    continue
            project_data = {
                'label': project.name,
                'url': project.url(),
                'icon': project.icon_url,
                'shortname': project.shortname,
                'tools': self._get_global_nav_tools_for_project(project),
                'actions': self._get_global_nav_actions_for_project(project)
            }
            project_id_map[project._id] = project_data
            hood_id_map[project.neighborhood_id]['children'].\
                append(project_data)

        root_item = self._get_global_nav_root_item()
        # compile output
        return {
            'hoods': hood_items,
            'globals': {
                'children': self._get_global_nav_children(),
                'actions': self._get_global_nav_actions()
            },
            "label": root_item['label'],
            "url": root_item['url'],
            "icon": root_item['icon']
        }

    def _get_global_nav_children(self):
        items = self._get_global_nav_exchanges()
        item_keys = config.get('masternav.root_items', '').split()
        for key in item_keys:
            key_prefix = 'masternav.items.' + key + '.'
            try:
                label = config[key_prefix + 'label']
                href = config[key_prefix + 'href']
                icon_url = config[key_prefix + 'icon']
            except KeyError, e:
                LOG.exception('Missing required key for %r, skipping it', key)
                continue
            if asbool(config.get(key_prefix + 'icon_is_resource', False)):
                icon_url = g.resource_manager.absurl(icon_url)
            items.append({
                'label': label,
                'url': href,
                'icon': icon_url
            })
        return items

    def _get_global_nav_actions(self):
        global_actions = []
        if c.user.is_anonymous:
            global_actions.append({
                'label': 'Register',
                'url': g.user_register_url
            })
            global_actions.append({
                'label': 'Log In',
                'url': g.login_url
            })
        return global_actions

    def _get_global_nav_root_item(self):
        if c.user.is_anonymous:
            href = config.get('masternav.root.href', "/")
        else:
            href = config.get('masternav.root.href',
                              "/dashboard/activity_feed/")
        icon_url = config.get('masternav.root.icon',
                              "images/vf_logo_icon2.png")
        if asbool(config.get('masternav.root.icon_is_resource', 'true')):
            icon_url = g.resource_manager.absurl(icon_url)
        label = config.get('masternav.root.label', '').strip()
        return {
            'label': label,
            'icon': icon_url,
            'url': href
        }

    def _get_global_nav_actions_for_hood(self, hood):
        actions = []
        if hood.user_can_register(c.user):
            actions.append({
                'label': 'Start a {}'.format(hood.project_cls.type_label),
                'url': '{}add_project'.format(hood.url()),
                'icon': 'ico-plus'
            })
        return actions

    def _get_global_nav_tools_for_project(self, project):
        tools = []
        i = 0
        for mount in project.ordered_mounts():
            i += 1
            if i == 1:  # skip the first mount for listing
                continue
            app_config = mount.get('ac', None)
            if app_config is None or not app_config.is_visible_to(c.user):
                continue
            app_config_data = {
                'label': app_config.options.mount_label,
                'url': app_config.url(),
                'icon': app_config.icon_url(32),
                'shortname': app_config.options.mount_point,
                'actions': [],
                'children': []
            }
            try:
                app_instance = app_config.instantiate()
                app_nav_data = app_instance.get_global_navigation_data()
            except:
                pass
            else:
                app_config_data.update(app_nav_data)
            # special behavior for "home" mount point
            if app_config.options.get('mount_point', None) == 'home':
                tools.insert(0, app_config_data)
            else:
                tools.append(app_config_data)
        return tools

    def _get_global_nav_actions_for_project(self, project):
        return []

    def _get_global_nav_exchanges(self):
        exchange_items = []
        for exchange in g.exchange_manager.exchanges:
            exchange_items.append({
                "label": exchange.config["name"],
                "url": exchange.url(),
                "icon": g.resource_manager.absurl(exchange.config['icon'])
            })
        return exchange_items
