from paste.registry import Registry
from pylons import app_globals as g
from ew.core import widget_context, WidgetContext


def register_widget_context():
    """setup widget_context, if not done already"""
    try:
        widget_context.widget
    except TypeError:
        scheme = g.base_url.split(':', 1)[0]
        r = Registry()
        r.prepare()
        r.register(
            widget_context,
            WidgetContext(
                scheme=scheme,
                resource_manager=g.resource_manager))