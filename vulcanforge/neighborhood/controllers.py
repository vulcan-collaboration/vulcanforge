import logging
import re
from urllib import unquote

import ming.odm
from webob import exc
from formencode import Invalid
from pylons import tmpl_context as c, app_globals as g
from tg import redirect, flash, override_template
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
from vulcanforge.common.types import SitemapEntry
from vulcanforge.common.util import re_path_portion
from vulcanforge.common.util.antispam import AntiSpam
from vulcanforge.common.widgets.util import PageSize, PageList
from vulcanforge.auth.model import User
from vulcanforge.auth.tasks import remove_workspacetabs
from vulcanforge.neighborhood.marketplace.controllers import (
    NeighborhoodMarketplaceController)
from vulcanforge.project.validators import ProjectShortnameValidator
from vulcanforge.project.model import Project
from vulcanforge.project.controllers import (
    ProjectController,
    ProjectBrowseController
)
from vulcanforge.project.widgets import ProjectListWidget

from .model import Neighborhood, NeighborhoodFile
from .exceptions import RegistrationError
from .widgets import NeighborhoodAddProjectForm, NeighborhoodAdminOverview

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:neighborhood/templates/'


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

    project_shortname_validator = ProjectShortnameValidator()

    class Forms(BaseTGController.Forms):
        add_project = NeighborhoodAddProjectForm()

    _admin_controller_cls = NeighborhoodAdminController

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
                pname = self.project_shortname_validator.validate_name(pname)
            except Invalid:
                raise exc.HTTPNotFound, pname
        project = Project.query.get(
            neighborhood_id=self.neighborhood._id,
            shortname=self.prefix + pname)
        if project is None:
            project = self.neighborhood.neighborhood_project
            c.project = project
            return ProjectController()._lookup(pname, *remainder)

        c.project = project
        if project is None or (project.deleted and
                               not g.security.has_access(c.project, 'update')):
            raise exc.HTTPNotFound, pname
        if project.neighborhood.name != self.neighborhood_name:
            redirect(project.url())
        return ProjectController(), remainder

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
        if not self.neighborhood.user_can_register():
            flash("You are already a member of a team", "error")
            redirect(self.neighborhood.url())
        if self.neighborhood.kind == "competition":
            title = "Form a Team"
        else:
            title = "Create a Project"
        c.add_project = self.Forms.add_project
        for checkbox in ['Wiki', 'Tickets', 'Discussion', 'Components']:
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
        validator = self.Forms.add_project.fields.project_unixname.validator
        try:
            validator.to_python(project_name)
        except Invalid as e:
            msg = e.msg
        return dict(message=msg)

    @vardec
    @expose()
    @AntiSpam.validate('Spambot protection engaged')
    @require_post()
    def register(self, **form_data):
        """Register a project on this neighborhood"""
        g.security.require_access(self.neighborhood, 'register')
        if not self.neighborhood.user_can_register():
            flash("You are already a member of a team", "error")
            redirect(self.neighborhood.url())

        # Validate the form. We cannot use the nifty tg decorator because the
        # form can be different depending on the neighborhood.
        form = self.Forms.add_project
        try:
            form_result = form.to_python(form_data)
        except Invalid, inv:
            c.form_errors = inv.unpack_errors()
            c.form_result = inv.value
            override_template(self.register, TEMPLATE_DIR + 'add_project.html')
            return self.add_project(**form_data)

        # expand the values
        project_name = h.really_unicode(
            form_result.pop('project_name', '')).encode('utf-8')
        project_description = h.really_unicode(
            form_result.pop('project_description', '')).encode('utf-8')
        project_unixname = h.really_unicode(
            form_result.pop('project_unixname', '')).encode('utf-8').lower()
        private_project = form_result.pop('private_project', None)
        neighborhood = self.neighborhood

        apps = []
        tool_info = {
            'Tickets': 'Manage',
            'Wiki': 'Docs',
            'Discussion': 'Forums'
        }
        for repo in ('Git', 'SVN', 'Hg'):
            tool_info[repo] = 'Repository'
        for i, tool in enumerate(form_result):
            if tool in tool_info:
                label, mp = tool_info[tool], tool_info[tool].lower()
            else:
                label, mp = tool, tool.lower()
            if form_result[tool]:
                apps.append((tool.lower(), mp, label))
        if apps:
            apps = [
                ('home', 'home', 'Home'),
                ('admin', 'admin', 'Admin')
            ] + apps

        # install the project
        try:
            c.project = neighborhood.register_project(
                project_unixname,
                project_name=project_name,
                private_project=private_project,
                apps=apps or None
            )
            if project_description:
                c.project.short_description = project_description
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
        return dict(projects=projects,
            title=title,
            text=None,
            neighborhood=self.neighborhood,
            sort=sort,
            limit=limit,
            page=page,
            count=count,
            hide_sidebar=self.hide_sidebar)


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
        p = Project.query.get(shortname=pid, deleted=False)
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
        p = Project.query.get(
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
        project = Project.query.get(
            shortname=name,
            neighborhood_id=self._neighborhood._id,
            deleted=False
        )
        if project:
            c.project = project
        else:
            c.project = self._neighborhood.neighborhood_project
            remainder = [name] + list(remainder)

        return ProjectRestController(), remainder
