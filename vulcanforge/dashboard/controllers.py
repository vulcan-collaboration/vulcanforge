# -*- coding: utf-8 -*-

"""
dashboard

@summary: dashboard

@author: U{tannern<tannern@gmail.com>}
"""
from datetime import datetime
import logging

import bson
import pymongo
from webob.exc import HTTPNotFound, HTTPBadRequest
from pylons import tmpl_context as c, app_globals as g, response
from tg import config
from tg.controllers.util import redirect
from tg.decorators import expose, with_trailing_slash, without_trailing_slash
from vulcanforge.auth.model import User
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import validate_form, \
    require_post, require_site_admin_access
from vulcanforge.common.types import SitemapEntry
from vulcanforge.common.widgets.util import PageSize, PageList
from vulcanforge.messaging.forms import MakeAnnouncementForm, \
    ConversationReplyForm, StartConversationForm, AnnounceToAllForm
from vulcanforge.messaging.model import ConversationStatus, Conversation
from vulcanforge.notification.model import Mailbox, Notification
from vulcanforge.project.model import Project, AppConfig
from vulcanforge.resources import Icon


LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:dashboard/templates/'


class BaseDashboardController(BaseController):
    class Forms(BaseController.Forms):
        make_announcement_form = MakeAnnouncementForm()

    def _before(self, *args, **kwargs):
        c.custom_sidebar_menu = []
        reg_nbhd = c.user.registration_neighborhood()
        if reg_nbhd and reg_nbhd.user_can_register():
            c.custom_sidebar_menu.extend([
                SitemapEntry(
                    'Start a {}'.format(reg_nbhd.project_cls.type_label),
                    reg_nbhd.url() + 'add_project',
                    ui_icon=Icon('', 'ico-plus')
                ),
                SitemapEntry('Dashboard')
            ])
        c.custom_sidebar_menu.extend([
            SitemapEntry('Activity Feed', '/dashboard/activity_feed',
                         ui_icon=Icon('', 'ico-activity')),
            SitemapEntry('Conversations', '/dashboard/messages',
                         ui_icon=Icon('', 'ico-inbox')),
            SitemapEntry(
                'Start a conversation',
                '/dashboard/messages/start_conversation',
                ui_icon=Icon('', 'ico-plus')
            ),
        ])
        if len(self.Forms.make_announcement_form._available_sender_roles()):
            c.custom_sidebar_menu.append(SitemapEntry(
                'Make an announcement',
                '/dashboard/messages/make_announcement',
                ui_icon=Icon('', 'ico-plus')
            ))
            # announce to all users option
        p_admin = Project.query.get(shortname=g.site_admin_project)
        if g.security.has_access(p_admin, 'admin'):
            c.custom_sidebar_menu.append(SitemapEntry(
                "Announce to All Users",
                '/dashboard/messages/announce_to_all',
                ui_icon=Icon('', 'ico-plus')
            ))


class DashboardRootController(BaseDashboardController):
    def __init__(self):
        self.api = DashboardAPIController()
        self.messages = MessagesController()
        self.activity_feed = ActivityFeedController()

    def _check_security(self):
        g.security.require_authenticated()

    @expose()
    def index(self, **kwargs):
        return redirect('/dashboard/activity_feed')


class BaseMessagesController(BaseDashboardController):
    pass


class ConversationController(BaseMessagesController):
    conversation = None

    class Forms(BaseMessagesController.Forms):
        reply_form = ConversationReplyForm()

    def __init__(self, _id):
        try:
            self.conversation = Conversation.query.get(
                _id=bson.ObjectId(_id)
            )
        except bson.errors.InvalidId:
            pass
        if self.conversation is None:
            raise HTTPNotFound

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'conversation.html')
    def index(self, **kwargs):
        c.form = self.Forms.reply_form
        status = self.conversation.get_status_for_user_id(c.user._id)
        status.unread = False
        return {
            'conversation': self.conversation,
        }

    @expose()
    @validate_form("reply_form", error_handler=index)
    def do_reply(self, text=None, **kwargs):
        self.conversation.add_message(c.user._id, text)
        return redirect(self.conversation.get_url())


class MessagesController(BaseMessagesController):
    # controllers
    conversation_controller = ConversationController

    # widgets
    class Widgets(BaseMessagesController.Widgets):
        page_list_widget = PageList()
        page_size_widget = PageSize()

    class Forms(BaseMessagesController.Forms):
        start_conversation_form = StartConversationForm()
        announce_to_all_form = AnnounceToAllForm()

    @expose()
    def _lookup(self, _id, *remainder):
        return self.conversation_controller(_id), remainder

    @expose(TEMPLATE_DIR + 'messages.html')
    def index(self, page=0, limit=25, **kwargs):
        c.page_list = self.Widgets.page_list_widget
        c.page_size = self.Widgets.page_size_widget
        limit, page, start = g.handle_paging(limit, page)
        cursor = ConversationStatus.query.find(
            {'user_id': c.user._id}, start=start, limit=limit
        ).sort('updated_at', pymongo.DESCENDING)
        return {
            'conversation_statuses': cursor.all(),
            'limit': limit,
            'page': page,
            'count': cursor.count(),
        }

    @expose(TEMPLATE_DIR + 'start_conversation.html')
    def start_conversation(self, recipients=None, subject=None, message=None,
                           **kwargs):
        c.form = self.Forms.start_conversation_form
        return {
            'form_values': {
                'recipients': recipients or '',
                'subject': subject or '',
                'message': message or '',
            }
        }

    @expose()
    @require_post()
    @validate_form("start_conversation_form", error_handler=start_conversation)
    def do_start_conversation(self, recipients=None, subject=None, text=None,
                              **kwargs):
        conversation = Conversation()
        for user in recipients:
            conversation.add_user_id(user._id)
        conversation.subject = subject
        conversation.add_user_id(c.user._id)
        conversation.add_message(c.user._id, text)
        return redirect(conversation.get_url())

    @expose(TEMPLATE_DIR + 'make_announcement.html')
    def make_announcement(self, as_role=None, to_role=None, subject=None,
                          message=None, **kwargs):
        c.form = self.Forms.make_announcement_form
        return {
            'form_values': {
                'as_role': as_role or '',
                'to_role': to_role or '',
                'subject': subject or '',
                'message': message or '',
            }
        }

    @expose()
    @require_post()
    @validate_form("make_announcement_form", error_handler=make_announcement)
    def do_make_announcement(self, as_role=None, to_role=None, text=None,
                             allow_comments=None, subject=None, **kwargs):
        conversation = Conversation()
        conversation.is_announcement = True
        conversation.allow_comments = allow_comments
        conversation.subject = subject
        conversation.add_role_id(to_role._id)
        conversation.add_user_id(c.user._id)
        conversation.add_message(c.user._id, text, role_id=as_role._id)
        return redirect(conversation.get_url())

    @expose(TEMPLATE_DIR + 'announce_to_all.html')
    @require_site_admin_access()
    def announce_to_all(self, **kwargs):
        c.form = self.Forms.announce_to_all_form
        return {
            'form_values': kwargs
        }

    @expose()
    @require_site_admin_access()
    @require_post()
    @validate_form("announce_to_all_form", error_handler=announce_to_all)
    def do_announce_to_all(self, as_role=None, text=None, allow_comments=None,
                           subject=None, **kwargs):
        conversation = Conversation()
        conversation.is_announcement = True
        conversation.allow_comments = allow_comments
        conversation.subject = subject
        for user in User.query.find():
            conversation.add_user_id(user._id)
        conversation.add_message(c.user._id, text, role_id=as_role._id)
        return redirect(conversation.get_url())


class DashboardAPIController(BaseController):
    def _get_mailbox_q(self):
        return Mailbox.query.find({
            'user_id': c.user._id,
            'is_flash': False,
            #'follow': True,
        })

    @expose('json')
    def notifications(self, before=None, after=None, **kwargs):
        limit = 20
        mailbox_q = self._get_mailbox_q()
        if not mailbox_q.count():
            return {"notifications": []}
        project_ids = []
        n_params = {
        }
        or_queries = []
        for mailbox in mailbox_q:
            if mailbox.project_id is not None:
                project_ids.append(mailbox.project_id)
            or_queries.append(mailbox._get_notification_query_params())
        if len(or_queries):
            n_params['$or'] = or_queries

        if (before is not None and before != 'null') \
            or (after is not None and after != 'null'):
            pubdate = {}
            if before is not None:
                pubdate['$lt'] = datetime.strptime(before,
                                                   "%Y-%m-%d %H:%M:%S.%f")
            if after is not None:
                limit = 1000
                pubdate['$gt'] = datetime.strptime(after,
                                                   "%Y-%m-%d %H:%M:%S.%f")
            n_params['pubdate'] = pubdate

        # get all matching notifications
        notification_q = Notification.query.find(n_params, limit=limit)
        notification_q.sort('pubdate', pymongo.DESCENDING)

        # prepare notifications
        notifications = [n.__json__() for n in notification_q
                         if n.has_access('read')]

        return {
            'notifications': notifications
        }


class ActivityFeedController(BaseDashboardController):
    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'activity_feed/index.html')
    def index(self, **kwargs):
        return {}

    @expose(TEMPLATE_DIR + 'activity_feed/filters.html')
    def filters(self):

        # get state
        activity_feed_state = c.user.state_preferences.get('activity_feed', {})
        project_state = {}
        app_config_state = activity_feed_state.get('app_config_state', {})

        # get project ids
        project_ids = set()
        app_config_ids = set()
        ## from roles
        reaching_roles = c.user.get_roles()
        [project_ids.add(r.project_id) for r in reaching_roles if r.name]
        ## from mailboxes
        js = "db.%s.distinct('project_id', {user_id:ObjectId(\"%s\")})" % (
            Mailbox.__mongometa__.name, c.user._id)
        [project_ids.add(x) for x in Mailbox.query.session.impl.db.eval(js)]

        # get projects and app config ids
        projects = []
        project_params = {
            '_id': {
                '$in': list(project_ids),
            }
        }
        project_query = Project.query.find(project_params)
        project_query.sort('sortable_name', pymongo.ASCENDING)
        for project in project_query:
            if project.is_user_project():
                project_ids.remove(project._id)
                continue
            p_id = str(project._id)
            info = project.__json__()
            # get app configs
            info['app_configs'] = []
            app_config_params = {
                'project_id': project._id,
            }
            app_config_query = AppConfig.query.find(app_config_params)
            app_config_query.sort('options.ordinal', pymongo.ASCENDING)
            project_state[p_id] = True
            for app_config in app_config_query:
                if not app_config.has_access('read'):
                    continue
                app_config_ids.add(app_config._id)
                info['app_configs'].append(app_config.__json__())
                ac_id_s = str(app_config._id)
                app_config_state[ac_id_s] = app_config_state.get(ac_id_s, True)
                if project_state[p_id] and not app_config_state[ac_id_s]:
                    project_state[p_id] = False
            projects.append(info)

        # update state
        activity_feed_state['app_config_state'] = app_config_state
        c.user.state_preferences['activity_feed'] = activity_feed_state

        # response
        return {
            'projects': projects,
            'project_ids': list(project_ids),
            'project_state': project_state,
            'app_config_ids': list(app_config_ids),
            'app_config_state': app_config_state,
        }

    def _get_isodate_from_arg(self, date=None):
        try:
            return datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f").isoformat()
        except (ValueError, TypeError):
            pass
        try:
            return datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f").isoformat()
        except (ValueError, TypeError):
            pass
        return datetime.utcnow().isoformat()

    @expose(content_type='application/json')
    def notifications(self, date=None, before=True, **kwargs):
        # get state
        activity_feed_state = c.user.state_preferences.get('activity_feed', {})
        app_config_state = activity_feed_state.get('app_config_state', {})
        # build solr query
        iso_date = self._get_isodate_from_arg(date)
        if isinstance(before, basestring):
            before = before.lower().startswith('t')
        if before:
            q = "pubdate_dt:[* TO {0}Z]".format(iso_date)
            limit = 10
        else:
            q = "pubdate_dt:[{0}Z TO *]".format(iso_date)
            limit = 1000
        q += " AND -(pubdate_dt:{0}Z)".format(iso_date.replace(':', '\:'))
        shown_app_config_ids = [str(k) for k, v
                                in app_config_state.items()
                                if v]
        if len(shown_app_config_ids):
            q += " AND app_config_id_s:({})".format(
                ' OR '.join(shown_app_config_ids))
        else:
            return '{"notifications":[]}'
        read_roles = ' OR '.join(g.security.get_user_read_roles())
        solr_params = {
            'q': q,
            'fq': [
                'type_s:Notification',
                'read_roles:({})'.format(read_roles),
            ],
            'start': 0,
            'sort': 'pubdate_dt desc',
            'rows': limit,
        }
        # query solr
        results = g.solr.search(**solr_params)
        # build json response
        has_more = 'true' if results.hits > limit else 'false'
        json = '{"notifications":['
        i = 0
        for doc in results.docs:
            if i > 0:
                json += ','
            json += doc['json_s']
            i += 1
        json += '],"more":{}'.format(has_more)
        json += '}'
        return json

    def _set_app_config(self, _id_s, value):
        try:
            app_config = AppConfig.query.get(_id=bson.ObjectId(_id_s))
        except TypeError:
            raise HTTPBadRequest('Invalid AppConfig id')
        if app_config is None:
            raise HTTPBadRequest('AppConfig with id not found')
            # get state
        activity_feed_state = c.user.state_preferences.get('activity_feed', {})
        app_config_state = activity_feed_state.get('app_config_state', {})
        # update state
        app_config_state[_id_s] = value
        activity_feed_state['app_config_state'] = app_config_state
        c.user.state_preferences['activity_feed'] = activity_feed_state

    @without_trailing_slash
    @expose()
    def disable_app_config(self, _id=None):
        self._set_app_config(_id, False)

    @without_trailing_slash
    @expose()
    def enable_app_config(self, _id=None):
        self._set_app_config(_id, True)

    def _set_project(self, _id_s, value):
        try:
            project = Project.query.get(_id=bson.ObjectId(_id_s))
        except TypeError:
            raise HTTPBadRequest('Invalid Project id')
        if project is None:
            raise HTTPBadRequest('Project with id not found')
        app_configs = AppConfig.query.find({'project_id': project._id})
        # get state
        activity_feed_state = c.user.state_preferences.get('activity_feed', {})
        app_config_state = activity_feed_state.get('app_config_state', {})
        # update state
        for ac in app_configs:
            _id_s = str(ac._id)
            app_config_state[_id_s] = value
        activity_feed_state['app_config_state'] = app_config_state
        c.user.state_preferences['activity_feed'] = activity_feed_state

    @without_trailing_slash
    @expose()
    def disable_project(self, _id=None):
        self._set_project(_id, False)

    @without_trailing_slash
    @expose()
    def enable_project(self, _id=None):
        self._set_project(_id, True)

    @expose('json')
    def projects(self):
        projects = set()
        for p in c.user.my_projects():
            if not p.is_real():
                continue
            projects.add(p)
        for mb in Mailbox.query.find({'user_id': c.user._id}):
            if not mb.project.is_real():
                continue
            projects.add(mb.project)
        return {
            'projects': sorted(projects, key=lambda x: x.name)
        }

    @expose('json')
    def project(self, _id=None):
        try:
            project = Project.query.get(_id=bson.ObjectId(_id))
        except TypeError:
            raise HTTPBadRequest('Invalid Project id')
        if project is None:
            raise HTTPBadRequest('Project with id not found')
        app_configs = AppConfig.query.find({'project_id': project._id}).all()
