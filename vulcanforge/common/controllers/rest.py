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
import logging
import urllib
import os

import oauth2 as oauth
from webob import exc
from tg import expose, flash, redirect, config, TGController
from pylons import tmpl_context as c, app_globals as g, request, response
from ming.odm import session
from ming.utils import LazyProperty
from vulcanforge.artifact.model import ArtifactReference
from vulcanforge.artifact.widgets import short_artifact_link_data
from vulcanforge.auth.model import (
    ServiceToken,
    ApiTicket,
    ApiToken,
    User,
    StaticResourceToken
)
from vulcanforge.auth.oauth.model import (
    OAuthConsumerToken,
    OAuthAccessToken,
    OAuthRequestToken
)
from vulcanforge.cache.decorators import cache_rendered
from vulcanforge.common.controllers.decorators import require_authenticated
from vulcanforge.common.util import (
    nonce,
    get_client_ip,
    re_path_portion
)

from vulcanforge.artifact.controllers import ArtifactRestController
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.exceptions import NoSuchProjectError
from vulcanforge.project.model import AppConfig, Project

LOG = logging.getLogger(__name__)


class RestController(TGController):

    def __init__(self):
        self.user = UserRestController()
        self.artifact = ArtifactRestController(index_only=True)
        self.webapi = WebAPIController()

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
        require_authenticated()
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
        require_authenticated()
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
        require_authenticated()

    @expose('json')
    def index(self, **kwargs):
        # TODO: speed this up by making a multi_artifact_by_index_id method
        ref_ids = c.user.workspace_references
        references = {}
        for ref_id in ref_ids:
            artifact = ArtifactReference.artifact_by_index_id(ref_id)
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
        artifact = ArtifactReference.artifact_by_index_id(ref_id)
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

        - GET L{rest/u/user/get_user_profile
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

        GET I{rest/user/u/get_user_profile}

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
        token = request.headers.get('WS_TOKEN')
        if not token or token != config.get('auth.ws.token'):
            LOG.info('invalid web service token %s', str(token))
            raise exc.HTTPNotFound()


class SwiftAuthRestController(object):

    def _before(self, *args, **kw):
        LOG.info('request to swift auth %s', request.url)
        # ensure requester is our swift server
        header_name = config.get('swift.auth.header', 'VFSW_TOKEN')
        token = request.headers.get(header_name)
        if not token or token != config.get('swift.auth.token'):
            LOG.warn(
                'invalid swift token %s from %s', str(token), get_client_ip())
            raise exc.HTTPNotFound()

        # authenticate user
        api_key = request.headers.get('SWIFT_USER_TOKEN')
        if api_key:
            st = StaticResourceToken.query.get(api_key=api_key)

            if st and st.authenticate_request(request.environ):
                c.user = st.user
                LOG.info('setting user to %s', c.user.username)

    @expose('json')
    def has_permission(self, path=None, method="GET", **kw):
        path = urllib.unquote(path)
        has_permission = g.has_s3_key_access(path, method=method)
        LOG.info(
            'has_permission is %s to resource %s for %s',
            str(has_permission), path, c.user.username)
        return {"has_permission": has_permission}


class WebAPIController(TGController):

    @expose('json')
    @cache_rendered(timeout=60)
    def navdata(self, **kwargs):

        global_actions = []
        if c.user == User.anonymous():
            global_actions.append({
                'label': 'Register',
                'url': g.user_register_url
            })
            global_actions.append({
                'label': 'Sign In',
                'url': g.login_url
            })

        hood_id_map = {}
        project_id_map = {}

        hood_items = []

        for hood in Neighborhood.query.find():
            if not g.security.has_access(hood, 'read'):
                continue
            hood_data = {
                'label': hood.name,
                'url': hood.url(),
                'icon': hood.icon_url(),
                'shortname': hood.url_prefix,
                'children': [],
                'actions': []
            }
            hood_id_map[hood._id] = hood_data
            hood_items.append(hood_data)
            if hood.user_can_register(c.user):
                hood_data['actions'].append({
                    'label': 'Create Project',
                    'url': '{}add_project'.format(hood.url())
                })

        project_query_params = {
            'neighborhood_id': {
                '$in': hood_id_map.keys()
            }
        }
        for project in Project.query.find(project_query_params):
            if not g.security.has_access(project, 'read'):
                continue
            project_data = {
                'label': project.name,
                'url': project.url(),
                'icon': project.icon_url,
                'shortname': project.shortname,
                'children': [],
                'actions': []
            }
            project_id_map[project._id] = project_data
            hood_id_map[project.neighborhood_id]['children'].append(project_data)

        app_config_query_params = {
            'project_id': {'$in': project_id_map.keys()}
        }
        for app_config in AppConfig.query.find(app_config_query_params):
            if not g.security.has_access(app_config, 'read'):
                continue
            app_config_data = {
                'label': app_config.options.mount_label,
                'url': app_config.url(),
                'icon': app_config.icon_url(48),
                'shortname': app_config.options.mount_point,
                'actions': []
            }
            project_id_map[app_config.project_id]['children'].append(app_config_data)

        return {
            'hoods': hood_items,
            'globals': [
                {
                    'label': 'Browse Projects',
                    'url': g.url('/browse/'),
                    'icon': g.url(g.resource_manager.absurl('images/forge_toolbar_icons/projects_icon_on.png'))
                },
                {
                    'label': 'Browse Designers',
                    'url': g.url('/designers/'),
                    'icon': g.url(g.resource_manager.absurl('images/forge_toolbar_icons/designers_icon_on.png'))
                }
            ],
            'actions': global_actions
        }
