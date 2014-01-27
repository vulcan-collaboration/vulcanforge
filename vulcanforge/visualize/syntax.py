from pylons import app_globals as g

from vulcanforge.common.util.diff import unified_diff
from vulcanforge.resources.widgets import Widget, JSLink, CSSLink
from vulcanforge.visualize.base import BaseVisualizer
from vulcanforge.visualize.widgets import BaseContentWidget, ArtifactDiff


class SyntaxContent(BaseContentWidget):
    template = 'visualize/widgets/syntax.html'

    def resources(self):
        for r in super(SyntaxContent, self).resources():
            yield r
        yield CSSLink('js/lib/google-code-prettify/prettify.css', scope="page")
        yield CSSLink('visualize/syntax/syntaxvis.css', scope="page")
        yield JSLink('js/vf.js', scope="page")
        yield JSLink('js/lib/google-code-prettify/prettify.js', scope="page")


class SyntaxArtifactDiff(ArtifactDiff):
    template = 'visualize/widgets/diff_syntax.html'

    def display(self, value1, value2, visualizer, extra_params=None,
                filename1=None, filename2=None, **kwargs):
        if filename1 is None:
            filename1 = self.get_filename_from_value(value1)
        if filename2 is None:
            filename2 = self.get_filename_from_value(value2)
        diff_list = unified_diff(
            value1.read().split('\n'),
            value2.read().split('\n'),
            ('a' + value1.url()).encode('utf-8'),
            ('b' + value2.url()).encode('utf-8'))
        diff = g.highlight('\n'.join(diff_list), lexer='diff')
        return Widget.display(
            self, diff=diff, value1=value1, value2=value2, filename1=filename1,
            filename2=filename2, **kwargs)


class SyntaxVisualizer(BaseVisualizer):
    content_widget = SyntaxContent()
    artifact_diff_widget = SyntaxArtifactDiff()
    default_options = {
        "name": "Source",
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
        "icon": "FILE_TEXT"
    }
