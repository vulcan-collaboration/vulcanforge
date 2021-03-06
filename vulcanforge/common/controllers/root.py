# -*- coding: utf-8 -*-
"""Main VFTheme Controller"""
import logging

from pylons import tmpl_context as c, app_globals as g
import tg
from tg import expose, request, override_template
from tg.decorators import with_trailing_slash
from tg.flash import TGFlash
from vulcanforge.auth.model import User

from vulcanforge.common.controllers.base import WsgiDispatchController
from vulcanforge.artifact.controllers import ArtifactReferenceController
from vulcanforge.auth.controllers import AuthController, UserDiscoverController
from vulcanforge.common.controllers.debugutil import DebugUtilRootController
from vulcanforge.common.controllers.error import ErrorController
from vulcanforge.common.controllers.rest import (
    RestController,
    WebServiceRestController)
from vulcanforge.common.controllers.static import (
    NewForgeController,
    ForgeStaticController
)
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.common.util import alpha_cmp_factory
from vulcanforge.common.util.debug import profile_setup_request
from vulcanforge.dashboard.controllers import DashboardController
from vulcanforge.exchange.controllers.root import GlobalExchangeController
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.controllers import ProjectBrowseController
from vulcanforge.project.model import ProjectCategory, Project
from vulcanforge.project.widgets import ProjectListWidget
from vulcanforge.s3.controllers import S3ProxyController
from vulcanforge.search.controllers import (
    AutocompleteController,
    SearchController
)
from vulcanforge.visualize.controllers import VisualizerRootController


__all__ = ['ForgeRootController']

LOG = logging.getLogger(__name__)
TGFlash.static_template = '''
    $('#messages').notify('%(message)s', {status: '%(status)s'});
'''
TEMPLATE_DIR = 'jinja:vulcanforge:common/templates/'


class ForgeRootController(WsgiDispatchController):
    """
    The root controller for VulcanForge.

    All the other controllers and WSGI applications should be mounted on this
    controller. For example::

        panel = ControlPanelController()
        another_app = AnotherWSGIApplication()

    Keep in mind that WSGI applications shouldn't be mounted directly: They
    must be wrapped around with :class:`tg.controllers.WSGIAppController`.

    """
    # controllers
    artifact_ref = ArtifactReferenceController()
    auth = AuthController()
    autocomplete = AutocompleteController()
    dashboard = DashboardController()
    users = UserDiscoverController()
    error = ErrorController()
    exchange = GlobalExchangeController()
    nf = NewForgeController()
    forge_global = ForgeStaticController()
    rest = RestController()
    search = SearchController()
    s3_proxy = S3ProxyController()
    visualize = VisualizerRootController()
    webs = WebServiceRestController()

    # widgets
    class Widgets(WsgiDispatchController.Widgets):
        project_list = ProjectListWidget()

    _counters = {
        'projects': {
            'cls': Project,
            'label': 'Projects'
        },
        'users': {
            'cls': User,
            'label': 'Users'
        }
    }

    def __init__(self):
        if g.cache is not None and g.cache.exists('fail_whale'):
            pass
        else:
            for n in Neighborhood.query.find():
                if n.url_prefix.startswith('//'):
                    continue
                n.bind_controller(self)
            self.browse = ProjectBrowseController()

            if not g.production_mode:
                self._debug_util_ = DebugUtilRootController()

        super(ForgeRootController, self).__init__()

    def _set_user_context(self):
        if g.cache is not None and g.cache.exists('fail_whale'):
            pass
        else:
            c.user = g.auth_provider.authenticate_request()
            assert c.user is not None, \
                'c.user should always be at least User.anonymous()'

    def _setup_request(self):
        c.neighborhood = c.project = c.app = None
        c.memoize_cache = {}
        self._set_user_context()

        if g.cache is not None and g.cache.exists('fail_whale'):
            pass
        else:
            if g.visibility_mode_handler.is_enabled:
                g.visibility_mode_handler.check_visibility(c.user, request)

        if g.profile_middleware:
            profile_setup_request()

    def _cleanup_request(self):
        pass

    @expose('front.html')
    @with_trailing_slash
    def index(self, **kwargs):
        if g.cache is not None and g.cache.exists('fail_whale'):
            if tg.config.get('templates.fail_whale'):
                override_template(self.index, tg.config.get('templates.fail_whale'))
                return {}

        root_redirect = tg.config.get('root_redirect', None)
        if root_redirect is not None:
            return tg.redirect(root_redirect)
        if c.user.is_anonymous:
            return self._anonymous_index(**kwargs)
        return self._authenticated_index(**kwargs)

    def _authenticated_index(self, **kwargs):
        return tg.redirect(c.user.landing_url())

    def _anonymous_index(self, **kwargs):
        """Handle the front-page.

        TODO:
        - decide how to limit "featured" projects
            - featured flag -or- N most active
        - replace Mongo queries with SOLR queries

        """
        c.project_list = self.Widgets.project_list

        neighborhoods = Neighborhood.query.find(dict(allow_browse=True))

        homepage_project_list_limit = int(
            tg.config.get('homepage_project_list_limit', 10)
        )

        params = {
            "q": ' AND '.join((
                'type_s:(Project)',
                'is_root_b:(true)',
                'neighborhood_id_s:(%s)' % ' OR '.join(
                    str(n._id) for n in neighborhoods),
                'deleted_b:(false)',
                'NOT shortname_s:("--init--")'
            )),
            "fq": ' AND '.join((
                'read_roles:("%s")' % '" OR "'.join(
                    g.security.get_user_read_roles()),
            )),
            "start": 0,
            "rows": homepage_project_list_limit,
            "sort": "activity_i desc"
        }
        results = g.search(**params)

        if results is None:
            projects = []
        else:
            projects = results.docs
            projects.sort(alpha_cmp_factory('name_s'))
            projects.reverse()

        categories = ProjectCategory.query.find({
            'parent_id': None}).sort('name').all()

        c.custom_sidebar_menu = [
            SitemapEntry(
                cat.label, '/browse/' + cat.name, className='nav_child')
            for cat in categories
        ]
        is_demo_mode = (tg.config.get('demo_mode', 'disabled') == 'enabled')

        counts = dict(
            [(spec['label'], format(spec['cls'].active_count(), ',d'))
             for k, spec in self._counters.items()]
        )

        return dict(is_demo_mode=is_demo_mode,
                    projects=projects,
                    title="All Projects",
                    counts=counts)
