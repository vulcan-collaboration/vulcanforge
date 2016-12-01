from vulcanforge.resources.widgets import JSLink
from vulcanforge.visualize.base import BaseVisualizer
from vulcanforge.visualize.widgets import BaseContentWidget


class MarkdownContent(BaseContentWidget):
    template = 'visualize/widgets/markdown.html'

    def resources(self):
        for r in super(MarkdownContent, self).resources():
            yield r
        yield JSLink('visualize/markdown.js')


class MarkdownVisualizer(BaseVisualizer):
    content_widget = MarkdownContent()
    default_options = {
        "name": "Markdown Visualizer",
        "mime_types": ['^text/markdown'],
        "extensions": ['*'],
        "description": "Visualizes markdown files",
        "icon": "FILE_TEXT"
    }