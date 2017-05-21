# -*- coding: utf-8 -*-
"""The application's Globals object"""
import logging
import cgi
import json
import datetime
import os
import requests
import urllib
import time
import hmac
import hashlib
import posixpath

import markdown
import pygments
import pygments.lexers
import pygments.formatters
from paste.deploy.converters import asbool, asint
from pylons import tmpl_context as c, request
from tg import config, session
from boto.s3.key import Key

from vulcanforge.auth.model import User
from vulcanforge.common import helpers as h
from vulcanforge.common.util import gravatar
from vulcanforge.common.util.antispam import AntiSpam
from vulcanforge.common.util.filesystem import import_object
from vulcanforge.common.widgets.analytics import GoogleAnalytics
from vulcanforge.common.widgets.buttons import ButtonWidget, IconButtonWidget
from vulcanforge.artifact.widgets.subscription import SubscriptionPopupMenu
from vulcanforge.auth.widgets import Avatar
from vulcanforge.config.render.markdown_ext.mdx_datasort_table import \
    DataSortTableExtension
from vulcanforge.config.render.markdown_ext.mdx_forge import ForgeExtension
import vulcanforge.events.tasks
from vulcanforge.events.model import Event
from vulcanforge.project.model import Project
from vulcanforge.resources import Icon
from vulcanforge.tools.wiki.mdx_forgewiki import ForgeWikiExtension


__all__ = ['Globals']

LOG = logging.getLogger(__name__)


class ForgeAppGlobals(object):
    """Container for objects available throughout the life of the application.

    One instance of Globals is created during application initialization and
    is available during requests via the 'app_globals' variable.

    # notes

        task_queue:
            Set to a task queue instance by the
            ForgeConfig.setup_helpers_and_globals method.
            If set to None, taskd daemon will use polling instead of a queue.

    """
    __shared_state = {}
    tool_manager = None
    resource_manager = None
    task_queue = None
    event_queue = None

    def __init__(self):
        self.__dict__ = self.__shared_state
        if self.__shared_state:
            return

        self.forge_name = config.get('forge_name', 'Forge')

        # Load login/logout urls
        self.login_url = config.get('auth.login_url', '/auth/')
        self.logout_url = config.get('auth.logout_url', '/auth/logout')
        self.post_logout_url = config.get('auth.post_logout_url', '/')

        # other special urls
        self.user_register_url = config.get("user_register_url",
                                            "/auth/register/")
        self.home_url = config.get("home_url", "/")
        self.browse_home = config.get("browse_home", "/")
        self.show_register_on_login = asbool(config.get(
            'show_register_on_login', 'true'))

        # Setup pygments
        self.pygments_formatter = pygments.formatters.HtmlFormatter(
            cssclass='codehilite',
            linenos='inline')

        # Setup analytics
        ga_account = config.get('ga.account', None)
        if ga_account:
            self.analytics = GoogleAnalytics(account=ga_account)
        else:
            self.analytics = False

        MASTER_DIR = 'vulcanforge.common:templates/jinja_master/'
        self.templates = {
            'master': config.get(
                'templates.master', MASTER_DIR + 'master.html'),
            'macros': config.get(
                'templates.macros', MASTER_DIR + 'master_macros.html'),
            'nav': config.get('templates.nav', MASTER_DIR + 'nav_menu.html'),
            'project_toolbar': config.get(
                'templates.project_toolbar',
                MASTER_DIR + 'project_toolbar.html'),
            'sidebar_menu': config.get(
                'templates.sidebar_menu', MASTER_DIR + 'sidebar_menu.html'),
            'polymer-master': config.get(
                'templates.polymer_master',
                MASTER_DIR + 'polymer-master.html'),
            'polymer-user': config.get(
                'templates.polymer_user_master',
                MASTER_DIR + 'polymer-user-master.html'),
            'polymer-project': config.get(
                'templates.polymer_project_master',
                MASTER_DIR + 'polymer-project-master.html')
        }

        self.favicon_path = config.get('favicon_path', 'favicon.ico')
        self.icons = dict(
            edit=Icon('', 'ico-admin'),
            home=Icon('', 'ico-home'),
            admin=Icon('', 'ico-admin'),
            pencil=Icon('', 'ico-pencil'),
            help=Icon('', 'ico-help'),
            search=Icon('', 'magnifying_glass'),
            history=Icon('', 'ico-history'),
            feed=Icon('', 'ico-feed'),
            mail=Icon('', 'ico-mail'),
            reply=Icon('', 'ico-reply'),
            tag=Icon('', 'ico-tag'),
            flag=Icon('', 'ico-flag'),
            undelete=Icon('', 'ico-undelete'),
            delete=Icon('', 'ico-delete'),
            close=Icon('', 'ico-close'),
            table=Icon('', 'ico-table'),
            stats=Icon('', 'ico-stats'),
            pin=Icon('', 'ico-pin'),
            folder=Icon('', 'ico-folder_fill'),
            list=Icon('', 'ico-list'),
            fork=Icon('', 'ico-fork'),
            merge=Icon('', 'ico-merge'),
            plus=Icon('', 'ico-plus'),
            conversation=Icon('', 'ico-conversation'),
            group=Icon('', 'ico-group'),
            user=Icon('', 'ico-user'),
            preview=Icon('', 'ico-preview'),
            # Permissions
            perm_read=Icon('E', 'ico-focus'),
            perm_update=Icon('0', 'ico-sync'),
            perm_create=Icon('e', 'ico-config'),
            perm_submit_design=Icon('e', 'ico-config'),
            perm_detailed_scores=Icon('e', 'ico-config'),
            perm_register=Icon('e', 'ico-config'),
            perm_delete=Icon('-', 'ico-minuscirc'),
            perm_tool=Icon('x', 'ico-config'),
            perm_admin=Icon('(', 'ico-lock'),
            perm_overseer=Icon('e', 'ico-config')
        )

        self.button_widget = ButtonWidget()
        self.icon_button_widget = IconButtonWidget()
        self.avatar = Avatar()
        self.subscription_popup_menu = SubscriptionPopupMenu()

        # neighborhood controllers
        nbhd_controller_path = config.get(
            'default_nbhd_controller',
            'vulcanforge.neighborhood.controllers:NeighborhoodController')
        self.default_nbhd_controller = import_object(nbhd_controller_path)
        nbhd_rest_controller_path = config.get(
            'default_nbhd_rest_controller',
            'vulcanforge.neighborhood.controllers:NeighborhoodRestController')
        self.default_nbhd_rest_controller = import_object(
            nbhd_rest_controller_path)

        # Registration blocker
        setting = 'registration.allow'
        self.registration_allowed = asbool(config.get(setting, True))

        # get site admin project name
        setting = 'site_admin_project'
        self.site_admin_project = config.get(setting, 'forgeadmin')

        # idle logout
        setting = 'idle_logout.enabled'
        self.idle_logout_enabled = asbool(config.get(setting, False))
        setting = 'idle_logout.minutes'
        self.idle_logout_minutes = asint(config.get(setting, 30))
        setting = 'idle_logout.countdown_seconds'
        self.idle_logout_countdown_seconds = asint(config.get(setting, 30))

        # visibility mode
        visibility_mode = config.get('visibility_mode', 'default')
        self.closed_platform = visibility_mode == 'closed'

        # is openid enabled
        self.openid_enabled = asbool(config.get('openid.enabled', False))

        # Title postfix
        self.title_postfix = config.get('title_postfix', ' - VF')

        # TrustForge
        self.trustforge_enabled = asbool(
            config.get('trustforge.enabled', False))
        self.trustforge_url = config.get('trustforge.url', '')
        self.trustforge_token = config.get('trustforge.auth_token', '')

        # base url
        self.base_url = config.get('base_url', 'http://localhost:8080/')
        self.url_scheme = urllib.splittype(self.base_url)[0]
        self.base_domain = h.split_subdomain(self.base_url)

        # forgemail
        self.forgemail_return_path = config.get('forgemail.return_path',
                                                'noreply@vulcanforge.org')

        # Templates
        tmpl_master = 'vulcanforge.common:templates/jinja_master/'
        self.templates = {
            'master': config.get(
                'templates.master', tmpl_master + 'master.html'),
            'macros': config.get(
                'templates.macros', tmpl_master + 'master_macros.html'),
            'nav': config.get('templates.nav', tmpl_master + 'nav_menu.html'),
            'project_toolbar': config.get(
                'templates.project_toolbar',
                tmpl_master + 'project_toolbar.html'),
            'sidebar_menu': config.get(
                'templates.sidebar_menu', tmpl_master + 'sidebar_menu.html'),
            'polymer-master': config.get(
                'templates.polymer_master',
                tmpl_master + 'polymer-master.html'),
            'polymer-user': config.get(
                'templates.polymer_user_master',
                tmpl_master + 'polymer-user-master.html'),
            'polymer-project': config.get(
                'templates.polymer_project_master',
                tmpl_master + 'polymer-project-master.html')
        }

        # websocket
        self.websocket_enabled = asbool(config.get('websocket.enabled', True))

        self.use_gravatars = asbool(config.get('use_gravatars', True))
        self.gravatar_default = config.get('gravatar.default', "retro")

        # Global site ticketing system
        self.site_issues_url = config.get("site_issues_url")
        self.site_issues_label = config.get("site_issues_label", "Help Desk")
        self.site_faq_url = config.get("site_faq_url")
        self.site_faq_label = config.get("site_faq_label", "FAQ")

        # resumable multipart files
        setting = 'multipart_chunk_size'
        self.multipart_chunk_size = asint(config.get(setting, 4*5242880))
        # The minimum allowed size is 5242880
        if self.multipart_chunk_size < 5242880:
            self.multipart_chunk_size = 5242880

        # S3
        self.s3_serve_local = asbool(config.get('s3.serve_local', True))
        # Specify in seconds
        self.s3_url_expires_in = asint(config.get('s3.url_expires_in', 30*60))
        self.s3_encryption = asbool(config.get('s3.encryption', False))

        # Clam AV
        self.clamav_enabled = asbool(config.get('antivirus.enabled', False))
        self.clamav_host = config.get('antivirus.host', '')
        self.clamav_port = asint(config.get('antivirus.port', 3310))
        setting = 'clamav.stream_max_length'
        self.clamav_stream_max = asint(config.get(setting, 25*1000*1000))
        setting = 'clamav.task_priority'
        self.clamav_task_priority = asint(config.get(setting, 5))

        # two-factor authentication
        self.auth_two_factor = asbool(config.get('auth.two_factor', False))

        # verify login clients
        setting = 'auth.verify_login_clients'
        self.verify_login_clients = asbool(config.get(setting, False))

        # email change primary
        setting = "user.pref.change_primary_email"
        self.user_change_primary_email =  asbool(config.get(setting, True))

        # ssh public keys
        setting = "user.pref.ssh_public_key"
        self.user_ssh_public_key = asbool(config.get(setting, True))

    def gravatar(self, *args, **kwargs):
        options = {
            'd': self.gravatar_default
        }
        alias_map = (
            ('default', 'd'),
            ('rating', 'r'),
            ('forcedefault', 'f'),
            ('size', 's')
        )
        for alias, key in alias_map:
            if alias in kwargs:
                kwargs[key] = kwargs.pop(alias)
        options.update(kwargs.iteritems())
        return gravatar.url(*args, **options)

    def user_or_gravatar(self, *args, **kwargs):
        email = args[0]
        user = User.by_email_address(email)
        if user:
            return user.icon_url()
        else:
            return self.gravatar(*args, **kwargs)

    @property
    def header_logo(self):
        return self.resource_manager.absurl(
            config.get('header_logo', 'images/vf_logo_header_short.png'))

    def tool_icon_url(self, tool_entry_point, size):
        tool_entry_point = tool_entry_point.lower()
        app = self.tool_manager.tools[tool_entry_point]['app']
        return app.icon_url(size, tool_entry_point)

    def get_site_admin_project(self):
        return Project.by_shortname(self.site_admin_project)

    def trustforge_request(self, method, uri, data_dict=None):
        if self.trustforge_url and self.trustforge_token:
            request_function = getattr(requests, method)

            headers = {
                'content-type': 'application/json',
                'trust_token': self.trustforge_token}
            uri = os.path.join(self.trustforge_url, uri)
            if data_dict:
                response = request_function(
                    uri,
                    data=json.dumps(data_dict),
                    headers=headers
                )
            else:
                response = request_function(uri, headers=headers)

            return response
        else:
            return None

    def artifact_s3_prefix(self, artifact):
        if artifact is not None:
            return h.urlquote('/'.join((
                artifact.project.shortname,
                artifact.app_config.options.mount_point,
                artifact.s3_key_prefix())) + '#')
        else:
            return ''

    def make_s3_keyname(self, key_name, artifact=None):
        return config.get('s3.app_prefix', 'Forge') + '/' + \
            self.artifact_s3_prefix(artifact) + \
            h.urlquote(key_name)

    def get_s3_key(self, key_name, artifact=None, bucket=None,
                   insert_if_missing=True):
        if bucket is None:
            bucket = self.s3_bucket
        key_name = self.make_s3_keyname(key_name, artifact)

        key = None
        try:
            key = bucket.get_key(key_name)
        except:
            pass

        if key is None and insert_if_missing:
            key = Key(bucket, key_name)

        return key

    def get_s3_keys(self, key_prefix, artifact=None):
        key_prefix = self.make_s3_keyname(key_prefix, artifact)
        keys = self.s3_bucket.get_all_keys(prefix=h.urlquote(key_prefix))
        for key in keys:
            if '%2523' in key.name:  # The '#' has been double escaped
                key.name = urllib.unquote(key.name)
        return keys

    def delete_s3_key(self, key):
        prefix = config.get('s3.app_prefix', 'Forge') + '/'
        if key.name.startswith(prefix) and key.name != prefix:
            self.s3_bucket.delete_key(key.name)

    def make_s3_request(self, method, key_name):
        key_name = self.make_s3_keyname(key_name)
        return self.s3.make_request(method, self.s3_bucket, key_name)

    def has_s3_key_access(self, keyname, **kw):
        return self.s3_auth.has_access(keyname, **kw)

    def s3_temp_url(self, keyname, bucket=None, temp_url_key=None,
                    expires=None, account_name=None, method="GET"):
        """Note that this uses the full keyname of the s3 object"""
        if bucket is None:
            bucket = self.s3_bucket
        if temp_url_key is None:
            temp_url_key = config['s3.tempurlkey']
        if account_name is None:
            account_name = config.get('s3.account_name', 'account')
        if expires is None:
            expires = int(config.get('s3.tempurlexpires', 1800))
        expiry_time = int(time.time() + expires)
        path = '/v1/AUTH_{account}/{bucket}/{key}'.format(
            account=account_name,
            bucket=bucket.name,
            key=keyname
        )
        hmac_body = '%s\n%s\n%s' % (method, expiry_time, h.urlquote(path))
        sig = hmac.new(temp_url_key, hmac_body, hashlib.sha1).hexdigest()
        url = '{protocol}://{host}:{port}{path}?{query}'.format(
            protocol=bucket.connection.protocol,
            host=bucket.connection.host,
            port=bucket.connection.port,
            path=h.urlquote(h.urlquote(path)),
            query=urllib.urlencode({
                'temp_url_sig': sig,
                'temp_url_expires': expiry_time
            })
        )
        return url

    def post_event(self, topic, *args, **kwargs):
        LOG.debug(
            'event "%s" posted with args:%s kwargs:%s', topic, args, kwargs)
        vulcanforge.events.tasks.event.post(topic, *args, **kwargs)

    def store_event(self, event_type, user=None, neighborhood=None,
                     project=None, app=None, extra=None):
        return Event.make_event(
            user=user,
            neighborhood=neighborhood,
            project=project,
            app=app,
            type=event_type,
            extra=extra)

    @property
    def antispam(self):
        a = request.environ.get('vulcan.antispam')
        if a is None:
            a = request.environ['vulcan.antispam'] = AntiSpam()
        return a

    def handle_paging(self, limit, page, default=50):
        if limit:
            if c.user is None or c.user.is_anonymous:
                session['results_per_page'] = int(limit)
                session.save()
            else:
                old_pref = c.user.get_pref('results_per_page')
                if old_pref != int(limit):
                    c.user.set_pref('results_per_page', int(limit))
        else:
            if c.user is None or c.user.is_anonymous:
                limit = 'results_per_page' in session and \
                        session['results_per_page'] or default
            else:
                limit = c.user.get_pref('results_per_page') or default
        page = max(int(page), 0)
        start = page * int(limit)
        return int(limit), int(page), int(start)

    def document_class(self, neighborhood):
        classes = ''
        if neighborhood:
            classes += ' neighborhood-%s' % neighborhood.name
        if not neighborhood and c.project:
            classes += ' neighborhood-%s' % c.project.neighborhood.name
        if c.project:
            classes += ' project-%s' % c.project.shortname
        if c.app:
            classes += ' mountpoint-%s' % c.app.config.options.mount_point
        return classes

    def highlight(self, text, lexer=None, filename=None, no_text='Empty File'):
        if not text:
            return h.html.literal('<em>{}</em>'.format(no_text))
        if lexer == 'diff':
            formatter = pygments.formatters.HtmlFormatter(
                cssclass='codehilite', linenos=False)
        else:
            formatter = self.pygments_formatter
        if lexer is None:
            try:
                lexer = pygments.lexers.get_lexer_for_filename(
                    filename, encoding='chardet')
            except pygments.util.ClassNotFound:
                # no highlighting, just escape
                text = h.really_unicode(text)
                text = cgi.escape(text)
                return h.html.literal(u'<pre>' + text + u'</pre>')
        else:
            lexer = pygments.lexers.get_lexer_by_name(
                lexer, encoding='chardet')
        return h.html.literal(pygments.highlight(text, lexer, formatter))

    def forge_markdown(self, **kwargs):
        """return a markdown.Markdown object on which you can call convert"""
        extensions = [
            'codehilite',
            ForgeExtension(**kwargs),
            'tables',
            DataSortTableExtension()
        ]
        extension_configs = {}
        if kwargs.get('wiki', False):
            extensions.append(ForgeWikiExtension())
        return markdown.Markdown(extensions=extensions,
                                 extension_configs=extension_configs,
                                 output_format='html5')

    @property
    def markdown(self):
        return self.forge_markdown()

    @property
    def markdown_wiki(self):
        project = getattr(c, 'project', None)
        if project is not None and project.shortname == '--init--':
            return self.forge_markdown(wiki=True,
                                       macro_context='neighborhood-wiki')
        else:
            return self.forge_markdown(wiki=True)

    @property
    def production_mode(self):
        return not asbool(config.get('debug', 'false'))

    def oid_session(self):
        if 'openid_info' in session:
            return session['openid_info']
        else:
            session['openid_info'] = result = {}
            session.save()
            return result

    def set_project(self, pid_or_project):
        if isinstance(pid_or_project, Project):
            c.project = pid_or_project
        elif isinstance(pid_or_project, basestring):
            cls = c.neighborhood.project_cls if c.neighborhood else Project
            c.project = cls.query_get(shortname=pid_or_project, deleted=False)
        elif pid_or_project is None:
            c.project = None
        else:
            c.project = None
            LOG.error('Trying g.set_project(%r)', pid_or_project)

    def set_app(self, name):
        c.app = c.project.app_instance(name)

    def url(self, uri, **kw):
        try:
            url = "{}://{}".format(self.url_scheme, request.host)
        except TypeError:
            url = self.base_url
        if not uri.startswith('/'):
            url += '/'
        url += uri
        params = urllib.urlencode(kw)
        if params:
            url += '?{}'.format(params)
        return url

    def cloud_url(self, uri):
        base_url = config.get('cloud_url', self.base_url)
        url = base_url.rstrip('/') + '/' + uri.lstrip('/')
        return url

    def make_url(self, rel_uri, is_index=False):
        """
        Make a url from a uri relative to the current request.

        Set is_index to True if current method is index to remove ambiguity.

        """
        path = request.path_info
        if path.endswith('/') and (not is_index or path.endswith('index/')):
            path = path.rstrip('/')
        elif is_index and not path.endswith('/index'):
            path += '/'
        return posixpath.join(posixpath.dirname(path), rel_uri)

    def year(self):
        return datetime.datetime.utcnow().year

    # commented excluded fields for reference
    index_default_text_fields = [
        'cat',
        'subject',
        'author',
        'title',
        'description',
        'name',
        'features',
        'license',
        'text',
        'keywords',
        'links',
        'category',
        'manu',
        'comments',
    ]
