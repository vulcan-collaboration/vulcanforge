from urllib import unquote

from webob import exc
from pylons import app_globals as g, tmpl_context as c
from tg import expose, redirect
from tg.decorators import with_trailing_slash, without_trailing_slash

from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import add_cache_headers
from vulcanforge.common.helpers import really_unicode
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.model import Project
from vulcanforge.tools.wiki.model import Page

TEMPLATE_DIR = 'jinja:vulcanforge:common/templates/'


class NewForgeController(BaseController):

    @expose()
    @without_trailing_slash
    def markdown_to_html(self, markdown, neighborhood=None, project=None,
                         app=None):
        """Convert markdown to html."""
        if project is not None and project != 'None':
            if neighborhood is not None and neighborhood != 'None':
                n = Neighborhood.query.get(name=neighborhood)
                project = Project.query.get(
                    shortname=project, neighborhood_id=n._id
                )
            g.set_project(project)
            if app is not None and app != 'None':
                g.set_app(app)
        html = g.markdown_wiki.convert(markdown)
        return html

    @expose(TEMPLATE_DIR + 'markdown_syntax_fragment.html')
    def markdown_syntax(self):
        return dict()

    @expose()
    @with_trailing_slash
    def redirect(self, path, **kw):
        """Redirect to external sites."""
        redirect(path)

    @expose()
    def _lookup(self, page_title, *remainder):
        page_title = really_unicode(unquote(page_title))
        # try to find a matching page
        g.context_manager.set(g.site_admin_project, mount_point=u'static')
        page = Page.query.get(
            app_config_id=c.app.config._id, title=page_title
        )
        controller = ForgeStaticPage(page)
        return controller, remainder


class ForgeStaticPage(BaseController):
    def __init__(self, page):
        self.page = page

    @add_cache_headers(12 * 60 * 60)  # cache por un medio dia
    @expose(TEMPLATE_DIR + 'static_page.html')
    def index(self, **kw):
        if not self.page:
            raise exc.HTTPNotFound()
        return dict(page=self.page)
