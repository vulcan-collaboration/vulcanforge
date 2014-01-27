from vulcanforge.resources.widgets import JSLink, CSSLink, JSScript
from vulcanforge.visualize.base import BaseVisualizer
from vulcanforge.visualize.widgets import BaseContentWidget


class PDFContent(BaseContentWidget):
    template = 'visualize/widgets/pdf.html'

    def resources(self):
        pdfbase = "visualize/pdf/"
        buildbase = pdfbase + "build/"
        webbase = pdfbase + "web/"
        yield JSLink(buildbase + "pdf.js")
        page_js_urls = [
            'compatibility.js',
            'debugger.js',
            'l10n.js',
            'viewer.js'
        ]
        for url in page_js_urls:
            yield JSLink(webbase + url)
        yield CSSLink(webbase + "viewer.css")
        worker_url = buildbase + "pdf.worker.js"
        worker_link = JSLink(worker_url)
        yield worker_link
        yield JSScript("PDFJS.workerSrc = '{}';".format(
            worker_link.manager.absurl(worker_url)
        ))


class PDFVisualizer(BaseVisualizer):
    content_widget = PDFContent()
    default_options = {
        "name": "PDF Visualizer",
        "mime_types": ['^application/pdf'],
        "icon": 'FILE_TEXT',
        "description": "Visualizes PDF files"
    }