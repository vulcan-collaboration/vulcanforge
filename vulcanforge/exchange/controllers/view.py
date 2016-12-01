import logging

from webob import exc
from pylons import app_globals as g, tmpl_context as c
from tg import expose, validate

from vulcanforge.common.controllers import BaseController
from vulcanforge.common.validators import ObjectIdValidator
from vulcanforge.exchange.widgets import NodeMenuBar

LOG = logging.getLogger(__name__)


class ArtifactViewController(BaseController):
    """Default Controller to View Artifacts within the Exchange"""

    class Widgets(BaseController.Widgets):
        menu_bar = NodeMenuBar()

    @expose('exchange/view.html')
    @validate({"node_id": ObjectIdValidator()})
    def index(self, node_id, **kwargs):
        node = c.artifact_config['node'].query.get(_id=node_id)
        if not node:
            raise exc.HTTPNotFound
        g.security.require_access(node, 'read')

        c.renderer = c.artifact_config["renderer"](is_exchange=True)
        c.menu_bar = self.Widgets.menu_bar

        node.artifact.view_hook()

        return {
            "node": node,
            "xcng_name": c.exchange.config["name"]
        }

    @expose('exchange/history.html')
    @validate({"node_id": ObjectIdValidator()})
    def history(self, node_id, **kwargs):
        node = c.artifact_config['node'].query.get(_id=node_id)
        if not node:
            raise exc.HTTPNotFound
        g.security.require_access(node, 'read')

        c.menu_bar = self.Widgets.menu_bar
        versions = node.history()

        return {
            "versions": versions,
            "node": node,
            "xcng_name": c.exchange.config["name"]
        }
