# -*- coding: utf-8 -*-

"""
dashboard

@summary: dashboard

@author: U{tannern<tannern@gmail.com>}
"""
from datetime import datetime
import logging
import simplejson

import bson
from bson import ObjectId
from datetime import datetime, timedelta
from markupsafe import Markup
from operator import itemgetter
import pymongo
from webob.exc import HTTPNotFound, HTTPBadRequest
from paste.deploy.converters import asbool
from pylons import tmpl_context as c, app_globals as g, response
from tg import config, flash
from tg.controllers.util import redirect
from tg.decorators import expose, with_trailing_slash, \
    without_trailing_slash, validate
from vulcanforge.auth.model import User
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import validate_form, \
    require_post, require_site_admin_access
from vulcanforge.common.controllers.rest import UserRestController
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.common.util import push_config
from vulcanforge.common.util.counts import get_tools_info
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.common.util.notifications import get_notifications
from vulcanforge.common.widgets.util import PageSize, PageList
from vulcanforge.messaging.forms import MakeAnnouncementForm, \
    ConversationReplyForm, StartConversationForm, AnnounceToAllForm
from vulcanforge.messaging.model import ConversationStatus, Conversation
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.notification.model import Mailbox, Notification
from vulcanforge.project.model import (
    Project,
    AppConfig,
    MembershipRequest,
    MembershipInvitation
)
from vulcanforge.resources import Icon
from vulcanforge.notification.stats import NotificationQuerySchema, \
    NotificationAggregator
from vulcanforge.cache.decorators import cache_rendered, cache_json
from vulcanforge.tools.profile.user_main import UserProfileController
from vulcanforge.stats import STATS_CACHE_TIMEOUT


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

    @expose(TEMPLATE_DIR + 'teamup.html')
    def teamup(self, q='', page=0, limit=25, **kwargs):
        reg_nbhd = c.user.registration_neighborhood()
        if reg_nbhd and reg_nbhd.user_can_register():
            add_team_url = reg_nbhd.url() + 'add_project'
        else:
            add_team_url = None
        search_url = '/dashboard/teamup_data'
        return {
            "q": q,
            "page": page,
            "limit": limit,
            "add_team_url": add_team_url,
            "search_url": search_url
        }

    @expose('json')
    def teamup_data(self, q=None, limit=25, start=0, **kwargs):
        start = int(start)
        limit = int(limit)
        read_roles_q = ' OR '.join(g.security.get_user_read_roles())
        q_list = ['read_roles:({})'.format(read_roles_q)]
        if q:
            q_list.append(q)

        # Project Advertisements
        ad_results = g.search(
            q=' AND '.join(q_list),
            fq='type_s:ProjectAdvertisement',
            start=start,
            limit=limit,
            sort='pubdate_dt desc'
        )

        # All projects
        neighborhoods = Neighborhood.query.find({"allow_browse": True})
        nbhd_q = ' OR '.join(str(n._id) for n in neighborhoods)
        fq = ["deleted_b:false", "type_s:Project",
              "neighborhood_id_s:({})".format(nbhd_q)]
        if ad_results.docs:
            id_q = ' OR '.join(ad["project_id_s"] for ad in ad_results.docs)
            fq.append("NOT _id_s:({})".format(id_q))

        projects = []
        project_count = 0
        if len(ad_results.docs) < limit:
            project_results = g.search(
                q=' AND '.join(q_list),
                fq=fq,
                start=max(start - ad_results.hits, 0),
                rows=limit - len(ad_results.docs),
                sort='last_updated_dt desc'
            )
            if project_results:
                projects = project_results.docs
                project_count = project_results.hits
        else:
            # just a count
            project_results = g.search(
                q=' AND '.join(q_list),
                fq=fq,
                rows=0
            )
            if project_results:
                project_count = project_results.hits

        return {
            "featured": ad_results.docs,
            "projects": projects,
            "total_count": ad_results.hits + project_count
        }

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

    @without_trailing_slash
    @expose()
    def select(self, project=None, app=None, **kwargs):
        """Starting selection for Activity Feed"""

        # pre-filter selected project
        if project:
            try:
                p = Project.by_id(bson.ObjectId(project))
                if p and g.security.has_access(p, "read"):
                    self._set_all_prefs(False)
                    self._set_project(project, True)
            except:
                msg = "Unable to set project '{}' for Activity Feed."
                LOG.info(msg.format(project))

        # pre-filter selected app
        if app:
            try:
                app_config_id = bson.ObjectId(app)
                ac = AppConfig.query.get(_id=app_config_id)
                if ac and g.security.has_access(ac, "read"):
                    self._set_all_prefs(False)
                    self._set_app_config(app, True)
            except:
                msg = "Unable to set app_config '{}' for Activity Feed."
                LOG.info(msg.format(app))

        redirect(".")

    def _get_projects(self):
        """gets the user's projects"""
        project_ids = set()
        ## from roles
        reaching_roles = c.user.get_roles()
        [project_ids.add(r.project_id) for r in reaching_roles if r.name]
        ## from mailboxes
        db, coll = pymongo_db_collection(Mailbox)
        cur = coll.find({"user_id": c.user._id})
        user_project_ids = filter(None, cur.distinct('project_id'))
        project_ids.update(user_project_ids)
        project_params = {
            '_id': {
                '$in': list(project_ids),
            }
        }
        project_query = Project.query.find(project_params)
        project_query.sort('sortable_name', pymongo.ASCENDING)
        return [x for x in project_query if x.is_real()]

    @expose(TEMPLATE_DIR + 'activity_feed/filters.html')
    def filters(self, global_state=None):

        # get state
        activity_feed_state = c.user.state_preferences.get('activity_feed', {})
        project_state = {}
        app_config_state = activity_feed_state.get('app_config_state', {})
        exchange_state = activity_feed_state.get('exchange_state', {})

        # get projects and app config ids
        projects = []
        project_query = self._get_projects()
        project_ids = set([x._id for x in projects])
        app_config_ids = set()
        for project in project_query:
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
                app_config_state.setdefault(ac_id_s, True)
                if project_state[p_id] and not app_config_state[ac_id_s]:
                    project_state[p_id] = False
            projects.append(info)

        # get exchanges
        exchanges = []
        for exchange in g.exchange_manager.exchanges:
            exchanges.append({
                "uri": exchange.config["uri"],
                "name": exchange.config["name"],
                "url": exchange.url(),
                "icon_url": g.resource_manager.absurl(exchange.config['icon'])
            })
            exchange_state.setdefault(exchange.config["uri"], True)

        # tool activity
        urc = UserRestController()
        urc.user = c.user
        tool_info = urc.get_artifact_count()
        app_config_activity = {}
        project_shortnames = [x['shortname'] for x in projects]
        project_activity = {x: 0 for x in project_shortnames}
        for tool in tool_info['tools']:
            if tool['artifact_counts'].get('new', 0):
                new_count = tool['artifact_counts']['new'] 
                app_config_activity[tool["id"]] = new_count
                pname = tool['project_shortname']
                project_activity[pname] += new_count

        # global state override requested
        if global_state:
            if global_state == "new":
                for ac_id in app_config_state:
                    app_config_state[ac_id] = ac_id in app_config_activity
                for project in projects:
                    shortname = project['shortname']
                    active = bool(project_activity[shortname])
                    project_state[project['_id']] = active
                # todo: exchange new
                for exchange in exchange_state:
                    exchange_state[exchange] = False
            else:
                state_holders = (app_config_state, exchange_state,
                                 project_state)
                value = global_state == "set" 
                for states in state_holders:
                    for state in states:
                        states[state] = value

        # update state
        activity_feed_state['app_config_state'] = app_config_state
        activity_feed_state['exchange_state'] = exchange_state
        c.user.state_preferences['activity_feed'] = activity_feed_state
        
        # reorder projects by activity
        projects.sort(key=lambda x: project_activity[x['shortname']],
                      reverse=True)

        # response
        return {
            'projects': projects,
            'project_ids': list(project_ids),
            'project_state': project_state,
            'app_config_ids': list(app_config_ids),
            'app_config_state': app_config_state,
            'app_config_activity': app_config_activity,
            'exchanges': exchanges,
            'exchange_state': exchange_state
        }

    @expose('json')
    def notifications(self, from_dt=None, to_dt=None, **kwargs):
        LOG.info("Notifications: {} to {}".format(from_dt, to_dt))
        limit=10
        results = get_notifications(c.user, from_dt=from_dt, to_dt=to_dt, limit=limit, **kwargs)
        # build json response
        has_more = 'true' if results.hits > limit else 'false'
        json = '{{"notifications":[{notifications}],"more":{more}}}'.format(
            notifications=','.join(d['json_s'] for d in results.docs),
            more=has_more
        )
        return Markup(json)

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

    def _set_all_prefs(self, value):
        """set all user state preferences to a value"""
        # get state
        activity_feed_state = c.user.state_preferences.get('activity_feed', {})
        app_config_state = activity_feed_state.get('app_config_state', {})
        exchange_state = activity_feed_state.get('exchange_state', {})
        # modify state
        state_holders = (app_config_state, exchange_state) 
        for states in state_holders:
            for state in states:
                states[state] = value
        # update state
        activity_feed_state['app_config_state'] = app_config_state
        activity_feed_state['exchange_state'] = exchange_state
        c.user.state_preferences['activity_feed'] = activity_feed_state

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

    def _set_projects(self, value):
        """set all project state preferences to a value"""
        projects = self._get_projects()
        for project in projects:
            self._set_project(str(project._id), value)
        
    @without_trailing_slash
    @expose()
    def disable_project(self, _id=None):
        self._set_project(_id, False)

    @without_trailing_slash
    @expose()
    def enable_project(self, _id=None):
        self._set_project(_id, True)

    def _set_exchange(self, uri, value):
        exchange = g.exchange_manager.get_exchange_by_uri(uri)
        if exchange is None:
            raise HTTPBadRequest('Invalid exchange uri')

        activity_feed_state = c.user.state_preferences.get('activity_feed', {})
        exchange_state = activity_feed_state.get('exchange_state', {})
        # update state
        exchange_state[uri] = value
        activity_feed_state['exchange_state'] = exchange_state
        c.user.state_preferences['activity_feed'] = activity_feed_state

    @expose()
    def disable_exchange(self, uri=None):
        self._set_exchange(uri, False)

    @expose()
    def enable_exchange(self, uri=None):
        self._set_exchange(uri, True)

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
    #@cache_rendered(timeout=STATS_CACHE_TIMEOUT)
    @validate(NotificationQuerySchema())
    def notification_aggregate(self, date_start=None, date_end=None, bins=None,
                         order=None, label=None, user=None):
        msg = "Notification Aggregator: start: {} end: {}"
        LOG.info(msg.format(date_start, date_end))
        if bins is None:
            bins = ['daily']

        activity_feed_state = c.user.state_preferences.get('activity_feed', {})
        app_config_state = activity_feed_state.get('app_config_state', {})
        exchange_state = activity_feed_state.get("exchange_state", {})
        if any(app_config_state.values()) or any(exchange_state.values()):
            app_config_ids = []
            remove = []
            for ac in app_config_state:
                ac_oid = bson.ObjectId(ac)
                if AppConfig.query.get(_id=ac_oid):
                    if app_config_state[ac]:
                        app_config_ids.append(ac_oid)
                else:
                    remove.append(ac)
            if remove:
                for ac in remove:
                    del app_config_state[ac]
                activity_feed_state['app_config_state'] = app_config_state
                c.user.state_preferences['activity_feed'] = activity_feed_state
    
            exchange_uris = [k for k, v in exchange_state.items() if v]
    
            agg = NotificationAggregator(
                date_start=date_start,
                date_end=date_end,
                bins=bins,
                order=order,
                label=label,
                user=user,
                app_config_id=app_config_ids,
                exchange_uri=exchange_uris
            )
            agg.run()
            return agg.fix_results()
        return dict(ok=1, results=[])

class DashboardController(DashboardRootController):

    def __init__(self):
        super(DashboardController, self).__init__()
        self.public_users = asbool(config.get('all_users_public', False))

    @expose(TEMPLATE_DIR + 'teamup.html')
    def teams(self, q='', page=0, limit=25, **kwargs):
        return {}

    @expose('polymer_colorscheme.html')
    def colors(self, **kwargs):
        return {}

    @expose('json')
    def allprojects(self, **kwargs):
        myprojects = {x._id: None for x in c.user.my_projects()
                      if x.is_real()}
        retProj = []
        myProj = []
        projects = [
            x for x in Project.query.find() if x.is_real() and
            (not x.deleted or g.security.has_access(x, 'admin', c.user)) and
            g.security.has_access(x, 'read', c.user)
        ]
        for pr in projects:
            p = {}
            p['name'] = pr.name
            p['info'] = pr.short_description
            p['canAdmin'] = g.security.has_access(pr, 'admin', c.user)
            p['deleted'] = pr.deleted
            p['hasInvite'] = (pr.user_requested(c.user) or
                              pr.user_invited(c.user))
            p['isMember'] = pr._id in myprojects
            p['icon_url'] = pr.icon_url
            p['private'] = pr.icon_url
            p['url'] = pr.url()
            p['user_num'] = len(pr.users())
            p['cdate'] = pr._id.generation_time.replace(tzinfo=None)
            p['shortname'] = pr.shortname
            if p['isMember']:
                myProj.append(p)
            else:
                retProj.append(p)
        return {'projects': retProj, 'myProjects': myProj}

    @expose('dashboard/index.html')
    def index(self, **kwargs):
        projects = []
        neighborhood_ids = set()
        archive_tool_configs = []
        for project in c.user.my_projects():
            if not project.is_real() or project.deleted:
                continue
            projects.append(project)
            neighborhood_ids.add(project.neighborhood_id)
        projects.sort(key=lambda x: x.name)
        project_ids = [x._id for x in projects]
        project_ids_set = set(project_ids)

        # projects to which user has been invited
        project_invites = []
        vites = MembershipInvitation.query.find({'user_id': c.user._id})
        for vite in vites:
            if not (vite.user in vite.project.users() or
                        vite.project.deleted):
                p_dict = vite.project.index()
                p_dict['project'] = vite.project
                p_dict['type'] = 'user'
                can_read = g.security.has_access(vite.project, 'read')
                p_dict['can_read'] = can_read
                p_dict['status'] = 'Invited'
                p_dict['id'] = vite._id
                project_invites.append(p_dict)

        # projects to which user has requested membership
        project_requests = []
        mreqs = MembershipRequest.query.find({'user_id': c.user._id})
        for req in mreqs:
            if not (req.user in req.project.users() or req.project.deleted):
                p_dict = req.project.index()
                p_dict['project'] = req.project
                p_dict['type'] = 'user'
                can_read = g.security.has_access(req.project, 'read')
                p_dict['can_read'] = can_read
                p_dict['status'] = 'Requested'
                p_dict['id'] = req._id
                project_requests.append(p_dict)

        # return info
        pcount = len([x for x in projects if not x.deleted])
        return {
            'user': c.user,
            'lastLog': c.user.last_login,
            'projects': pcount,
            'invites': project_invites,
            'mrequests': project_requests
        }

    @expose('json')
    @cache_json(name='user-projects', key='{args[1]}', timeout=5)
    def projects_info(self, username):
        start_time = datetime.now()
        profile = {}
        user = User.by_username(username)
        prefs = user.user_fields.get("DashboardPrefs", {})
        projects = {x.shortname: x for x in user.my_projects()
                    if x.is_real() and not x.deleted and
                    g.security.has_access(x, "read", c.user)}
        profile['project_list'] = datetime.now() - start_time

        # tool content and activity information
        project_ids = [x._id for x in projects.values()]
        #tool_info = get_artifact_counts(user, project_ids=project_ids)
        tool_info = get_tools_info(user, project_ids, auth_user=c.user)
        tinfo = {x: {} for x in projects}
        for tool in tool_info['tools']:
            if tool['project_shortname'] in projects:
                pinfo = tinfo[tool['project_shortname']]
                tname = tool['tool_name']
                # address case irregularities in tool name
                if tname != "home":
                    tname = tname.capitalize()
                if tname not in pinfo:
                    pinfo[tname] = tool['artifact_counts']
                    pinfo[tname]['url'] = tool['url']
                else:
                    for ac in tool['artifact_counts']:
                        pinfo[tname][ac] += tool['artifact_counts'][ac]

        elapsed = datetime.now() - start_time
        profile['tool_info'] = elapsed - sum(profile.values(), timedelta())

        my_user = c.user.username == username
        info = {x: {} for x in projects}
        for project in projects:
            p = projects[project]
            can_admin = g.security.has_access(p, 'admin', user)
            total = new = 0
            # signal membership requests
            if my_user and can_admin:
                q = {'project_id': p._id,
                     'user_id': {"$ne": None}}
                mrequests = MembershipRequest.query.find(q)
                requests = [dict(user=x.user, id=x._id) for x in mrequests
                            if (self.public_users or x.user.public) and
                            not p.user_in_project(x.user._id)]
                new += len(requests)
            # tally counts
            for tool in tinfo[project]:
                total += tinfo[project][tool].get('all', 0)
                new += tinfo[project][tool].get('new', 0)
            # build info structure
            info[project] = dict(
                shortname=p.shortname,
                pref=prefs.get(p.shortname, True) if my_user else True,
                name=p.name,
                project_id=str(p._id),
                new=new,
                total=total,
                url=p.url(),
                icon_url=p.icon_url,
                can_admin=can_admin,
                tool_info = tinfo[project]
            )

        elapsed = datetime.now() - start_time
        profile['project_info'] = elapsed - sum(profile.values(), timedelta())

        # order return value by activity then total content
        ordered = sorted(info.values(),
                         key=itemgetter('new', 'total'), reverse=True)
        for i, item in enumerate(ordered):
            item['index'] = i

        elapsed = datetime.now() - start_time
        profile['ordering'] = elapsed - sum(profile.values(), timedelta())
        profiling = {k: str(v) for k, v in profile.items()}

        result = dict(projects=ordered, profiling=profiling)
        return result

    @expose('json')
    def userinfo(self, **kw):
        uinfo = c.user.get_profile_info()
        uf = c.user.user_fields
        info = {
            'name': uinfo['fullName'],
            'interests': uinfo['interests'],
            'username': c.user.username,
            'mission': uinfo['mission'],
            'expertise': c.user.expertise,
            'icon': c.user.icon_url(),
            'email': c.user.get_email_address(),
            'joined': uinfo['userSince'],
            'telephone': uf.get('telephone', None),
            'position': uf.get('position', None),
            'company': uf.get('company', None),
            'affil': uf.get('mai_affiliation', None),
            'forge_name': config.get("forge_name"),
            'url': c.user.url()
        }
        return info

    @expose('json')
    def updatePreferences(self, **kw):
        g.security.require_authenticated()
        failure_resp = {'status': 'Failure', 'reason': 'Invalid parameter'}
        if not 'prefs' in kw or type(kw['prefs']) is basestring:
            return failure_resp
        try:
            prefs = simplejson.loads(kw['prefs'])
        except Exception as e:
            return failure_resp
        if (type(prefs) is not dict or
                not all([type(x) is bool for x in prefs.values()])):
            return failure_resp
        else:
            projects = {x.shortname: x for x in c.user.my_projects()
                        if x.is_real() and not x.deleted}
            user_prefs = c.user.user_fields.get("DashboardPrefs", {})
            updates = {k: v for k, v in prefs.items() if k in projects}
            user_prefs.update(updates)
            c.user.user_fields["DashboardPrefs"] = user_prefs
            return {'status': 'Success'}

    @expose()
    def invitation_accept(self, id_string):
        if id_string:
            invite = MembershipInvitation.query.get(_id=ObjectId(id_string))
            if invite:
                project = invite.project
                if not project.deleted:
                    app = project.app_instance(project.home_ac)
                    with push_config(c, project=invite.project, app=app):
                        UserProfileController(invite.user).accept_membership(
                            invite.project.shortname
                        )
                    flash('Invitation accepted')
                else:
                    flash('Team not available')
            else:
                flash('Invitation not available')
        else:
            flash('failed')
        redirect('/dashboard')

    @expose()
    def invitation_decline(self, id_string):
        if not id_string:
            raise HTTPNotFound
        invite = MembershipInvitation.query.get(_id=ObjectId(id_string))
        if invite:
            invite.delete()
            flash('Invitation declined')
        else:
            flash('Invitation not available')
        redirect('/dashboard')

    @expose()
    def invitation_rescind(self, id_string):
        if not id_string:
            raise HTTPNotFound
        invite = MembershipInvitation.query.get(_id=ObjectId(id_string))
        if invite:
            invite.delete()
            flash('Invitation canceled')
        else:
            flash('Invitation not available')
        redirect('/dashboard')

    @expose()
    def membership_request_accept(self, id_string):
        if id_string:
            request = MembershipRequest.query.get(_id=ObjectId(id_string))
            if request:
                project = request.project
                if not project.deleted:
                    project.user_join_project(request.user, notify=True)
                    flash('Request accepted')
                else:
                    flash("Team not available")
            else:
                flash('Request not available')
        else:
            flash('failed')
        redirect('/dashboard')

    @expose()
    def membership_request_decline(self, id_string):
        if not id_string:
            raise HTTPNotFound
        request = MembershipRequest.query.get(_id=ObjectId(id_string))
        if request:
            request.delete()
            flash('Request declined')
        else:
            flash('Request not available')
        redirect('/dashboard')

    @expose()
    def membership_request_rescind(self, id_string):
        if not id_string:
            raise HTTPNotFound
        request = MembershipRequest.query.get(_id=ObjectId(id_string))
        if request:
            request.delete()
            flash('Request canceled')
        else:
            flash('Request not available')
        redirect('/dashboard')
