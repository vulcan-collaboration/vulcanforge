import logging
import time
from datetime import datetime
from uuid import UUID
import json
import pymongo
import re

from pylons import tmpl_context as c, app_globals as g, request
from tg import config
from bson import ObjectId
from ming import schema as S
from ming.utils import LazyProperty
from ming.odm import ThreadLocalODMSession, Mapper
from ming.odm import session, state
from ming.odm import FieldProperty, RelationProperty, ForeignIdProperty
from ming.odm.declarative import MappedClass
from vulcanforge.auth.model import User
from vulcanforge.common.model.base import BaseMappedClass

from vulcanforge.common.model.session import (
    main_orm_session,
    project_orm_session
)
from vulcanforge.common.model.filesystem import File
from vulcanforge.common.model.index import SOLRIndexed
from vulcanforge.common.helpers import strip_str
from vulcanforge.common.types import SitemapEntry
from vulcanforge.common.util import title_sort, push_config
from vulcanforge.common.util.decorators import exceptionless
from vulcanforge.auth.schema import ACL, ACE, EVERYONE
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.tasks import unindex_project, reindex_project

LOG = logging.getLogger(__name__)

BANISH_TEXT = "Your membership has been revoked from {}."


class ProjectFile(File):

    class __mongometa__:
        name = 'project_file'
        session = main_orm_session
        indexes = [('project_id', 'category')] + File.__mongometa__.indexes

    project_id = FieldProperty(S.ObjectId)
    category = FieldProperty(str)
    caption = FieldProperty(str)

    @property
    def project(self):
        return Project.query.get(_id=self.project_id)

    @property
    def default_keyname(self):
        keyname = super(ProjectFile, self).default_keyname
        return '/'.join(('Project', self.project.shortname, keyname))

    def local_url(self):
        return self.project.url() + 'icon'


class AppConfigFile(File):

    class __mongometa__:
        name = 'app_config_file'
        session = main_orm_session
        indexes = [('app_config_id', 'category')] + File.__mongometa__.indexes

    app_config_id = FieldProperty(S.ObjectId)
    category = FieldProperty(str)
    size = FieldProperty(int)

    THUMB_URL_POSTFIX = ''

    @property
    def app_config(self):
        return AppConfig.query.get(_id=self.app_config_id)

    @property
    def default_keyname(self):
        keyname = super(AppConfigFile, self).default_keyname
        return '/'.join(('AppConfigFile', str(self.app_config_id), keyname))

    def local_url(self):
        return self.app_config.project.url() + 'app_icon/' + \
               self.app_config.options.get('mount_point')


class ProjectCategory(MappedClass):
    class __mongometa__:
        session = main_orm_session
        name = 'project_category'

    _id = FieldProperty(S.ObjectId)
    parent_id = FieldProperty(S.ObjectId, if_missing=None)
    name = FieldProperty(str)
    label = FieldProperty(str, if_missing='')
    description = FieldProperty(str, if_missing='')

    @property
    def parent_category(self):
        return self.query.get(_id=self.parent_id)

    @property
    def subcategories(self):
        return self.query.find(dict(parent_id=self._id)).all()


class Project(SOLRIndexed):
    _perms_base = ['read', 'write', 'admin']
    _perms_proj = _perms_base[:]
    _perms_init = _perms_base + ['register', 'overseer']

    class __mongometa__:
        name = 'project'
        polymorphic_on = 'kind'
        polymorphic_identity = 'project'
        indexes = [
            'name',
            'sortable_name',
            'neighborhood_id',
            ('neighborhood_id', 'name'),
            'shortname',
            'parent_id',
            'sortable_activity']

        def before_save(self):
            if self.name is None and self.shortname is not None:
                self.name = self.shortname
            self.sortable_name = title_sort(self.name)
            self.stripped_name = strip_str(self.name)

    type_s = 'Project'
    type_label = 'Project'

    # Project schema
    kind = FieldProperty(str, if_missing='project')
    parent_id = FieldProperty(S.ObjectId, if_missing=None)
    neighborhood_id = ForeignIdProperty(Neighborhood)
    shortname = FieldProperty(str)
    name = FieldProperty(str)
    sortable_name = FieldProperty(str, if_missing=None)
    stripped_name = FieldProperty(str, if_missing=None)
    notifications_disabled = FieldProperty(bool)
    show_download_button = FieldProperty(bool, if_missing=True)
    short_description = FieldProperty(str, if_missing='')
    description = FieldProperty(str, if_missing='')
    homepage_title = FieldProperty(str, if_missing='')
    external_homepage = FieldProperty(str, if_missing='')
    support_page = FieldProperty(str, if_missing='')
    support_page_url = FieldProperty(str, if_missing='')
    removal = FieldProperty(str, if_missing='')
    moved_to_url = FieldProperty(str, if_missing='')
    removal_changed_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    export_controlled = FieldProperty(bool, if_missing=False)
    database = FieldProperty(S.Deprecated)
    database_uri = FieldProperty(str)
    is_root = FieldProperty(bool)
    acl = FieldProperty(ACL())
    neighborhood_invitations = FieldProperty([S.ObjectId])
    neighborhood = RelationProperty(Neighborhood)
    app_configs = FieldProperty(S.Deprecated)  # RelationProperty('AppConfig')
    category_id = FieldProperty(S.ObjectId, if_missing=None)
    deleted = FieldProperty(bool, if_missing=False)
    labels = FieldProperty([str])
    last_updated = FieldProperty(datetime, if_missing=None)
    tool_data = FieldProperty({str: {str: None}})  # entry point: prefs dict
    ordinal = FieldProperty(int, if_missing=0)
    database_configured = FieldProperty(bool, if_missing=True)
    _extra_tool_status = FieldProperty([str])
    moderated_renounce = FieldProperty(bool, if_missing=False)
    _uuid = FieldProperty(str, if_missing=None)  # access via uuid property

    activity = FieldProperty(int, if_missing=0)

    allow_membership_request = FieldProperty(bool, if_missing=True)
    display_membership_info = FieldProperty(bool, if_missing=True)

    # begin special case options
    disable_notification_emails = FieldProperty(bool, if_missing=False)
    # end special case options

    def __json__(self):
        return {
            '_id': str(self._id),
            'neighborhood_id': str(self.neighborhood_id),
            'name': self.get_display_name(),
            'shortname': self.shortname,
            'description': self.description,
            'short_description': self.short_description,
            'url': self.url(),
            'icon_url': self.icon_url,
        }

    @classmethod
    def by_url_path(cls, url_path):
        for n in Neighborhood.query.find():
            if url_path.strip("/").startswith(n.url_prefix.strip("/")):
                break
        else:
            return None, url_path
        # url_prefix
        project_part = n.shortname_prefix + url_path[len(n.url_prefix):]
        parts = project_part.split('/')
        length = len(parts)
        while length:
            shortname = '/'.join(parts[:length])
            p = Project.query.get(shortname=shortname, deleted=False)
            if p:
                return p, parts[length:]
            length -= 1
        return None, url_path.split('/')

    def index(self, text_objects=None, **kwargs):
        text_objects = text_objects or []

        if self.private_project_of() is None:
            return super(Project, self).index(text_objects, **kwargs)
        else:
            return None

    @property
    def uuid(self):
        if not self._uuid:
            self._uuid = str(UUID(str(self._id) + "1" * 8))
            session(self.__class__).flush(self)
        return UUID(self._uuid)

    @property
    def app_configs(self):
        return AppConfig.query.find({'project_id': self._id}).all()

    @property
    def index_dict(self):
        return dict(
            name_s=self.name,
            title_s='Project %s' % self.name,
            shortname_s=self.shortname,
            short_description_s=self.short_description,
            description_s=self.description,
            labels_s=', '.join(self.labels),
            last_updated_dt=self.last_updated,
            icon_url_s=self.icon and self.icon_url or '',
            activity_i=self.activity,
            neighborhood_id_s=str(self.neighborhood_id),
            deleted_b=self.deleted,
            is_root_b=self.is_root,
            url_s=self.url(),
            category_id_s=str(self.category_id),
            registration_time_dt=self.registration_datetime
        )

    @property
    def index_text_objects(self):
        return [self.name, self.short_description, self.description]

    def indexable(self):
        return (self.is_root and
                self.private_project_of() is None and
                '--init--' not in self.shortname)

    def get_read_roles(self):
        """
        Returns IDs of most basic role(s) that have read access

        For example, if anonymous has read access this method will not return
        authenticated, because authenticated is a subset

        """
        return g.security.roles_with_permission(self, 'read')

    def get_expanded_read_roles(self):
        """Returns all roles that have read access"""
        read_role_ids = self.get_read_roles()

        # special cases = special role + all named
        if read_role_ids == ['anonymous']:
            return [
                ProjectRole.authenticated(self),
                ProjectRole.anonymous(self)
            ] + self.named_roles
        if read_role_ids == ['authenticated']:
            return [ProjectRole.authenticated(self)] + self.named_roles

        read_role_ids = map(ObjectId, read_role_ids)

        # named roles only ==> append children of roles that have read access
        base_roles = ProjectRole.query.find({
            '_id': {'$in': read_role_ids}
        })
        read_roles = []
        for role in base_roles:
            read_roles.append(role)
            for child in role.all_children():
                if child._id not in read_role_ids:
                    read_role_ids.append(child._id)
                    read_roles.append(child)
        return read_roles

    def get_roles(self, permission):
        return g.security.roles_with_permission(self, permission)

    @classmethod
    def by_id(cls, _id):
        """
        :rtype: Project
        """
        return cls.query.get(_id=_id)

    @classmethod
    def active_count(cls, neighborhood_ids=None):
        """Get the total number of active projects.

        'active' for now means that a project belongs to the 'Projects'
        neighborhood and is not marked as deleted.

        @param cls:
        @return: Number of active projects
        @rtype: int
        """
        query = [
            'type_s:(Project)',
            'deleted_b:(false)',
        ]
        if neighborhood_ids is not None:
            query.append('neighborhood_id_s:(%s)' % ' OR '.join(
                map(str, neighborhood_ids)))
        results = g.search(' AND '.join(query))
        if results is None:
            return 0
        return results.hits

    @property
    def permissions(self):
        if self.shortname == '--init--':
            return self._perms_init
        else:
            return self._perms_proj

    def parent_security_context(self):
        """ACL processing should proceed up the project hierarchy."""
        return self.parent_project

    @classmethod
    def default_database_uri(cls, shortname):
        return config.get('ming.project.database')

    @LazyProperty
    def allowed_tool_status(self):
        return ['production'] + self._extra_tool_status

    @exceptionless([], LOG)
    def sidebar_menu(self):
        result = []
        if not self.is_root:
            p = self.parent_project
            result.append(SitemapEntry('Parent Project'))
            result.append(SitemapEntry(p.name or p.script_name, p.script_name))
        sps = self.direct_subprojects
        if sps:
            result.append(SitemapEntry('Child Projects'))
            result += [
                SitemapEntry(p.name or p.script_name, p.script_name)
                for p in sps
            ]
        return result

    def get_tool_data(self, tool, key, default=None):
        return self.tool_data.get(tool, {}).get(key, None)

    def set_tool_data(self, tool, **kw):
        d = self.tool_data.setdefault(tool, {})
        d.update(kw)
        state(self).soil()

    def admin_menu(self):
        return []

    def is_real(self):
        return not (self.shortname == '--init--' or self.is_user_project())

    def is_user_project(self):
        return self.neighborhood.name == 'Users'

    @property
    def can_register_users(self):
        return (self.shortname == config.get('site_admin_project')) or \
               (self.shortname == '--init--' and
                self.neighborhood.can_register_users)

    @property
    def script_name(self):
        url = self.url()
        if '//' in url:
            return url.rsplit('//')[-1]
        else:
            return url

    def url(self):
        if self.shortname.endswith('--init--'):
            return self.neighborhood.url()
        shortname = self.shortname[len(self.neighborhood.shortname_prefix):]
        url = self.neighborhood.url_prefix + shortname + '/'
        if url.startswith('//'):
            try:
                return request.scheme + ':' + url
            except TypeError:  # pragma no cover
                return 'http:' + url
        else:
            return url

    def best_download_url(self):
        return None

    @property
    def icon(self):
        icon_file = None
        if self.shortname == '--init--':
            icon_file = self.neighborhood.icon
        if not icon_file:
            icon_file = ProjectFile.query.get(
                project_id=self._id,
                category='icon')
        return icon_file

    @property
    def icon_url(self):
        icon = self.icon
        if icon:
            return icon.url()
        else:
            return g.resource_manager.absurl('images/project_default.png')

    @property
    def member_agreement(self):
        return ProjectFile.query.get(
            project_id=self._id,
            category='member_agreement')

    @property
    def member_agreement_url(self):
        return '{}member_agreement'.format(self.url())

    @property
    def description_html(self):
        return g.markdown.convert(self.description)

    @property
    def parent_project(self):
        if self.is_root:
            return None
        return self.query.get(_id=self.parent_id)

    def private_project_of(self):
        """If this is a user-project, return the User, else None"""
        from vulcanforge.auth.model import User

        user = None
        if self.shortname.startswith('u/'):
            user = User.query.get(username=self.shortname[2:])
        return user

    @LazyProperty
    def root_project(self):
        if self.is_root:
            return self
        return self.parent_project.root_project

    @LazyProperty
    def project_hierarchy(self):
        if not self.is_root:
            return self.root_project.project_hierarchy
        projects = set([self])
        while True:
            new_projects = set(
                self.query.find(dict(
                    parent_id={'$in': [p._id for p in projects]}))
            )
            new_projects.update(projects)
            if new_projects == projects:
                break
            projects = new_projects
        return projects

    @property
    def category(self):
        return ProjectCategory.query.find(dict(_id=self.category_id)).first()

    def roleids_with_permission(self, name):
        roles = set()
        for p in self.parent_iter():
            for ace in p.acl:
                if ace.permission == name and ace.access == ACE.allow:
                    roles.add(ace.role_id)
        return list(roles)

    @classmethod
    def menus(cls, projects):
        """Return a dict[project_id] = sitemap of sitemaps, efficiently"""
        pids = [p._id for p in projects]
        project_index = dict((p._id, p) for p in projects)
        entry_index = dict((pid, []) for pid in pids)
        q_subprojects = cls.query.find(dict(
                parent_id={'$in': pids},
                deleted=False))
        for sub in q_subprojects:
            entry_index[sub.parent_id].append(dict(
                ordinal=sub.ordinal,
                entry=SitemapEntry(sub.name, sub.url())
            ))
        q_app_configs = AppConfig.query.find(dict(
                project_id={'$in': pids}))
        for ac in q_app_configs:
            if ac.is_visible_to(c.user):
                entry = SitemapEntry(ac.options.mount_label)
                entry.url = '.'
                entry.ui_icon = 'tool-%s' % ac.tool_name.lower()
                ordinal = ac.options.get('ordinal', 0)
                entry_index[ac.project_id].append({
                    'ordinal': ordinal,
                    'entry': entry
                })
        sitemaps = dict((pid, SitemapEntry('root').children) for pid in pids)
        for pid, entries in entry_index.iteritems():
            entries.sort(key=lambda e: e['ordinal'])
            sitemap = sitemaps[pid]
            for e in entries:
                sitemap.append(e['entry'])
        return sitemaps

    @classmethod
    def icon_urls(cls, projects):
        """Return a dict[project_id] = icon_url, efficiently"""
        result = {
            p._id: g.resource_manager.absurl('images/project_default.png')
            for p in projects}
        ico_query = {
            'project_id': {'$in': result.keys()},
            'category': 'icon'
        }
        for icon in ProjectFile.query.find(ico_query):
            result[icon.project_id] = icon.url()
        return result

    def sitemap(self):
        sitemap = SitemapEntry('root')
        entries = []
        for sub in self.direct_subprojects:
            if not sub.deleted:
                entries.append({
                    'ordinal': sub.ordinal,
                    'entry': SitemapEntry(sub.name, sub.url())
                })
        for ac in self.app_configs:
            if ac.is_visible_to(c.user):
                entry = SitemapEntry(ac.options.mount_label)
                entry.url = ac.url()
                entry.ui_icon = 'tool-%s' % ac.tool_name.lower()
                entry.icon_url = ac.icon_url(32)
                ordinal = ac.options.get('ordinal', 0)
                entries.append({'ordinal': ordinal, 'entry': entry})
        entries = sorted(entries, key=lambda e: e['ordinal'])
        for e in entries:
            sitemap.children.append(e['entry'])
        return sitemap.children

    def parent_iter(self):
        yield self
        pp = self.parent_project
        if pp:
            for p in pp.parent_iter():
                yield p

    @property
    def subprojects(self):
        q = self.query.find(dict(
            shortname={'$gt': self.shortname})).sort('shortname')
        for project in q:
            if project.shortname.startswith(self.shortname + '/'):
                yield project
            else:
                break

    @property
    def direct_subprojects(self):
        return self.query.find(dict(parent_id=self._id))

    @property
    def named_roles(self):
        roles = sorted(
            g.security.credentials.project_roles(self.root_project._id).named,
            key=lambda r: r.name.lower())
        return roles

    @property
    def default_role(self):
        role = None
        for role in self.named_roles:
            if role.name == 'Member':
                return role
        return role

    @property
    def admin_users(self):
        for role in self.named_roles:
            if role.name == u'Admin':
                break
        else:
            return []
        return [r.user for r in role.users_with_role()]

    def install_app(self, ep_name, mount_point=None, mount_label=None,
                    ordinal=None, acl=None, install_options=None,
                    **override_options):
        if install_options is None:
            install_options = {}
        App = g.tool_manager.tools[ep_name.lower()]["app"]

        if not mount_point:
            base_mount_point = mount_point = App.default_mount_point
            for x in range(10):
                if self.app_instance(mount_point) is None:
                    break
                mount_point = base_mount_point + '-%d' % x

        if ordinal is None:
            ordinal = int(self.ordered_mounts()[-1]['ordinal']) + 1
        options = App.default_options()
        options['mount_point'] = mount_point
        options['mount_label'] = mount_label or App.default_mount_label or \
                                 mount_point
        options['ordinal'] = int(ordinal)
        options.update(override_options)

        if acl is None and self.neighborhood.project_template:
            project_template = json.loads(self.neighborhood.project_template)
            acl = project_template.get('default_acl', {}).get(ep_name.lower())

        cfg = AppConfig(
            project_id=self._id,
            tool_name=ep_name,
            options=options)
        app = App(self, cfg)
        with push_config(c, project=self, app=app):
            session(cfg).flush()  # needed for artifacts created during install
            app.install(self, acl=acl, **install_options)
            session(cfg).flush()
        return app

    def uninstall_app(self, mount_point):
        app = self.app_instance(mount_point)
        if app is None:
            return
        if self.support_page == app.config.options.mount_point:
            self.support_page = ''
        with push_config(c, project=self, app=app):
            app.uninstall(self)

    def app_instance(self, mount_point_or_config):
        """
        @param mount_point_or_config: The mount point or the AppConfig to
            lookup
        @type mount_point_or_config: AppConfig or str or unicode
        @return: The App or None if there is no matching App
        @rtype: None or App

        """
        if isinstance(mount_point_or_config, AppConfig):
            app_config = mount_point_or_config
        else:
            app_config = self.app_config(mount_point_or_config)
        if app_config is None:
            return None
        App = app_config.load()
        if App is None:
            return None
        else:
            return App(self, app_config)

    def app_config(self, mount_point):
        """
        @param mount_point: The mount point of the app
        @type mount_point: str or unicode
        @rtype: AppConfig

        """
        return AppConfig.query.find({
            'project_id': self._id,
            'options.mount_point': mount_point
        }).first()

    def ordered_mounts(self):
        """
        Returns an array of a projects mounts (tools and sub-projects) in
        toolbar order.

        """
        result = []
        for sub in self.direct_subprojects:
            result.append({
                'ordinal': int(sub.ordinal),
                'sub': sub,
                'rank': 1
            })
        for ac in self.app_configs:
            ordinal = ac.options.get('ordinal', 0)
            rank = 0 if ac.options.get('mount_point', None) == 'home' \
                   else 1
            result.append({
                'ordinal': int(ordinal),
                'ac': ac,
                'rank': rank
            })
        return sorted(result, key=lambda e: (e['ordinal'], e['rank']))

    def first_mount(self, required_access=None):
        """
        Returns the first (toolbar order) mount, or the first mount to
        which the user has the required access.

        """
        ProjectHomeApp = g.tool_manager.tools["home"]["app"]
        NeighborhoodHomeApp = g.tool_manager.tools["neighborhood_home"]["app"]
        mounts = self.ordered_mounts()
        if mounts and required_access is None:
            return mounts[0]
        for mount in mounts:
            if 'sub' in mount:
                obj = mount['sub']
            else:
                obj = self.app_instance(mount['ac'])

            if g.security.has_access(obj, required_access) or \
                    isinstance(obj, ProjectHomeApp) or \
                    isinstance(obj, NeighborhoodHomeApp):
                return mount
        return None

    @LazyProperty
    def home_ac(self):
        home_tools = {'home', 'team_home', 'neighborhood_home',
                      'competition_home'}
        for ac in self.app_configs:
            if ac.tool_name in home_tools:
                return ac
        return None

    def delete(self):
        # Cascade to subprojects
        for sp in self.direct_subprojects:
            sp.delete()
        # Cascade to app configs
        for ac in self.app_configs:
            ac.delete()
        MappedClass.delete(self)

    def render_widget(self, widget):
        app = self.app_instance(widget['mount_point'])
        with push_config(c, project=self, app=app):
            return getattr(app.widget(app), widget['widget_name'])()

    def breadcrumbs(self):
        entry = (self.name, self.url())
        if self.parent_project:
            trail = self.parent_project.breadcrumbs()
        else:
            trail = [(self.neighborhood.name, self.neighborhood.url())]
        return trail + [entry]

    def users(self):
        """Find all the users who have named roles for this project"""
        named_roles = g.security.RoleCache(
            g.security.credentials,
            g.security.credentials.project_roles(
                project_id=self.root_project._id).named
        )
        users = []
        for role in named_roles.roles_that_reach:
            if role.user_id:
                user = role.user
                if user:
                    users.append(user)
        return users

    def project_role(self, user):
        if user._id is None:
            return ProjectRole.anonymous(self)
        else:
            return ProjectRole.upsert(
                user_id=user._id, project_id=self._id)

    def named_roles_in(self, user):
        roles = []
        for pr_id in self.project_role(user).roles:
            pr = ProjectRole.query.get(_id=pr_id)
            if pr.name:
                roles.append(pr)
        return roles

    def user_in_project(self, username=None, user=None):
        from vulcanforge.auth.model import User

        if user is None and username is not None:
            user = User.by_username(username)
        if user is None:
            return None
        named_roles = g.security.credentials.project_roles(
            project_id=self.root_project._id).named
        for r in named_roles.roles_that_reach:
            if r.user_id == user._id:
                return user
        return None

    def user_invited(self, user):
        try:
            from vulcanforge.tools.admin.model import MembershipInvitation
        except ImportError:
            return False
        if MembershipInvitation.query.get(project_id=self._id,
                                          user_id=user._id):
            return True
        e_query = MembershipInvitation.query.find({
            'project_id': self._id,
            'email': {'$in': user.email_addresses}
        })
        invite = e_query.first()
        if invite:
            invite.user_id = user._id
            return True
        return False

    def user_requested(self, user):
        try:
            from vulcanforge.tools.admin.model import MembershipRequest
        except ImportError:
            return False
        return bool(
            MembershipRequest.query.get(project_id=self._id, user_id=user._id)
        )

    def user_requested_leave(self, user):
        try:
            from vulcanforge.tools.admin.model import MembershipCancelRequest
        except ImportError:
            return False
        return bool(
            MembershipCancelRequest.query.get(
                project_id=self._id, user_id=user._id)
        )

    def user_removal_requested(self, user):
        try:
            from vulcanforge.tools.admin.model import MembershipRemovalRequest
        except ImportError:
            return False
        return bool(
            MembershipRemovalRequest.query.get(
                project_id=self._id, user_id=user._id)
        )

    def user_join_project(self, user, role=None, notify=False,
                          notify_ac_id=None, **kw):
        from vulcanforge.tools.home.model import UserJoin
        self.neighborhood.assert_user_can_register(user)
        try:
            from vulcanforge.tools.admin import model as AM
        except ImportError:
            LOG.exception("Could not import admin app")
            AM = None
        if role is None:
            role = self.default_role
        pr = self.project_role(user)
        pr.roles.append(role._id)
        if AM is not None:
            q = {'user_id': user._id, 'project_id': self._id}
            AM.MembershipRequest.query.remove(q)
            AM.MembershipInvitation.query.remove(q)
        if notify_ac_id is None:
            notify_ac_id = self.home_ac._id
        with g.context_manager.push(self._id, app_config_id=notify_ac_id):
            ev = UserJoin(user_id=user._id, project_id=self._id, **kw)
            if notify:
                ev.notify()

        user.add_workspace_tab_for_project(self)

        return ev

    def user_leave_project(self, user, clean_roles=True, notify=False,
                           banished=False, **kw):
        from vulcanforge.notification.model import Mailbox
        from vulcanforge.tools.home.model import UserExit
        from vulcanforge.messaging.model import Conversation
        try:
            from vulcanforge.tools.admin.model import MembershipCancelRequest
        except ImportError:
            MembershipCancelRequest = None
        if clean_roles:
            pr = self.project_role(user)
            pr.roles = []
        q = {'user_id': user._id, 'project_id': self._id}
        Mailbox.query.remove(q)
        if MembershipCancelRequest is not None:
            MembershipCancelRequest.query.remove(q)
        with g.context_manager.push(self._id, app_config_id=self.home_ac._id):
            ev = UserExit(user_id=user._id, project_id=self._id, **kw)
            if notify:
                ev.notify()
        if banished:
            conversation = Conversation(subject="Membership Revoked")
            conversation.add_user_id(c.user._id)
            conversation.add_user_id(user._id)
            conversation.add_message(c.user._id, BANISH_TEXT.format(self.name))

        user.delete_workspace_tab_for_project(self)

        return ev

    def get_membership_status(self, user):
        if not user.active():
            return "NA"
        if self.user_in_project(user.username):
            if self.user_requested_leave(user):
                return 'member-requested-leave'
            if self.user_removal_requested(user):
                return 'removal-requested'
            return 'member'
        if not self.neighborhood.user_can_register(user):
            return 'no-register'
        if self.user_invited(user):
            return 'invited'
        if self.user_requested(user):
            return 'requested'
        return 'none'

    def install_default_acl(self, admins=None, is_private_project=False,
                            is_user_project=False):
        if admins is None:
            admins = []
        root_project_id = self.root_project._id

        # upsert project roles
        role_admin = ProjectRole.upsert(
            name='Admin', project_id=root_project_id)
        role_developer = ProjectRole.upsert(
            name='Developer', project_id=root_project_id)
        role_member = ProjectRole.upsert(
            name='Member', project_id=root_project_id)
        role_auth = ProjectRole.upsert(
            name='*authenticated', project_id=root_project_id)
        role_anon = ProjectRole.upsert(
            name='*anonymous', project_id=root_project_id)

        # Setup subroles
        role_admin.roles = [role_developer._id]
        role_developer.roles = [role_member._id]

        # Set acl
        self.acl = [
            ACE.allow(role_developer._id, 'read'),
            ACE.allow(role_member._id, 'read')
        ]
        if not is_private_project:
            # user projects have authenticated read only
            read_role = None
            if self.neighborhood.project_template:
                project_template = json.loads(
                    self.neighborhood.project_template)
                if 'default_read_role' in project_template:
                    read_role = ProjectRole.upsert(
                        name=project_template['default_read_role'],
                        project_id=root_project_id
                    )
            if read_role is None:
                read_role = role_auth if is_user_project else role_anon
            self.acl.append(ACE.allow(read_role._id, 'read'))
        self.acl += [
            ACE.allow(role_admin._id, perm) for perm in self.permissions]

        # Knight the admins
        for user in admins:
            pr = self.project_role(user)
            pr.roles = [role_admin._id]

    def _required_apps(self, is_user_project=False):
        if is_user_project:
            return [('profile', 'profile', 'Profile'),
                    ('admin', 'admin', 'Admin')]
        else:
            return [('home', 'home', 'Home'),
                    ('admin', 'admin', 'Admin')]

    def configure_project(self, users=None, apps=None, is_user_project=False,
                          is_private_project=False, app_install_opts=None):
        if app_install_opts is None:
            app_install_opts = {}
        self.notifications_disabled = True
        if users is None:
            users = [c.user]
        if apps is None:
            apps = self._required_apps(is_user_project)
        if is_user_project:
            app_install_opts.setdefault(
                'admin', {}).setdefault('subscribe_admins', False)
        with push_config(c, project=self, user=users[0]):
            self.install_default_acl(
                admins=users,
                is_private_project=is_private_project,
                is_user_project=is_user_project
            )

            session(self).flush(self)

            # Setup apps
            for i, (ep_name, mount_point, label) in enumerate(apps):
                install_options = app_install_opts.get(mount_point, {})
                self.install_app(
                    ep_name,
                    mount_point,
                    label,
                    ordinal=i,
                    install_options=install_options
                )
            self.database_configured = True
            self.notifications_disabled = False
            ThreadLocalODMSession.flush_all()

    def add_user(self, user, role_names):
        """Convenience method to add member with the given role(s)."""
        pr = self.project_role(user)
        for role_name in role_names:
            r = ProjectRole.by_name(role_name, self)
            pr.roles.append(r._id)

    def get_display_name(self):
        owner = self.private_project_of()
        if owner is not None:
            return owner.display_name
        return self.name

    @property
    def registration_datetime(self):
        gt = self._id.generation_time
        return datetime.utcfromtimestamp(time.mktime(gt.utctimetuple()))

    def delete_project(self, user=None):
        from vulcanforge.neighborhood.marketplace.model import (
            ProjectAdvertisement
        )
        from vulcanforge.auth.tasks import remove_workspacetabs
        if user is None:
            user = c.user
        LOG.info(
            "Deleting project: %s by user: %s",
            self.shortname, c.user.username
        )
        self.deleted = True
        ProjectAdvertisement.query.remove({'project_id': self._id})
        g.solr.delete(q='type_s: ProjectAdvertisement '
                        'AND project_id_s: {}'.format(str(self._id)))
        unindex_project.post(self._id)
        remove_workspacetabs.post('^' + re.escape(self.url()))
        for sp in self.subprojects:
            sp.delete_project(user)
        LOG.info("Project %s deleted by %s", self.shortname, user.username)

    def undelete_project(self):
        LOG.info("Undeleting project: %s", self.shortname)
        self.deleted = False
        reindex_project.post(self._id)
        for sp in self.subprojects:
            sp.undelete_project()

    def get_label_counts(self):
        labels = {}
        for ac in self.app_configs:
            for k, v in ac.label_count_data:
                try:
                    labels[k] += v
                except KeyError:
                    labels[k] = v
        return labels

    def update_label_counts(self):
        for ac in self.app_configs:
            ac.update_label_counts()

    def get_labels(self):
        label_counts = self.get_label_counts()
        return label_counts.keys()


class AppConfig(MappedClass):
    """
    Configuration information for an instantiated
    :class:`Application <vulcanforge.common.app.Application>` in a project

    :var options: an object on which various options are stored.
        options.mount_point is the url component for this app instance
    :var acl: a dict that maps permissions (strings) to lists of roles that
        have the permission

    """

    class __mongometa__:
        session = project_orm_session
        name = 'config'
        indexes = [
            ('_id',),
            ('project_id',)
        ]

    # AppConfig schema
    _id = FieldProperty(S.ObjectId)
    project_id = ForeignIdProperty(Project)
    discussion_id = FieldProperty(S.ObjectId)
    tool_name = FieldProperty(str)
    visible_to_role = FieldProperty(str, if_missing='read')
    version = FieldProperty(str)
    options = FieldProperty(None)
    project = RelationProperty(Project, via='project_id')
    reference_opts = FieldProperty(None, if_missing={})
    # treat below like: [[str, int], ...]
    label_count_data = FieldProperty(None, if_missing=[])

    acl = FieldProperty(ACL())

    @LazyProperty
    def app(self):
        return self.load()

    def __json__(self):
        return {
            '_id': str(self._id),
            'project_id': str(self.project_id),
            'tool_name': self.tool_name,
            'url': self.url(),
            'options': self.options,
            'icon_urls': {
                '24': self.icon_url(24),
                '32': self.icon_url(32),
                '48': self.icon_url(48),
            }
        }

    @LazyProperty
    def discussion_cls(self):
        from vulcanforge.discussion.model import Discussion
        return Discussion

    @LazyProperty
    def discussion(self):
        return self.discussion_cls.query.get(_id=self.discussion_id)

    def icon_url(self, size, skip_lookup=False):
        if not skip_lookup:
            icon = self.get_icon(size)
            if icon is not None:
                return self.project.url() + '/app_icon/' + \
                       self.options.get('mount_point')

        return self.app.icon_url(size, self.tool_name.lower())

    def parent_security_context(self):
        """ACL processing should terminate at the AppConfig"""
        return None

    def load(self):
        """
        :returns: the related :class:`Application
            <vulcanforge.common.app.Application>` instance

        """
        result = g.tool_manager.tools[self.tool_name.lower()]["app"]
        return result

    def update_label_counts(self):
        self.label_count_data = self.lookup_label_counts()

    def lookup_label_counts(self):
        app = self.load()
        labels = {}
        for artifact_cls in app.artifacts.values():
            db, coll = artifact_cls.get_pymongo_db_and_collection()
            pipeline = [
                {
                    '$match': {
                        'app_config_id': self._id,
                    },
                },
                {'$project': {'labels': 1}},
                {'$unwind': "$labels"},
                {
                    '$group': {
                        '_id': '$labels',
                        'count': {'$sum': 1},
                    },
                },
            ]
            aggregate = coll.aggregate(pipeline)
            for result in aggregate['result']:
                label = result['_id']
                count = result['count']
                try:
                    labels[label] += count
                except KeyError:
                    labels[label] = count
        return [[k, v] for k, v in labels.items()]

    def script_name(self):
        return self.project.script_name + self.options.mount_point + '/'

    def url(self):
        return self.project.url() + self.options.mount_point + '/'

    def breadcrumbs(self):
        return self.project.breadcrumbs() + [
            (self.options.mount_point, self.url())]

    def is_visible_to(self, user):
        if self.visible_to_role.startswith('project.'):
            split_perm = self.visible_to_role.split('project.')
            return g.security.has_access(self.project, split_perm[1], user)

        return g.security.has_access(
            self, self.visible_to_role, user, project=self.project)

    def has_access(self, permission, user=None):
        if user is None:
            user = c.user
        if self.project is None:
            LOG.warn("missing project with id %r", self.project_id)
            return False
        if self.tool_name == 'admin':
            return g.security.has_access(self.project, 'admin', c.user)
        return g.security.has_access(
            self, permission, user, project=self.project)

    def get_read_roles(self):
        if self.visible_to_role.startswith('project.'):
            split_perm = self.visible_to_role.split('project.')
            return self.project.get_roles(split_perm[1])

        read_roles = g.security.roles_with_permission(self, 'read')
        if not read_roles:
            read_roles = self.project.get_read_roles()
        return read_roles

    def clean_acl(self):
        read_ids = set(r._id for r in self.project.get_expanded_read_roles())
        read_ids.add(EVERYONE)
        old_acl = self.acl
        self.acl = []

        for ace in old_acl:
            # does old ace role have project read access?
            if ace['role_id'] in read_ids and not ace in self.acl:
                self.acl.append(ace)
            else:
                # if not, search the heirarchy upwards for read access,
                # starting with all direct children of the role
                role = ProjectRole.query.get(_id=ace['role_id'])
                if role:
                    readable = ProjectRole.fundamental_fulfillers(
                        role.children(),
                        lambda r: r._id in read_ids
                    )
                    for child in readable:
                        new_ace = ace.copy()
                        new_ace['role_id'] = child._id
                        if new_ace not in self.acl:
                            self.acl.append(new_ace)

    def get_icon(self, size=32):
        icon_file = AppConfigFile.query.get(
            app_config_id=self._id,
            category='icon',
            size=size)
        return icon_file


class ProjectRole(BaseMappedClass):
    """
    Per-project roles, called "Groups" in the UI.
    This can be a proxy for a single user.  It can also inherit roles.

    :var user_id: used if this role is for a single user
    :var project_id:
    :var name:
    :var roles: a list of other ProjectRole objectids from which this role
                inherits

    """
    class __mongometa__:
        session = main_orm_session
        name = 'project_role'
        unique_indexes = [('user_id', 'project_id', 'name')]
        indexes = [('user_id',), ('project_id',), ('roles',)]

    user_id = ForeignIdProperty('User', if_missing=None)
    project_id = ForeignIdProperty(Project, if_missing=None)
    name = FieldProperty(str)
    roles = FieldProperty([S.ObjectId])

    user = RelationProperty('User')
    project = RelationProperty(Project)

    def __init__(self, **kw):
        assert 'project_id' in kw, 'Project roles must specify a project id'
        super(ProjectRole, self).__init__(**kw)

    def display(self):
        if self.name:
            return self.name
        if self.user_id:
            u = self.user
            if u.username:
                uname = u.username
            elif u.get_pref('display_name'):
                uname = u.get_pref('display_name')
            else:
                uname = u._id
            return '*user-%s' % uname
        return '**unknown name role: %s' % self._id  # pragma no cover

    @property
    def display_name(self):
        return self.project.neighborhood.role_aliases.get(self.name, self.name)

    @classmethod
    def by_user(cls, user=None, project=None):
        if user is None and project is None:
            return c.user.current_project_role
        if user is None:
            user = c.user
        if project is None:
            project = c.project
        pr = cls.query.get(
            user_id=user._id,
            project_id=project.root_project._id)
        if pr is None:
            pr = cls.query.get(
                user_id=user._id,
                project_id={'$exists': False})
        return pr

    @classmethod
    def by_name(cls, name, project=None):
        if project is None:
            project = c.project
        if hasattr(project, 'root_project'):
            project = project.root_project
        if hasattr(project, '_id'):
            project_id = project._id
        else:
            project_id = project
        role = cls.query.get(
            name=name,
            project_id=project_id)
        return role

    @classmethod
    def by_display_name(cls, display_name, project=None):
        if project is None:
            project = c.project
        if hasattr(project, 'root_project'):
            project = project.root_project
        for n, dn in project.neighborhood.role_aliases.iteritems():
            if dn == display_name:
                name = n
                break
        else:
            name = display_name
        return cls.by_name(name, project)

    @classmethod
    def anonymous(cls, project=None):
        return cls.by_name('*anonymous', project)

    @classmethod
    def authenticated(cls, project=None):
        return cls.by_name('*authenticated', project)

    @classmethod
    def upsert(cls, **kw):
        obj = cls.query.get(**kw)
        if obj is not None:
            return obj
        try:
            obj = cls(**kw)
            session(obj).insert_now(obj, state(obj))
        except pymongo.errors.DuplicateKeyError:
            session(obj).expunge(obj)
            obj = cls.query.get(**kw)
        return obj

    @property
    def special(self):
        if self.name:
            return '*' == self.name[0]
        if self.user_id:
            return True
        return False  # pragma no cover

    @property
    def user(self):
        if self.user_id is None and self.name and self.name != '*anonymous':
            return None
        return User.query.get(_id=self.user_id)

    @property
    def settings_href(self):
        if self.name in ('Admin', 'Developer', 'Member'):
            return None
        return self.project.url() + 'admin/groups/' + str(self._id) + '/'

    def parent_roles(self):
        """Find roles that inherit from this role"""
        return self.query.find({'roles': self._id}).all()

    def children(self):
        """
        Truly find the roles that inherit from this, including special users

        """
        if self.name == '*anonymous':
            return self.__class__.query.find({
                'name': '*authenticated',
                'project_id': self.project_id
            })
        elif self.name == '*authenticated':
            return self.__class__.base_named(self.project)
        else:
            return self.__class__.query.find({
                'roles': self._id,
                'name': {'$ne': None}
            })

    @classmethod
    def base_named(cls, project=None):
        """Named roles that do not inherit from other roles"""
        if project is None:
            project = c.project
        return cls.query.find({
            'name': re.compile(r'^[^\*]'),
            'roles': [],
            'project_id': project._id
        })

    @classmethod
    def fundamental_fulfillers(cls, base_roles, func):
        """
        Determine the most encompassing roles that fulfill a given function
        from a set of base roles

        """
        accepted = []

        def recurse_fundamental(roles, accepted):
            next_roles = []
            for role in roles:
                if func(role):
                    accepted.append(role)
                else:
                    next_roles.extend(role.children().all())
            if next_roles:
                recurse_fundamental(next_roles, accepted)

        recurse_fundamental(base_roles, accepted)
        return accepted

    def all_children(self):
        for child in self.children():
            yield child
            for grandchild in child.all_children():
                yield grandchild

    def users_with_role(self):
        return self.query.find(dict(
            project_id=self.project_id,
            user_id={'$ne': None},
            roles=self._id)
        ).all()
