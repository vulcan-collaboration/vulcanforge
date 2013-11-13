from pylons import app_globals as g

from vulcanforge.common.util.diff import unified_diff
from vulcanforge.resources.widgets import Widget
from vulcanforge.visualize.base import BaseVisualizer
from vulcanforge.visualize.widgets import BaseContentWidget


class SyntaxContent(BaseContentWidget):
    template = 'visualize/widgets/syntax.html'


class SyntaxArtifactDiff(Widget):
    template = 'visualize/widgets/diff_syntax.html'

    def display(self, value1, value2, visualizer, extra_params=None, **kwargs):
        diff_list = unified_diff(
            value1.read().split('\n'),
            value2.read().split('\n'),
            ('a' + value1.url()).encode('utf-8'),
            ('b' + value2.url()).encode('utf-8'))
        diff = g.highlight('\n'.join(diff_list), lexer='diff')
        return super(SyntaxArtifactDiff, self).display(
            diff=diff, value1=value1, value2=value2, **kwargs)


class SyntaxVisualizer(BaseVisualizer):
    content_widget = SyntaxContent()
    artifact_diff_widget = SyntaxArtifactDiff()
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
        "extensions": ['*'],
        "description": "Visualizes code and markup documents",
        "icon": "FILE_TEXT",
        "priority": -1
    }
