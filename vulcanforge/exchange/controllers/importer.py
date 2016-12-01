import logging
import os

from webob import exc
from pylons import tmpl_context as c, app_globals as g
from tg import expose, validate, request, flash, redirect

from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import (
    require_post,
    validate_form
)
from vulcanforge.common.validators import ObjectIdValidator
from vulcanforge.exchange.widgets import NodeMenuBar
from vulcanforge.exchange.widgets.importer import ArtifactImportForm

LOG = logging.getLogger(__name__)


class ImportController(BaseController):
    """
    Manages importing artifacts from the exchange into a local tool. This
    controller can be overidden at the artifact level by adding a
    "import_controller" key to the artifacts property of the tool.

    """
    class Widgets(BaseController.Widgets):
        menu_bar = NodeMenuBar()

    class Forms(BaseController.Forms):
        import_form = ArtifactImportForm()

    @expose('exchange/importer.html')
    @validate({"node_id": ObjectIdValidator()})
    def index(self, node_id, **kwargs):
        node = c.artifact_config['node'].query.get(_id=node_id)
        if not node:
            raise exc.HTTPNotFound
        if not c.artifact_config.get("importer"):
            raise exc.HTTPNotFound
        g.security.require_access(node, 'import')
        import_action = os.path.join(request.path_info, 'do_import')
        c.menu_bar = self.Widgets.menu_bar
        c.import_form = self.Forms.import_form

        value = {
            "node_id": node._id
        }

        return {
            "value": value,
            "xcng_name": c.exchange.config["name"],
            "import_action": import_action,
            "node": node
        }

    @expose()
    @require_post()
    @validate_form('import_form', error_handler=index)
    def do_import(self, node_id=None, app_config_id=None, **kwargs):
        node = c.artifact_config['node'].query.get(_id=node_id)
        if not node:
            raise exc.HTTPNotFound
        g.security.require_access(node, 'import')

        with g.context_manager.push(app_config_id=app_config_id):
            g.security.require_access(c.app, 'write')
            importer = c.artifact_config.get("importer")(node.artifact)
            if not importer:
                raise exc.HTTPNotFound
            new_artifact = importer.do_import()
            flash("Artifact imported successfully", "success")
            redirect(new_artifact.url())
