import tg.decorators
from pylons import request

from vulcanforge.common.helpers import monkeypatch


def apply():
    @monkeypatch(tg, tg.decorators)
    def override_template(controller, template):
        """Copy-pasted patch to allow multiple colons in a template spec"""
        if hasattr(controller, 'decoration'):
            decoration = controller.decoration
        else:
            return
        if hasattr(decoration, 'engines'):
            engines = decoration.engines
        else:
            return

        for content_type, content_engine in engines.iteritems():
            template = template.split(':', 1)
            template.extend(content_engine[2:])
            try:
                override_mapping = request._override_mapping
            except AttributeError:
                override_mapping = request._override_mapping = {}
            override_mapping[controller.im_func] = {content_type: template}
