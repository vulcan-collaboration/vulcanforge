import logging
from urllib import unquote
from itertools import islice, chain

from webob import exc
from formencode import Invalid, validators
from pylons import app_globals as g, tmpl_context as c
from paste.deploy.converters import asint
from tg import request, redirect, response
from tg.decorators import (
    expose,
    without_trailing_slash,
    with_trailing_slash,
    validate
)

from vulcanforge.common.controllers.base import BaseController
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.common.widgets.util import PageList, PageSize
from vulcanforge.common.validators import DateTimeConverter
from vulcanforge.auth.model import User, AppVisit
from vulcanforge.artifact.model import Feed, LogEntry
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.validators import MOUNTPOINT_VALIDATOR
from .widgets import ProjectListWidget
from .model import ProjectCategory

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:project/templates/'


class ProjectController(BaseController):

    mountpoint_validator = MOUNTPOINT_VALIDATOR

    def __init__(self):
        setattr(self, 'feed.rss', self.feed)
        setattr(self, 'feed.atom', self.feed)
        setattr(self, '_nav.json', self._nav)
        super(ProjectController, self).__init__()

    @expose('json:')
    def _nav(self):
        return dict(
            menu=[dict(name=s.label, url=s.url, icon=s.ui_icon)
                  for s in c.project.sitemap()]
        )

    @expose()
    def _lookup(self, name, *remainder):
        name = unquote(name)
        try:
            self.mountpoint_validator.validate_name(name)
        except Invalid:
            raise exc.HTTPNotFound, name
        app = c.project.app_instance(name)
        if app is None:
            raise exc.HTTPNotFound, name
        c.app = app

        # Update user's last visit time
        if not c.user.is_anonymous:
            AppVisit.upsert(c.user._id, app.config._id, app.project._id)

        return app.root, remainder

    def _check_security(self):
        LogEntry.insert(access_denied_only=True)
        g.security.require_access(c.project, 'read')

    @expose()
    @with_trailing_slash
    def index(self, **kw):
        if c.project.private_project_of():
            redirect('profile/')
        mount = c.project.first_mount('read')
        if mount is not None:
            if 'ac' in mount:
                redirect(mount['ac'].options.mount_point + '/')
            elif 'sub' in mount:
                redirect(mount['sub'].url())
        elif c.project.app_instance('profile'):
            redirect('profile/')
        else:
            redirect(c.project.app_configs[0].options.mount_point + '/')

    @expose(TEMPLATE_DIR + 'sitemap.html')
    @without_trailing_slash
    def sitemap(self):  # pragma no cover
        raise NotImplementedError('sitemap')

    @without_trailing_slash
    @expose()
    @validate(dict(
        since=DateTimeConverter(if_empty=None, if_invalid=None),
        until=DateTimeConverter(if_empty=None, if_invalid=None),
        page=validators.Int(if_empty=None),
        limit=validators.Int(if_empty=None)))
    def feed(self, since=None, until=None, page=None, limit=None):
        if request.environ['PATH_INFO'].endswith('.atom'):
            feed_type = 'atom'
        else:
            feed_type = 'rss'
        title = 'Recent changes to Project %s' % c.project.name
        feed = Feed.feed(
            dict(project_id=c.project._id),
            feed_type,
            title,
            c.project.url(),
            title,
            since, until, page, limit)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        return feed.writeString('utf-8')

    @expose(content_type="image/*")
    def icon(self):
        icon = c.project.icon
        if not icon:
            redirect(g.resource_manager.absurl('images/project_default.png'))
        return icon.serve()

    @expose(content_type="image/*")
    def app_icon(self, mount_point, size=32):
        size=asint(size)
        ac = c.project.app_config(mount_point)
        icon = ac.get_icon(size)
        if not icon:
            return redirect(ac.icon_url(size, skip_lookup=True))
        return icon.serve()

    @expose()
    def member_agreement(self):
        agreement = c.project.member_agreement
        if not agreement:
            raise exc.HTTPNotFound
        return agreement.serve()

    @expose()
    def user_icon(self):
        try:
            return self.icon()
        except exc.HTTPNotFound:
            pass

    @expose('json:')
    def user_search(self, term=''):
        #if len(term) < 3:
        #    raise exc.HTTPBadRequest('"term" param must be at least length 3')
        users = User.by_display_name(term)
        named_roles = g.security.RoleCache(
            g.security.credentials,
            g.security.credentials.project_roles(
                project_id=c.project.root_project._id).named
        )
        result = [[], []]
        for u in users:
            if u._id in named_roles.userids_that_reach:
                result[0].append(u)
            else:
                result[1].append(u)
        result = list(islice(chain(*result), 10))
        return dict(
            users=[dict(
                label='%s (%s)' % (u.get_pref('display_name'), u.username),
                value=u.username,
                id=u.username) for u in result]
        )


class ProjectBrowseController(BaseController):

    class Widgets(BaseController.Widgets):
        project_list = ProjectListWidget()
        page_list = PageList()
        page_size = PageSize()

    def __init__(self, category_name=None, parent_category=None):
        self.parent_category = parent_category
        self.nav_stub = '/browse/'
        self.additional_filters = {}
        if category_name:
            parent_id = parent_category and parent_category._id or None
            self.category = ProjectCategory.query.find(dict(
                name=category_name,
                parent_id=parent_id
            )).first()
            if not self.category:
                raise exc.HTTPNotFound, request.path
        else:
            self.category = None

    def _build_title(self):
        title = "All Projects"
        if self.category:
            title = self.category.label
            cat = self.category
            # introduced possible endless loops if category hierarchy is
            # invalid
            while cat.parent_category:
                cat = cat.parent_category
                title = "%s: %s" % (self.parent_category.label, title)
        return title

    def _build_nav(self):
        categories = ProjectCategory.query.find({
            'parent_id': None
        }).sort('name').all()
        nav = []
        for cat in categories:
            nav.append(SitemapEntry(
                cat.label,
                self.nav_stub + cat.name,
                className='nav_child'))
            if (self.category and self.category._id == cat._id
                and cat.subcategories)\
            or (self.parent_category and self.parent_category._id == cat._id):
                for subcat in cat.subcategories:
                    nav.append(SitemapEntry(
                        subcat.label,
                        self.nav_stub + cat.name + '/' + subcat.name,
                        className='nav_child2'))
        return nav

    def _find_projects(self, sort='alpha', limit=25, start=0,
                       neighborhoods=None, **kw):
        if neighborhoods is None:
            neighborhoods = Neighborhood.query.find(dict(allow_browse=True))
        params = dict(
            q="deleted_b:(false) AND type_s:Project",
            fq=[
                'read_roles:("%s")' % '" OR "'.join(
                    g.security.get_user_read_roles()),
                'neighborhood_id_s:(%s)' % ' OR '.join(
                    [str(n._id) for n in neighborhoods])
            ],
            start=start,
            rows=limit
        )
        if self.additional_filters:
            LOG.warn('Additional Filters specified in project browser, '
                     'currently no support for this')

        if self.category:
            ids = [self.category._id]
            # warning! this is written with the assumption that categories
            # are only two levels deep like the existing site
            if self.category.subcategories:
                ids = ids + [cat._id for cat in self.category.subcategories]
            params['fq'].append('category_id_s:(%s)' % ' OR '.join(
                map(str, ids)))

        if sort == 'alpha':
            params['sort'] = 'name_s asc'
        else:
            params['sort'] = 'last_updated_dt desc'

        results = g.search(**params)
        if results is None:
            count = 0
            projects = []
        else:
            count = results.hits
            projects = results.docs

        return projects, count

    @expose()
    def _lookup(self, category_name, *remainder):
        controller = ProjectBrowseController(
            category_name=category_name,
            parent_category=self.category)
        return controller, remainder

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'project_list.html')
    def index(self, sort='alpha', limit=25, page=0, **kw):
        c.project_list = self.Widgets.project_list
        c.page_size = self.Widgets.page_size
        c.page_list = self.Widgets.page_list
        limit, page, start = g.handle_paging(limit, page)
        projects, count = self._find_projects(sort, limit, start)
        title = self._build_title()
        c.custom_sidebar_menu = self._build_nav()
        return {'projects': projects, 'title': title, 'text': None,
                'limit': limit, 'count': count, 'page': page}
