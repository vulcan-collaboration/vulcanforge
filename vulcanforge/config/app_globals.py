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

import markdown
import pygments
import pygments.lexers
import pygments.formatters
from paste.deploy.converters import asbool, asint
from pylons import tmpl_context as c, request
from tg import config, session
from pypeline.markup import markup as pypeline_markup
from boto.s3.key import Key
from ming.utils import LazyProperty

from vulcanforge.common import helpers as h
from vulcanforge.common.util import gravatar
from vulcanforge.common.util.antispam import AntiSpam
from vulcanforge.common.util.filesystem import import_object
from vulcanforge.common.widgets.analytics import GoogleAnalytics
from vulcanforge.common.widgets.buttons import ButtonWidget, IconButtonWidget
from vulcanforge.artifact.widgets.subscription import SubscriptionPopupMenu
from vulcanforge.auth.model import User
from vulcanforge.auth.widgets import Avatar
from vulcanforge.config.markdown_ext.mdx_forge import ForgeExtension
import vulcanforge.events.tasks
from vulcanforge.events.model import Event
from vulcanforge.project.model import Project
from vulcanforge.resources import Icon


__all__ = ['Globals']

LOG = logging.getLogger(__name__)


class ForgeGlobals(object):
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

    def __init__(self):
        self.__dict__ = self.__shared_state
        if self.__shared_state:
            return

        self.use_queue = asbool(config.get('use_queue', False))

        # Load login/logout urls
        self.login_url = config.get('auth.login_url', '/auth/')
        self.logout_url = config.get('auth.logout_url', '/auth/logout')
        self.post_logout_url = config.get('auth.post_logout_url', '/')

        # other special urls
        self.user_register_url = config.get("user_register_url",
                                            "/auth/register/")
        self.site_issues_url = config.get("site_issues_url",
                                          "/projects/forgeadmin/issues/")
        self.site_issues_label = config.get("site_issues_label", "Help Desk")
        self.site_faq_url = config.get("site_faq_url",
                                       "/projects/forgeadmin/help/Home")
        self.home_url = config.get("home_url", "/")
        self.browse_home = config.get("browse_home", "/")
        self.show_register_on_login = asbool(config.get(
            'show_register_on_login', 'true'))

        # Setup Gravatar
        self.gravatar = gravatar.url

        # Setup pygments
        self.pygments_formatter = pygments.formatters.HtmlFormatter(
            cssclass='codehilite',
            linenos='inline')

        # Setup Pypeline
        self.pypeline_markup = pypeline_markup

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
                'templates.sidebar_menu', MASTER_DIR + 'sidebar_menu.html')
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
        self.registration_allowed = config.get(
            'registration.allow', 'true').lower().startswith('t')

        # get site admin project name
        self.site_admin_project = config.get(
            'site_admin_project', 'forgeadmin')

        # idle logout
        self.idle_logout_enabled = asbool(
            config.get('idle_logout_enabled', True))
        self.idle_logout_minutes = asint(config.get('idle_logout_minutes', 30))
        self.idle_logout_countdown_seconds = asint(
            config.get('idle_logout_countdown_seconds', 30))

        self.exchange_service_path = config.get(
            'exchange_tool.service.path', '/rest/exchange')

        self.exchange_content_agreement_message = config.get(
            'exchange.content_agreement_message', None
        )

        self.exchange_data_dir = config.get('exchange.component_staging')
        self.exchange_top_category_generation = asbool(
            config.get('exchange.top_category_generation', True)
        )
        self.exchange_send_notifications = asbool(
            config.get('exchange.send_notifications', True)
        )

        # is openid enabled
        self.openid_enabled = asbool(config.get('openid.enabled', False))

        # Title postfix
        self.title_postfix = config.get('title_postfix', ' - VF')

        self.trustforge_url = config.get('trustforge.url', '')
        self.trustforge_token = config.get('trustforge.auth_token', '')

        # base url
        self.base_url = config.get('base_url', 'http://localhost:8080/')
        self.url_scheme = urllib.splittype(self.base_url)[0]
        self.base_domain = h.split_subdomain(self.base_url)

        # forgemail
        self.forgemail_return_path = config.get('forgemail.return_path',
                                                'noreply@vehicleforge.org')

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
                'templates.sidebar_menu', tmpl_master + 'sidebar_menu.html')
        }

    @property
    def header_logo(self):
        return self.resource_manager.absurl(
            config.get('header_logo', 'images/vf_logo_header_short.png'))

    def tool_icon_url(self, tool_entry_point, size):
        tool_entry_point = tool_entry_point.lower()
        resource = self.tool_manager.tools[tool_entry_point]['app'].icons[size]
        resource = 'theme/{}'.format(resource)
        return self.resource_manager.absurl(resource)

    def get_site_admin_project(self):
        return Project.query.get(shortname=self.site_admin_project)

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
                artifact.shorthand_id())) + '#')
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
        if bucket is None:
            bucket = self.s3_bucket
        if temp_url_key is None:
            temp_url_key = config['s3.tempurlkey']
        if account_name is None:
            account_name = config.get('s3.account_name', 'account')
        if expires is None:
            expires = int(
                time.time() + int(config.get('s3.tempurlexpires', 1800)))
        path = '/v1/AUTH_{account}/{bucket}/{key}'.format(
            account=account_name,
            bucket=bucket.name,
            key=keyname
        )
        hmac_body = '%s\n%s\n%s' % (method, expires, path)
        sig = hmac.new(temp_url_key, hmac_body, hashlib.sha1).hexdigest()
        url = '{protocol}://{host}:{port}{path}?{query}'.format(
            protocol=bucket.connection.protocol,
            host=bucket.connection.host,
            port=bucket.connection.port,
            path=path,
            query=urllib.urlencode({
                'temp_url_sig': sig,
                'temp_url_expires': expires
            })
        )
        return url

    def swift_auth_url(self, keyname, bucket_name=None, artifact=None,
                       base_url=None):
        return '{base_url}{prefix}/{bucket}/{key}'.format(
            base_url=base_url or self.base_s3_url,
            prefix=config.get('swift.auth.url_prefix', 'swiftvf'),
            bucket=bucket_name or self.s3_bucket.name,
            key=self.make_s3_keyname(keyname, artifact),
        )

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
        a = request.environ.get('allura.antispam')
        if a is None:
            a = request.environ['allura.antispam'] = AntiSpam()
        return a

    def handle_paging(self, limit, page, default=50):
        if limit:
            if c.user in (None, User.anonymous()):
                session['results_per_page'] = int(limit)
                session.save()
            else:
                old_pref = c.user.get_pref('results_per_page')
                if old_pref != int(limit):
                    c.user.set_pref('results_per_page', int(limit))
        else:
            if c.user in (None, User.anonymous()):
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
        return markdown.Markdown(
            extensions=[
                #'toc',
                'codehilite',
                ForgeExtension(**kwargs),
                'tables',
            ],
            output_format='html4')

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
        return asbool(config.get('debug')) == False

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
            c.project = Project.query.get(
                shortname=pid_or_project, deleted=False)
        elif pid_or_project is None:
            c.project = None
        else:
            c.project = None
            LOG.error('Trying g.set_project(%r)', pid_or_project)

    def set_app(self, name):
        c.app = c.project.app_instance(name)

    def url(self, base, **kw):
        try:
            url = "{}://{}".format(self.url_scheme, request.host)
        except TypeError:
            url = self.base_url
        if not base.startswith('/'):
            url += '/'
        url += base
        params = urllib.urlencode(kw)
        if params:
            url += '?{}'.format(params)
        return url

    def postload_contents(self):
        text = '''
'''
        return json.dumps(dict(text=text))

    def year(self):
        return datetime.datetime.utcnow().year

    # commented excluded fields for reference
    index_default_text_fields = [
        'cat',
        #'percentile',
        #'weight',
        #'review_count',
        'subject',
        #'includes',
        #'project_type',
        #'unix_group_name',
        #'id',
        'author',
        #'last_modified',
        'title',
        #'screenshot_url',
        #'trove',
        'description',
        'name',
        #'manu_exact',
        'features',
        #'registration_date',
        'license',
        #'group_ranking',
        #'content_type',
        #'popularity',
        'text',
        #'num_downloads',
        'keywords',
        #'project_doc_id',
        #'help_wanted',
        #'group_id',
        'links',
        #'has_file',
        #'alphaNameSort',
        #'sku',
        #'num_developers',
        #'admin_subscribed',
        'category',
        #'price',
        #'license_other',
        'manu',
        #'source',
        #'num_services',
        #'rating',
        #'inStock',
        #'num_downloads_week',
        'comments',
    ]
