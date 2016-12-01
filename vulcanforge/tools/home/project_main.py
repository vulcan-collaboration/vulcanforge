import logging
from operator import itemgetter
import pymongo
from pprint import pformat
from datetime import datetime
import re

from markupsafe import Markup
from bson import ObjectId
from ming.odm import session, state
from webob import exc
from paste.deploy.converters import asbool
from pylons import tmpl_context as c, app_globals as g
from tg import config, expose, redirect, validate, flash
from tg.decorators import with_trailing_slash

from vulcanforge.auth.schema import ACE
from vulcanforge.common.app import Application
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import require_post, vardec
from vulcanforge.common.helpers import ago
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.common.util import nonce
from vulcanforge.common.util.datatable import DATATABLE_SCHEMA
from vulcanforge.common.util.http import raise_400
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.common.util.counts import get_home_info, get_artifact_counts
from vulcanforge.common.util.notifications import get_notifications
from vulcanforge.common.tasks.index import add_global_objs
from vulcanforge.neighborhood.exceptions import RegistrationError
from vulcanforge.tools.home.model import PortalConfig
from vulcanforge.tools.admin.admin_main import PROJECT_ADMIN_DESCRIPTION
from vulcanforge.project.model.membership import (
    MembershipCancelRequest,
    MembershipRemovalRequest
)
from vulcanforge.project.model import (
    Project,
    AppConfig,
    MembershipRequest,
    MembershipInvitation,
    ProjectRole,
    ProjectFile
)
from vulcanforge.artifact.model import LogEntry
from .model import AccessLogChecked

LOG = logging.getLogger(__name__)

TEMPLATE_HOME = 'home/'
COMMON_TEMPLATE_HOME = 'jinja:vulcanforge:common/templates/'

TOOL_ARTIFACTS = {
    'downloads': 'file',
    'wiki': 'page',
    'tickets': 'ticket',
    'discussion': 'post',
    'archive': 'dataset',
    'git': 'commit',
    'svn': 'commit'
}

class ProjectHomeApp(Application):
    has_chat = False
    tool_label = 'home'
    static_folder = 'home'
    default_mount_label = 'Project Home'
    is_customizable = False
    icons = {
        24: '{ep_name}/images/home_24.png',
        32: '{ep_name}/images/home_32.png',
        48: '{ep_name}/images/home_48.png'
    }
    visible_to_role = 'project.read'

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = ProjectHomeController()
        self.api_root = RootRestController()

    @classmethod
    def artifact_counts_by_kind(cls, app_configs, app_visits, tool_name):
        db, coll = ProjectRole.get_pymongo_db_and_collection()
        return get_home_info(coll, app_configs, app_visits, tool_name)

    @classmethod
    def permissions(cls):
        return {"read": Application.permissions()['read']}

    @classmethod
    def default_acl(cls):
        return {
            'Member': ['read'],
            '*anonymous': ['read']
        }

    def is_visible_to(self, user):
        """Whether the user can view the app."""
        return True

    def main_menu(self):
        """Apps should provide their entries to be added to the main nav
        :return: a list of :class:`<vulcanforge.common.types.SitemapEntry>`

        """
        return [SitemapEntry(self.config.options.mount_label.title(), '.')]

    @property
    def sitemap(self):
        return [SitemapEntry('Home', '.')]

    def sidebar_menu(self):
        menu_info = [
            SitemapEntry('Team info'),
            SitemapEntry("About", self.url),
        ]

        if c.project.user_in_project(user=c.user):
            menu_info.append(
                SitemapEntry(
                    "My Permissions",
                    c.app.url + "my_permissions"
                )
            )
        if g.security.has_access(c.project, 'admin'):
            db, log_coll = LogEntry.get_pymongo_db_and_collection()
            access_log_checked = AccessLogChecked.query.get(
                project_id=c.project._id,
                user_id=c.user._id)

            new_query_dict = {
                "project_id": c.project._id,
                "access_denied": True,
                "artifact_id": None
            }
            query_dict = new_query_dict.copy()
            if access_log_checked is not None:
                since = access_log_checked.last_checked
                if since is not None and isinstance(since, datetime):
                    new_query_dict["_id"] = {"$gt":ObjectId.from_datetime(since)}

            new_entry_count = log_coll.find(new_query_dict).count()
            all_entries = log_coll.find(query_dict).count()
            menu_info.append(
                SitemapEntry(
                    "Access Denials",
                    c.app.url + "access_denials",
                    small="{} / {}".format(new_entry_count, all_entries)
                )
            )

        return menu_info

    def admin_menu(self):
        return []

    def artifact_counts(self, since=None):
        db, role_coll = ProjectRole.get_pymongo_db_and_collection()

        query_dict = {
            "project_id":self.project._id,
            "user_id": {'$ne': None},
            "roles": {"$ne": []}
        }
        group_dict = {
            '_id': '$user_id',
            'id': {'$first': '$_id'}
        }

        role_aggregate = role_coll.aggregate([
            {'$match': query_dict},
            {'$group': group_dict}
        ])
        new_member_count = member_count = len(role_aggregate['result'])

        if since is not None and isinstance(since, datetime):
            query_dict['_id'] = {"$gt": ObjectId.from_datetime(since)}
            role_aggregate = role_coll.aggregate([
                {'$match': query_dict},
                {'$group': group_dict}
            ])
            new_member_count = len(role_aggregate['result'])

        return dict(
            new=new_member_count,
            all=member_count
        )


class ProjectHomeController(BaseController):

    _log_table_columns = [
        {
            "sTitle": "Access time",
            "mongo_field": "timestamp"
        },
        {
            "sTitle": "User",
            "mongo_field": "display_name"
        },
        {
            "sTitle": "URL",
            "mongo_field": "url"
        },
        {
            "sTitle": "Access denied",
            "mongo_field": "access_denied"
        }
    ]

    def _check_security(self):
        g.security.require_access(c.project, 'read')

    @with_trailing_slash
    @expose('home/project_index.html')
    def index(self, **kwargs):
        public_users = asbool(config.get('all_users_public', False))
        isAdmin = g.security.has_access(c.project, 'admin')
        is_member = bool(c.project.named_roles_in(c.user))
        visible_tools = self.has_visible_tools(c.project, c.user)
        retval = dict(is_member=is_member, visible_tools=visible_tools)
        if isAdmin:
            q = {'project_id': c.project._id,
                 'user_id' : {"$ne": None}}
            invites = MembershipInvitation.query.find(q)
            invitations = [dict(user=x.user, id=x._id) for x in invites
                           if (public_users or x.user.public) and
                           not c.project.user_in_project(x.user._id)]
            retval['invitations'] = invitations
            mrequests = MembershipRequest.query.find(q)
            requests = [dict(user=x.user, id=x._id) for x in mrequests
                        if (public_users or x.user.public) and
                        not c.project.user_in_project(x.user._id)]
            retval['requests'] = requests
        return retval

    @with_trailing_slash
    @expose(TEMPLATE_HOME + 'my_permissions.html')
    def my_permissions(self, **kw):
        tool_setups = []
        if g.security.has_access(c.project, 'admin'):
            tool_setups.append(dict(
                title="Project Setup",
                base_url=c.project.url(),
                description=PROJECT_ADMIN_DESCRIPTION,
                icon=dict(
                    url=c.project.icon_url,
                    class_name=""
                ),
                actions={
                    "Update Metadata": c.project.url() + 'admin/overview'
                },
                perm_descriptions=['You can administer this project']
            ))
        for ac in c.project.app_configs:
            if ac.is_visible_to(c.user) and ac.options.mount_point != 'home':
                App = ac.load()
                if App.admin_description or App.admin_actions:
                    app = App(c.project, ac)
                    # permission descriptions
                    perm_descriptions = []
                    if type(app.permissions) is dict:
                        for p in app.permissions:
                            if g.security.has_access(app, p):
                                if p in app.permissions and app.permissions[p]:
                                    perm_descriptions.append(
                                        'You can {}'.format(
                                            app.permissions[p].lower())
                                    )
                                else:
                                    perm_descriptions.append(
                                        'You have the {} permission'.format(p))
                    # tool infos
                    tool_actions = {
                        k: ac.url() + v['url']
                        for k, v in app.admin_actions.iteritems()
                        if not v.get('permission') or
                        g.security.has_access(app, v['permission'])
                    }
                    tool_setups.append(dict(
                        title=ac.options.mount_label,
                        base_url=ac.url(),
                        description=app.admin_description,
                        icon=dict(
                            url=ac.icon_url(48),
                            class_name=''
                        ),
                        actions=tool_actions,
                        perm_descriptions=perm_descriptions
                    ))
        return dict(tool_setups=tool_setups)

    @require_post()
    @expose('json')
    def renounce_membership(self, force_moderate=False, **kw):
        if force_moderate or c.project.moderated_renounce:
            if not MembershipCancelRequest:
                raise exc.HTTPNotFound
            MembershipCancelRequest.upsert(text=kw.get('text', ''))
        else:
            c.project.user_leave_project(c.user, notify=True)
        return dict(success=True)

    @require_post()
    @expose('json')
    def accept_membership(self, **kw):
        invite = MembershipInvitation.query.find({
            'user_id': c.user._id,
            'project_id': c.project._id
        }).first()
        if not invite:
            raise exc.HTTPForbidden(
                "You have not been invited to this project")
        try:
            c.project.user_join_project(c.user, notify=True)
        except RegistrationError:
            return dict(error="You do not have permission")
        return dict(location=c.app.url)

    @require_post()
    @expose('json')
    def deny_membership(self, **kw):
        MembershipInvitation.query.remove({
            'user_id': c.user._id,
            'project_id': c.project._id
        })
        return dict(location=c.app.url)

    @require_post()
    @expose()
    def request_membership(self, text='', **kw):
        if not MembershipRequest:
            raise exc.HTTPNotFound
        with g.context_manager.push(c.project.shortname, 'admin'):
            MembershipRequest.upsert(text=text)
            session(MembershipRequest).flush()
        redirect("index/")

    @require_post()
    @expose('json')
    def cancel_request(self, **kw):
        if not MembershipRequest:
            raise exc.HTTPNotFound
        MembershipRequest.query.remove({
            'project_id': c.project._id,
            'user_id': c.user._id
        })
        session(MembershipRequest).flush()
        return dict(location=c.app.url)

    @require_post()
    @expose('json')
    def cancel_leave_request(self, **kw):
        if not MembershipCancelRequest:
            raise exc.HTTPNotFound
        MembershipCancelRequest.query.remove({
            'project_id': c.project._id,
            'user_id': c.user._id
        })
        session(MembershipCancelRequest).flush()
        return dict(location=c.app.url)

    @require_post()
    @expose('json')
    def accept_removal(self, **kw):
        if not MembershipRemovalRequest:
            raise exc.HTTPNotFound
        removal = MembershipRemovalRequest.query.get(
            project_id=c.project._id,
            user_id=c.user._id
        )
        if not removal:
            raise exc.HTTPNotFound
        c.project.user_leave_project(
            c.user,
            removed_by_id=removal.initiator_id,
            notify=True
        )
        MembershipRemovalRequest.query.remove({
            'project_id': c.project._id,
            'user_id': c.user._id
        })
        return dict(location=c.user.landing_url())

    @require_post()
    @expose('json')
    def deny_removal(self, text='', **kw):
        if not MembershipRemovalRequest:
            raise exc.HTTPNotFound
        removal = MembershipRemovalRequest.query.get(
            project_id=c.project._id,
            user_id=c.user._id
        )
        if not removal:
            raise exc.HTTPNotFound
        removal.reject(text=text)
        return dict(location=c.app.url)

    @expose('json')
    def get_member_icons(self, **kwargs):
        member_icons = {}
        for user in c.project.users():
            for role in c.project.named_roles_in(user):
                avatar = g.avatar.display(
                    user=user, size=32, compact=False, framed=True)
                member_icons.setdefault(role.display_name, []).append(avatar)
        return member_icons

    @expose('json')
    def get_membership_status(self, **kwargs):
        return {
            "status": c.project.get_membership_status(c.user)
        }

    @expose(TEMPLATE_HOME + 'project_dashboard_configuration.html')
    def configuration(self):
        config = PortalConfig.current()
        mount_points = [
            (ac.options.mount_point, ac.load())
            for ac in c.project.app_configs]
        widget_types = [
            dict(mount_point=mp, widget_name=w)
            for mp, app_class in mount_points
            for w in app_class.widget.widgets
        ]
        return dict(
            layout_class=config.layout_class,
            layout=config.layout,
            widget_types=widget_types)

    @vardec
    @expose()
    @require_post()
    def update_configuration(self, divs=None, layout_class=None, new_div=None,
                             **kw):
        g.security.require_access(c.project, 'write')
        config = PortalConfig.current()
        config.layout_class = layout_class
        # Handle updated and deleted divs
        if divs is None:
            divs = []
        new_divs = []
        for div in divs:
            LOG.info('Got div update:%s', pformat(div))
            if div.get('del'):
                continue
            new_divs.append(div)
        # Handle new divs
        if new_div:
            new_divs.append(dict(name=nonce(), content=[]))
        config.layout = []
        for div in new_divs:
            content = []
            for w in div.get('content', []):
                if w.get('del'):
                    continue
                mp, wn = w['widget'].split('/')
                content.append(dict(mount_point=mp, widget_name=wn))
            if div.get('new_widget'):
                content.append(dict(mount_point='home', widget_name='welcome'))
            config.layout.append(dict(name=div['name'], content=content))
        redirect('configuration')

    @with_trailing_slash
    @expose(COMMON_TEMPLATE_HOME + 'access_log.html')
    def access_denials(self):
        g.security.require_access(c.project, 'admin')

        AccessLogChecked.upsert(c.user._id, c.app.config._id, c.project._id)

        data_url = "{}log_data".format(c.app.config.url())
        return dict(
            data_url=data_url,
            title="{} - Access Denials".format(c.project.name),
            header="{} - Access Denials".format(c.project.name),
            show_access_type=False
        )

    @expose('json', render_params={"sanitize": False})
    @validate(DATATABLE_SCHEMA, error_handler=raise_400)
    def log_data(self, iDisplayStart=0, iDisplayLength=None, sSearch=None,
                 iSortingCols=0, sEcho=0, **kwargs):
        g.security.require_access(c.project, 'admin')

        # assemble the query
        db, coll = pymongo_db_collection(LogEntry)

        query_dict = {'project_id': c.project._id, 'access_denied': True, "artifact_id": None}
        total = coll.find(query_dict).count()
        pipeline = [
            {'$match': query_dict}
        ]
        if iSortingCols > 0:
            sort_column = int(kwargs['iSortCol_0'])
            sort_dir_str = kwargs['sSortDir_0']
            field_name = self._log_table_columns[sort_column]['mongo_field']
            sort_dir = pymongo.ASCENDING
            if sort_dir_str.lower() == 'desc':
                sort_dir = pymongo.DESCENDING
            pipeline.append({'$sort': {field_name: sort_dir}})
        pipeline.append({'$skip' : iDisplayStart})
        pipeline.append({'$limit' : iDisplayLength})

        aggregate = coll.aggregate(pipeline)

        # format the data
        data = []
        for log_entry in aggregate['result']:
            row = [
                log_entry['timestamp'].strftime('%m/%d/%Y %H:%M:%S UTC'),
                Markup('<a href="/u/{}">{}</a>'.format(
                    log_entry['username'], log_entry['display_name'])),
                Markup('<a href="{}">{}</a>'.format(
                    log_entry['url'], log_entry['url'])),
                log_entry.get('access_denied', False)
            ]

            data.append(row)

        response = {
            'iTotalRecords': total,
            'iTotalDisplayRecords': total,
            'sEcho': sEcho,
            'aaData': data
        }
        return response

    @classmethod
    def has_visible_tools(cls, project, user):
        visible_tools = [x.tool_name for x in project.app_configs
                         if x.tool_name.lower() != "home" and
                         x.is_visible_to(user)]
        return len(visible_tools) > 0

    @expose('json')
    def profile_info(self):
        is_admin = g.security.has_access(c.project, 'admin')
        is_member = is_admin or c.project.user_in_project(user=c.user) is not None

        project_read_roles = c.project.get_expanded_read_roles()
        read_roles = [x.name for x in project_read_roles]
        private = not ('*anonymous' in read_roles or
                       '*authenticated' in read_roles)
        storage_used = 0
        counts = get_artifact_counts(c.user, c.project.shortname)
        excludes = ('home', 'chat', 'calendar')
        tool_info = [x for x in counts['tools']
                     if x['tool_name'] not in excludes]
        for t in tool_info:
            storage_used += t['artifact_counts'].get('total_size', 0)

        info = dict(
            name=c.project.name,
            shortname=c.project.shortname,
            url=c.project.url(),
            icon_url=c.project.icon_url,
            admin=is_admin,
            member=is_member,
            deleted=c.project.deleted,
            private=private,
            created=c.project.registration_datetime,
            summary=c.project.short_description,
            storage=storage_used
        )
        return info

    @expose('json')
    def users_info(self):
        public_users = asbool(config.get('all_users_public', False))
        isAdmin = g.security.has_access(c.project, 'admin')
        users = []
        project_users = {x._id: x for x in c.project.users()
                         if x.is_real_user() and not x.disabled}

        for user in project_users.values():
            named_roles = c.project.named_roles_in(user)
            user_roles = ", ".join(sorted([x.name for x in named_roles]))
            q = dict(project_id=c.project._id, user_id=user._id)
            project_role = ProjectRole.query.get(**q)
            member_since = None
            if project_role:
                member_since = project_role._id.generation_time
            if user_roles:
                p_dict = {}
                p_dict['name'] = user.display_name
                p_dict['public'] = public_users or user.public
                p_dict['roles'] = user_roles
                p_dict['url'] = user.url()
                p_dict['icon_url'] = user.icon_url()
                p_dict['joined'] = datetime.isoformat(member_since)
                users.append(p_dict)
        can_request = not (c.user._id in project_users or
                           c.project.user_requested(c.user) or
                           c.project.user_invited(c.user))
        first_role = lambda x: (x['roles'].split(', ')[0], x['name'])
        return {'users': sorted(users, key=first_role),
                'canAdmin': isAdmin,
                'canRequest': can_request,
                'projectURL': c.project.url()}

    @expose('json')
    def tools_info(self):
        tools = []
        canAdmin = g.security.has_access(c.project, 'admin')
        counts = get_artifact_counts(c.user, c.project.shortname)
        excludes = ('home', 'chat', 'calendar')
        tool_info = [x for x in counts['tools']
                     if x['tool_name'] not in excludes]

        project_read_roles = c.project.get_expanded_read_roles()
        read_roles = [x.name for x in project_read_roles]
        project_private = not ('*anonymous' in read_roles or
                               '*authenticated' in read_roles)
        for t in tool_info:
            p_dict = {}
            tool = AppConfig.query.get(_id=ObjectId(t['id']))
            p_dict['name'] = tool.options['mount_label']
            p_dict['project_id'] = tool.project_id
            p_dict['mount'] = tool.options['mount_point']
            p_dict['icon_url'] = tool.icon_url(48)
            p_dict['tool_url'] = tool.url()
            p_dict['new'] = t['artifact_counts']['new']
            p_dict['total'] = t['artifact_counts']['all']
            if 'total_size' in t['artifact_counts']:
                p_dict['total_size'] = t['artifact_counts']['total_size']
            tool_name = tool.tool_name.lower()
            if tool_name in TOOL_ARTIFACTS:
                p_dict['artifact'] = TOOL_ARTIFACTS[tool_name]
            if project_private:
                p_dict['private'] = True
            else:
                ac_read_roles = tool.get_read_roles()
                p_dict['private'] = not ('anonymous' in ac_read_roles or
                                         'authenticated' in ac_read_roles)
            tools.append(p_dict)
        tools.sort(key=itemgetter('new'), reverse=True)
        return {'tools': tools,
                'canAdmin': canAdmin,
                'projectURL': c.project.url(),
                'num': len(tools)}

    @expose('json')
    def activity(self, from_dt=None, to_dt=None, **kw):
        """returns the project's recent activity via notifications"""
        limit = 25
        results = get_notifications(
            c.user, c.project, from_dt, to_dt, limit=limit, **kw)

        has_more = 'true' if results.hits > limit else 'false'
        json = '{{"notifications":[{notifications}],' \
               '"more":{more},"project_id":"{project_id}"}}'.format(
            notifications=','.join(d['json_s'] for d in results.docs),
            more=has_more, project_id=str(c.project._id)
        )
        return Markup(json)

    @require_post()
    @expose('json')
    def do_edit_profile(self, name="", summary="", parent=None, private=False,
                        deleted=False, icon=None, **kw):
        g.security.require_access(c.project, 'admin')
        if name:
            name_regex = re.compile("^[A-Za-z]+[A-Za-z0-9 -]*$")
            mo = name_regex.match(name)
            if not mo:
                return {"status": "error", "reason": "Invalid team name"}
            elif c.project.name != name and Project.query.get(name=name):
                return {"status": "error", "reason": "Name already used"}
            else:
                c.project.name = name.encode('utf-8')
                # summary
            c.project.short_description = summary
        # parent
        if parent:
            parent_team = Project.query.get(shortname=parent)
            if not parent_team or parent_team.deleted:
                return {"status": "error", "reason": "Invalid parent"}
            c.project.parent_id = parent_team._id
        # private
        private = asbool(private)
        project_read_roles = c.project.get_expanded_read_roles()
        read_roles = [x.name for x in project_read_roles]
        project_private = not ('*anonymous' in read_roles or
                               '*authenticated' in read_roles)
        get_role = lambda x: ProjectRole.query.get(name=x,
                                                   project_id=c.project._id)
        if private and not project_private:
            role_names = ('*authenticated', '*anonymous')
            roles = [get_role(x) for x in role_names]
            role_ids = [x._id for x in roles if x]
            c.project.acl = [ace for ace in c.project.acl if
                             ace['access'] != ACE.ALLOW or
                             ace['permission'] != 'read' or
                             ace['role_id'] not in role_ids]
        elif not private and project_private:
            role = get_role('*authenticated')
            c.project.acl.append(ACE.allow(role._id, 'read'))
        # deleted
        deleted = asbool(deleted)
        c.project.deleted = deleted
        # team icon
        if icon is not None:
            if c.project.icon:
                ProjectFile.remove(dict(
                    project_id=c.project._id,
                    category='icon'
                ))
            ProjectFile.save_image(
                icon.filename,
                icon.file,
                content_type=icon.type,
                square=True,
                thumbnail_size=(64, 64),
                thumbnail_meta=dict(project_id=c.project._id,
                                    category='icon'))
            session(ProjectFile).flush()
            g.cache.redis.expire('navdata', 0)
            if state(c.project).status != "dirty":
                add_global_objs.post([c.project.index_id()])
        return {"status": "success"}

    @with_trailing_slash
    @expose('home/project_index.html')
    def about(self, **kw):
        redirect('..')

    @expose()
    def invitation_rescind(self, id_string):
        if not id_string:
            raise exc.HTTPNotFound
        invite = MembershipInvitation.query.get(_id=ObjectId(id_string))
        if invite:
            invite.delete()
            flash('Invitation canceled')
        else:
            flash('Invitation not available')
        redirect('..')

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
        redirect('..')

    @expose()
    def membership_request_decline(self, id_string):
        if not id_string:
            raise exc.HTTPNotFound
        request = MembershipRequest.query.get(_id=ObjectId(id_string))
        if request:
            request.delete()
            flash('Request declined')
        else:
            flash('Request not available')
        redirect('..')

    # the following method is overloaded simply to redirect
    # to user dashboard after membership requests

    @require_post()
    @expose()
    def request_membership(self, text='', **kw):
        if not MembershipRequest:
            raise exc.HTTPNotFound
        with g.context_manager.push(c.project.shortname, 'admin'):
            MembershipRequest.upsert(text=text)
            session(MembershipRequest).flush()
        redirect("/dashboard")


class RootRestController(BaseController):

    def _check_security(self):
        g.security.require_access(c.project, 'read')

    @expose('json')
    def index(self, **kwargs):
        return dict(shortname=c.project.shortname)
