from vulcanforge.visualize.base import BaseVisualizer
from vulcanforge.visualize.widgets import BaseArtifactDirect, BaseContentWidget


class SyntaxContent(BaseContentWidget):
    template = 'visualize/widgets/syntax.html'


class SyntaxVisualizer(BaseVisualizer):
    content_widget = SyntaxContent()
    default_options = {
        "name": "Syntax Visualizer",
        "mime_types": [
            '^text/',
            '^application/javascript',
            '^application/http',
            '^application/json',
            '^application/xml',
            '^application/xhtml\+xml',
            '^application/x-httpd-php',
            '^application/atom\+xml',
            '^application/atomcat\+xml',
            '^application/atomserv\+xml',
            '^application/vnd.mozilla.xul\+xml',
            '^application/vnd.wap.wbxml',
            '^application/x-info',
            '^application/x-latex'
        ],
        "extensions": None,
        "description": "Visualizes code and markup documents",
        "icon": "FILE_TEXT",
        "priority": -1
    }
