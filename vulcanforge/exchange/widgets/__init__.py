import logging

from pylons import app_globals as g

from vulcanforge.resources.widgets import Widget, JSLink

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'exchange/widgets/'


class NodeMenuBar(Widget):
    template = TEMPLATE_DIR + 'node_menu_bar.html'
    defaults = dict(
        Widget.defaults,
        node=None
    )

    def resources(self):
        for r in super(NodeMenuBar, self).resources():
            yield r
        yield JSLink('exchange/js/node_menu_bar.js')

    def prepare_context(self, context):
        context = super(NodeMenuBar, self).prepare_context(context)
        context.update({
            'icon_button_widget': g.icon_button_widget
        })
        return context

    def display(self, node, **kw):
        has_write_access = g.security.has_access(node.artifact, 'publish')
        # has_import_access = g.security.has_access(node, 'import')
        has_import_access = False
        has_artifact_read = g.security.has_access(node.artifact, 'read')
        return super(NodeMenuBar, self).display(
            node=node,
            has_write_access=has_write_access,
            has_artifact_read=has_artifact_read,
            has_import_access=has_import_access,
            **kw
        )