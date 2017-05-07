import logging
import re
import simplejson
from urllib import unquote

import ming.odm
from ming.odm import ThreadLocalODMSession
from ming.odm import state, session
from webob import exc
from formencode import Invalid
from paste.deploy.converters import asbool
from pylons import tmpl_context as c, app_globals as g
from tg import config, redirect, flash, override_template
from tg.decorators import expose, without_trailing_slash, with_trailing_slash

from vulcanforge.common.controllers.base import (
    BaseTGController,
    BaseController
)
from vulcanforge.common.controllers.decorators import (
    vardec,
    require_post,
    validate_form
)
from vulcanforge.common import helpers as h
from vulcanforge.common.controllers.rest import ProjectRestController
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.common.util import re_path_portion
from vulcanforge.common.widgets.util import PageSize, PageList
from vulcanforge.auth.model import User
from vulcanforge.auth.tasks import remove_workspacetabs
from vulcanforge.neighborhood.marketplace.controllers import (
    NeighborhoodMarketplaceController)
from vulcanforge.project.validators import MOUNTPOINT_VALIDATOR
from vulcanforge.project.model import (
    ProjectRole,
    ProjectFile
)
from vulcanforge.project.model.membership import MembershipInvitation
from vulcanforge.project.controllers import (
    ProjectController,
    ProjectBrowseController
)
from vulcanforge.project.widgets import ProjectListWidget
from vulcanforge.common.tasks.index import add_global_objs

from .model import Neighborhood, NeighborhoodFile
from .exceptions import RegistrationError
from .widgets import NeighborhoodAddProjectForm, NeighborhoodAdminOverview

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:neighborhood/templates/'
ADMIN_INVITE = '''
Hello there!

{user} has invited you to administer Team {team} on {forge_name}.
Follow the link below to sign up!
'''
MEMBER_INVITE = '''
Hello there!

{user} has invited you to be a member of Team {team} on {forge_name}.
Follow the link below to sign up!
'''

class NeighborhoodAdminController(BaseController):

    class Forms(BaseController.Forms):
        neighborhood_admin_overview = NeighborhoodAdminOverview()

    def __init__(self, neighborhood):
        self.neighborhood = neighborhood

    def _check_security(self):
        g.security.require_access(self.neighborhood, 'admin')

    def set_nav(self):
        project = self.neighborhood.neighborhood_project
        if project:
            c.project = project
            g.set_app('admin')
        else:
            admin_url = self.neighborhood.url() + '_admin/'
            c.custom_sidebar_menu = [
                SitemapEntry(
                    'Overview',
                    admin_url + 'overview',
                    className='nav_child'
                ),
                ]

    @with_trailing_slash
    @expose()
    def index(self, **kw):
        redirect('overview')

    def _overview_defaults(self):
        hood = self.neighborhood
        defaults = {
            'name': hood.name,
            'homepage': hood.homepage,
            'allow_browse': hood.allow_browse,
            'enable_marketplace': hood.enable_marketplace,
            'project_registration_enabled': hood.project_registration_enabled,
            'project_template': hood.project_template,
            'icon_img': '<img src="{}" alt="{} Icon"/>'.format(
                hood.icon_url(),
                hood.name
            ),
            'icon': '',
            'moderate_deletion': hood.moderate_deletion,
            'delete_moderator': hood.delete_moderator,
            'can_grant_anonymous': hood.can_grant_anonymous,
            'can_register_users': hood.can_register_users,
            }
        return defaults

    @without_trailing_slash
    @expose('jinja:vulcanforge:common/templates/form/generic_form.html')
    def overview(self, **kwargs):
        self.set_nav()
        c.form = self.Forms.neighborhood_admin_overview
        title = "{} Overview".format(self.neighborhood.name)
        return {
            'page_title': title,
            'page_header': title,
            'form_display_params': {
                'action': 'update',
                'value': self._overview_defaults(),
                'links': [
                    {
                        'label': 'cancel',
                        'href': self.neighborhood.url(),
                    },
                ],
            },
        }

    def _process_overview(self, name=None, homepage=None,
                          project_template=None, icon=None,
                          moderate_deletion=None, delete_moderator=None, **kw):
        hood = self.neighborhood
        hood.name = name
        hood.homepage = homepage
        hood.project_template = project_template
        hood.allow_browse = kw.get('allow_browse')
        hood.can_grant_anonymous = kw.get('can_grant_anonymous')
        hood.can_register_users = kw.get('can_register_users')
        enable_marketplace = kw.get('enable_marketplace')
        if hood.enable_marketplace and not enable_marketplace:
            remove_workspacetabs.post('^{}home/market/'.format(
                re.escape(hood.url())
            ))
        hood.enable_marketplace = enable_marketplace
        hood.project_registration_enabled = kw.get(
            'project_registration_enabled')
        hood.moderate_deletion = moderate_deletion
        delete_moderator = User.by_username(delete_moderator)
        hood.delete_moderator_id = getattr(delete_moderator, '_id', None)
        if icon is not None and icon != '':
            if hood.icon:
                hood.icon.delete()
            NeighborhoodFile.save_image(
                icon.filename, icon.file, content_type=icon.type,
                square=True, thumbnail_size=(48, 48),
                thumbnail_meta=dict(neighborhood_id=hood._id, category="icon"))

    @vardec
    @expose()
    @require_post()
    @validate_form("neighborhood_admin_overview", error_handler=overview)
    def update(self, **kw):
        self._process_overview(**kw)
        flash("Changes saved", 'success')
        redirect('overview')


class NeighborhoodController(BaseTGController):
    """Manages a neighborhood of projects."""

    mountpoint_validator = MOUNTPOINT_VALIDATOR

    class Forms(BaseTGController.Forms):
        add_project = NeighborhoodAddProjectForm()

    _admin_controller_cls = NeighborhoodAdminController
    _project_controller_cls = ProjectController

    def __init__(self, neighborhood_name, prefix=''):
        self.neighborhood_name = neighborhood_name
        self.neighborhood = Neighborhood.query.get(name=self.neighborhood_name)
        self.prefix = prefix
        self._moderate = NeighborhoodModerateController(self.neighborhood)
        if self.neighborhood.enable_marketplace:
            self._market = NeighborhoodMarketplaceController(self.neighborhood)
        self._admin = self._admin_controller_cls(self.neighborhood)
        if self.neighborhood.allow_browse:
            self.browse = NeighborhoodProjectBrowseController(
                neighborhood=self.neighborhood)

    def _dispatch(self, state, remainder):
        c.neighborhood = self.neighborhood
        return super(NeighborhoodController, self)._dispatch(state, remainder)

    def _check_security(self):
        g.security.require_access(self.neighborhood, 'read')

    @expose()
    def _lookup(self, pname=None, *remainder):
        if pname is None:
            pname = '--init--'
        else:
            pname = unquote(pname)
            try:
                pname = self.mountpoint_validator.validate_name(pname)
            except Invalid:
                raise exc.HTTPNotFound, pname
        project = self.neighborhood.project_cls.query_get(
            neighborhood_id=self.neighborhood._id,
            shortname=self.prefix + pname)
        if project is None:
            project = self.neighborhood.neighborhood_project
            c.project = project
            return self._project_controller_cls()._lookup(pname, *remainder)

        c.project = project
        if project is None or (project.deleted and
                               not g.security.has_access(c.project, 'write')):
            raise exc.HTTPNotFound, pname
        if project.neighborhood.name != self.neighborhood_name:
            redirect(project.url())
        return self._project_controller_cls(), remainder

    @expose()
    def index(self):
        if self.neighborhood.redirect:
            return redirect(self.neighborhood.redirect)
        c.project = self.neighborhood.neighborhood_project
        return redirect(c.project.first_mount()['ac'].url())

    @expose(TEMPLATE_DIR + 'add_project.html')
    @without_trailing_slash
    def add_project(self, **form_data):
        g.security.require_access(self.neighborhood, 'register')
        title = "Create a {}".format(self.neighborhood.project_cls.type_label)
        c.add_project = self.Forms.add_project
        for checkbox in ['Wiki', 'Tickets', 'Discussion', 'Downloads']:
            form_data.setdefault(checkbox, True)
        return dict(
            neighborhood=self.neighborhood,
            title=title,
            form_data=form_data
        )

    @expose('json:')
    def suggest_name(self, project_name=None):
        new_name = re.sub("[^A-Za-z0-9]", "", project_name).lower()
        result = {
            'suggested_name': new_name
        }
        result.update(self.check_name(new_name))
        return result

    @expose('json:')
    def check_name(self, project_name=None):
        msg = False
        name_field = self.Forms.add_project.fields_dict['project_unixname']
        validator = name_field.validator
        try:
            validator.to_python(project_name)
        except Invalid as e:
            msg = e.msg
        return dict(message=msg)

    def _parse_add_project_data(self, form_data):
        # expand the values
        project_name = h.really_unicode(
            form_data.pop('project_name', '')).encode('utf-8')
        project_description = h.really_unicode(
            form_data.pop('project_description', '')).encode('utf-8')
        project_unixname = h.really_unicode(
            form_data.pop('project_unixname', '')).encode('utf-8').lower()
        private_project = form_data.pop('private_project', None)

        tool_options = form_data.pop('tool_options', None)

        tool_info = {
            'Tickets': 'Manage',
            'Wiki': 'Docs',
            'Discussion': 'Forums'
        }
        repo_kind_map = {
            'Git': 'Git',
            'Subversion': 'SVN'
        }
        has_repo = form_data.pop('Repository', False)
        repo_kind_value = form_data.pop('RepositoryKind', None)
        if has_repo:
            repo_kind = repo_kind_map.get(repo_kind_value, None)
            if repo_kind:
                tool_info[repo_kind] = 'Repository'
                form_data[repo_kind] = True

        apps = []
        for tool in form_data:
            if form_data[tool]:
                if tool in tool_info:
                    label, mp = tool_info[tool], tool_info[tool].lower()
                else:
                    label, mp = tool, tool.lower()
                apps.append((tool.lower(), mp, label))
        if apps:
            apps = [
                ('home', 'home', 'Home'),
                ('admin', 'admin', 'Admin'),
                ('chat', 'chat', 'Chat'),
            ] + apps
        else:
            apps = None  # install default

        return project_unixname, {
            "project_name": project_name,
            "private_project": private_project,
            "short_description": project_description,
            "apps": apps,
            "tool_options": tool_options
        }

    @vardec
    @expose()
    @validate_form('add_project', error_handler=add_project)
    @require_post()
    def register(self, **form_data):
        """Register a project on this neighborhood"""
        g.security.require_access(self.neighborhood, 'register')
        shortname, reg_kwargs = self._parse_add_project_data(form_data)

        # install the project
        try:
            c.project = self.neighborhood.register_project(
                shortname, **reg_kwargs)
        except RegistrationError:
            redirect_to = self.neighborhood.url()
            ming.odm.odmsession.ThreadLocalODMSession.close_all()
            flash("You do not have permission to register", "error")
        else:
            redirect_to = c.project.script_name + 'home/'
            ming.odm.odmsession.ThreadLocalODMSession.flush_all()
            flash('Welcome to your new project!')

        redirect(redirect_to)

    @expose()
    def icon(self):
        icon = self.neighborhood.icon
        if not icon:
            raise exc.HTTPNotFound
        return icon.serve()

    @expose(content_type="image/*")
    def app_icon(self, mount_point):
        ac = self.neighborhood.neighborhood_project.app_config(mount_point)
        icon = ac.get_icon(32)
        if not icon:
            return redirect(ac.icon_url(32, skip_lookup=True))
        return icon.serve()

    @expose('json')
    def existing_projects(self):
        q = {'deleted': False,
             'neighborhood_id': self.neighborhood._id}
        project_cls = self.neighborhood.project_cls
        return {x.name: x.shortname for x in project_cls.query_find(q)
                if x.is_real() and g.security.has_access(x, 'read')}

    @expose('json')
    def team_exists(self, name):
        q = {'name': name,
             'neighborhood_id': self.neighborhood._id}
        project_cls = self.neighborhood.project_cls
        pc = project_cls.query_find(q)
        return {"found": pc.count() > 0}

    @expose('json')
    def existing_users(self):
        q = {'disabled': False}
        public_users = asbool(config.get('all_users_public', False))
        if not public_users:
            q.update({'public': True})
        return {x.display_name: {'username': x.username,
                                 'email': x.get_email_address()}
                for x in User.query.find(q) if x.is_real_user()}

    @require_post()
    @expose('json')
    def do_create_team(self, name, summary, parent=None, private=False,
                       icon=None, invitation_msg="", invitees="", **kw):
        g.security.require_access(c.neighborhood, 'register')
        # name
        name_regex = re.compile("^[A-Za-z]+[A-Za-z0-9 -]*$")
        mo = name_regex.match(name)
        if not mo:
            return {"status": "error", "reason": "Invalid team name"}
        else:
            name = name.encode('utf-8')
        # generate shortname and ensure uniqueness
        shortname = re.sub("[^A-Za-z0-9]", "", name).lower()
        project_cls = self.neighborhood.project_cls
        i = 1
        while True:
            if project_cls.by_shortname(shortname):
                i += 1
                shortname = shortname + unicode(i)
            else:
                break
        # team creation
        try:
            project = c.neighborhood.register_project(
                shortname,
                project_name=name,
                short_description=summary.encode('utf-8'),
                private_project=True if private else False,
                apps=None
            )
        except RegistrationError:
            ThreadLocalODMSession.close_all()
            return {"status": "error", "reason": "Team creation failed"}

        # team icon
        if icon is not None:
            if project.icon:
                ProjectFile.remove(dict(
                    project_id=project._id,
                    category='icon'
                ))
            ProjectFile.save_image(
                icon.filename,
                icon.file,
                content_type=icon.type,
                square=True,
                thumbnail_size=(64, 64),
                thumbnail_meta=dict(project_id=project._id, category='icon'))
            session(ProjectFile).flush()
            g.cache.redis.expire('navdata', 0)
            if state(project).status != "dirty":
                add_global_objs.post([project.index_id()])

        # invitations
        admin_text = ADMIN_INVITE.format(
            user=c.user.display_name,
            team=project.name,
            forge_name=config.get("forge_name", "The Forge"),
            url=g.url("/auth/register")
        )
        member_text = MEMBER_INVITE.format(
            user=c.user.display_name,
            team=project.name,
            forge_name=config.get("forge_name", "The Forge"),
            url=g.url("/auth/register")
        )
        if invitees:
            invited = simplejson.loads(invitees)
            if (type(invited) is list):
                itext = invitation_msg or "Please join my team."
                admin_role = ProjectRole.by_name('Admin', project)
                member_role = ProjectRole.by_name('Member', project)
                ac_id = project.home_ac._id
                with g.context_manager.push(app_config_id=ac_id):
                    c.project.notifications_disabled = False
                    for invitee in invited:
                        # check if email invitee is current user
                        if 'address' in invitee:
                            email = invitee['address']
                            user = User.by_email_address(email)
                            if user:
                                invitee['username'] = user.username
                        # issue invitation
                        admin = invitee.get('isAdmin', False)
                        role = admin_role if admin else member_role
                        if 'username' in invitee:
                            username = invitee['username']
                            user = User.by_username(username)
                            if user and user.username != c.user.username:
                                if admin:
                                    project.add_user(user, ['Admin'])
                                else:
                                    invite = MembershipInvitation.from_user(
                                        user, project=project, text=itext)
                                    invite.send()
                        elif 'address' in invitee:
                            email = invitee['address']
                            etext = admin_text if admin else member_text
                            invite = MembershipInvitation.from_email(
                                email, project=project, text=etext,
                                role_id=role._id)
                            invite.send()

        return {"status": "success"}

    @expose(content_type="image/*")
    def project_icon_url(self):
        redirect(g.resource_manager.absurl('images/project_default.png'))


class NeighborhoodProjectBrowseController(ProjectBrowseController):

    class Widgets(ProjectBrowseController.Widgets):
        project_list = ProjectListWidget()
        page_list = PageList()
        page_size = PageSize()

    def __init__(self, neighborhood=None, category_name=None,
                 parent_category=None, hide_sidebar=True):
        self.hide_sidebar = hide_sidebar
        self.neighborhood = neighborhood
        super(NeighborhoodProjectBrowseController, self).__init__(
            category_name=category_name,
            parent_category=parent_category
        )
        self.nav_stub = '%sbrowse/' % self.neighborhood.url()
        self.additional_filters = {'neighborhood_id': self.neighborhood._id}

    @expose()
    def _lookup(self, category_name, *remainder):
        category_name = unquote(category_name)
        return NeighborhoodProjectBrowseController(
            neighborhood=self.neighborhood, category_name=category_name,
            parent_category=self.category), remainder

    @expose(TEMPLATE_DIR + 'project_list.html')
    @without_trailing_slash
    def index(self, sort='alpha', limit=25, page=0, **kw):
        c.project_list = self.Widgets.project_list
        c.page_list = self.Widgets.page_list
        c.page_size = self.Widgets.page_size
        limit, page, start = g.handle_paging(limit, page)
        projects, count = self._find_projects(
            sort=sort, limit=limit, start=start,
            neighborhoods=[self.neighborhood]
        )
        title = self._build_title()
        c.custom_sidebar_menu = self._build_nav()
        return {'projects': projects, 'title': title, 'text': None,
                'neighborhood': self.neighborhood, 'sort': sort,
                'limit': limit, 'page': page, 'count': count,
                'hide_sidebar': self.hide_sidebar}


class NeighborhoodModerateController(object):

    def __init__(self, neighborhood):
        self.neighborhood = neighborhood

    def _check_security(self):
        g.security.require_access(self.neighborhood, 'admin')

    @expose(TEMPLATE_DIR + 'moderate.html')
    def index(self, **kw):
        return dict(neighborhood=self.neighborhood)

    @expose()
    @require_post()
    def invite(self, pid, invite=None, uninvite=None):
        project_cls = self.neighborhood.project_cls
        p = project_cls.query_get(shortname=pid, deleted=False)
        if p is None:
            flash("Can't find %s" % pid, 'error')
            redirect('.')
        if p.neighborhood == self.neighborhood:
            flash("%s is already in the neighborhood" % pid, 'error')
            redirect('.')
        if invite:
            if self.neighborhood._id in p.neighborhood_invitations:
                flash("%s is already invited" % pid, 'warning')
                redirect('.')
            p.neighborhood_invitations.append(self.neighborhood._id)
            flash('%s invited' % pid)
        elif uninvite:
            if self.neighborhood._id not in p.neighborhood_invitations:
                flash("%s is already uninvited" % pid, 'warning')
                redirect('.')
            p.neighborhood_invitations.remove(self.neighborhood._id)
            flash('%s uninvited' % pid)
        redirect('.')

    @expose()
    @require_post()
    def evict(self, pid):
        project_cls = self.neighborhood.project_cls
        p = project_cls.query_get(
            shortname=pid,
            neighborhood_id=self.neighborhood._id,
            deleted=False)
        if p is None:
            flash("%s is not in the neighborhood" % pid, 'error')
            redirect('.')
        if not p.is_root:
            flash("Cannot evict %s; it's a subproject" % pid, 'error')
            redirect('.')
        n = Neighborhood.query.get(name='Projects')
        p.neighborhood_id = n._id
        if self.neighborhood._id in p.neighborhood_invitations:
            p.neighborhood_invitations.remove(self.neighborhood._id)
        flash('%s evicted to Projects' % pid)
        redirect('.')


class NeighborhoodRestController(object):

    def __init__(self, neighborhood):
        self._neighborhood = neighborhood

    @expose()
    def _lookup(self, name, *remainder):
        if not re_path_portion.match(name):
            raise exc.HTTPNotFound, name
        name = self._neighborhood.shortname_prefix + name
        project_cls = self._neighborhood.project_cls
        project = project_cls.query_get(
            shortname=name,
            neighborhood_id=self._neighborhood._id
        )
        if project:
            c.project = project
        else:
            c.project = self._neighborhood.neighborhood_project
            remainder = [name] + list(remainder)

        return ProjectRestController(), remainder
