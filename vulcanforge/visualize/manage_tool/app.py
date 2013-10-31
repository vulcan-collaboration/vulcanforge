import logging
import cgi

from bson import ObjectId
import pymongo
from formencode import validators
from webob import exc
from pylons import tmpl_context as c, app_globals as g
from tg.controllers.util import redirect
from tg.decorators import expose, validate

from vulcanforge.common.app import Application
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import (
    require_post,
    validate_form
)
from vulcanforge.common.types import SitemapEntry
from vulcanforge.common.util import push_config
from vulcanforge.common.validators import MingValidator
from vulcanforge.visualize.model import VisualizerConfig
from vulcanforge.visualize.manage_tool.admin import VisualizerUploadForm
from vulcanforge.visualize.s3 import S3Visualizer


LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.visualize.manage_tool:templates/'


class ForgeVisualizeApp(Application):
    """The definitive Visualize App for VulcanForge"""
    __version__ = "0.1"
    searchable = False
    permissions = ['read', 'edit', 'admin']
    tool_label = "Visualizers"
    static_folder = 'Visualizers'
    default_mount_label = "Visualizers"
    default_mount_point = "visualize"
    default_root_page_name = u"Home"
    icons = {
        24: '{ep_name}/images/visualizers-icon_24.png',
        32: '{ep_name}/images/visualizers-icon_32.png',
        48: '{ep_name}/images/visualizers-icon_48.png'
    }
    default_acl = {
        'Admin': permissions,
        'Developer': ['read', 'edit']
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = VisualizerConfigController(self)

    @property
    def sitemap(self):
        menu_id = self.config.options.mount_label.title()
        with push_config(c, app=self):
            return [SitemapEntry(menu_id, '.')[self.sidebar_menu()]]

    def sidebar_menu(self):
        sidebar_menu = [SitemapEntry('Home', c.app.url)]
        return sidebar_menu


class VisualizerConfigController(BaseController):

    class Forms(BaseController.Forms):
        upload_form = VisualizerUploadForm(action="do_upload")

    def __init__(self, app):
        self.app = app

    def _check_security(self):
        g.security.require_access(self.app, 'read')

    @expose(TEMPLATE_DIR + 'manage.html')
    def index(self, **kw):
        c.upload_form = self.Forms.upload_form
        visualizers = VisualizerConfig.query.find({}).sort(
            'priority', pymongo.DESCENDING)
        return {
            'visualizers': visualizers,
            'is_admin': g.security.has_access(self.app, 'edit')
        }

    @expose()
    @validate({'visualizers': validators.UnicodeString(not_empty=True)})
    @require_post()
    def set_priority(self, visualizers=None):
        g.security.require_access(self.app, 'edit')
        ordered_ids = visualizers.split(',')
        num = len(ordered_ids)
        for n, vis_id in enumerate(ordered_ids):
            visualizer = VisualizerConfig.query.get(_id=ObjectId(vis_id))
            visualizer.priority = (num - n) * 10

    @expose()
    @validate({
        'visualizer': MingValidator(VisualizerConfig, not_empty=True),
        'active': validators.Bool(if_empty=True)
    })
    @require_post()
    def update(self, archive=None, visualizer=None, delete=None, active=True,
               **kw):
        g.security.require_access(self.app, 'edit')
        if delete == u'Delete':
            try:
                visualizer.delete_s3_keys()
            except Exception:
                LOG.exception(
                    'deleting s3 content %s on visualizer delete: %s',
                    visualizer.name)
            visualizer.delete()
        else:
            # extract and read archive
            if isinstance(archive, cgi.FieldStorage):
                visualizer.update_from_archive(archive.file)
            # set active state
            visualizer.active = active
        redirect('index')

    @expose()
    @validate_form("upload_form", error_handler=index)
    @require_post()
    def do_upload(self, archive=None, **kw):
        g.security.require_access(self.app, 'edit')
        if archive is None:
            raise exc.HTTPBadRequest('Must include an archive')

        S3Visualizer.new_from_archive(archive.file)
        redirect('index')
