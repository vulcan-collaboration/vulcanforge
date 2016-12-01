from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from cStringIO import StringIO

from vulcanforge.resources.widgets import JSLink, CSSLink, JSScript
from vulcanforge.visualize.base import BaseVisualizer
from vulcanforge.visualize.widgets import BaseContentWidget


class PDFContent(BaseContentWidget):
    template = 'visualize/widgets/pdf.html'

    def resources(self):
        # From super
        yield CSSLink('visualize/css/visualize.css')

        yield JSLink('js/lib/jquery/jquery.1.7.2.min.js', scope="forge")
        yield JSLink('js/lib/jquery/jquery-ui.1.10.3.js', scope="forge")
        yield JSLink('visualize/js/visualize.js', scope="forge")

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

    def text_content(self, artifact):
        input_file = StringIO(artifact.read())
        rsrcmgr = PDFResourceManager()
        retstr = StringIO()
        codec = 'utf-8'
        laparams = LAParams()
        device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        password = ""
        maxpages = 0
        caching = True
        pagenos=set()
        for page in PDFPage.get_pages(input_file, pagenos, maxpages=maxpages, password=password, caching=caching, check_extractable=True):
            interpreter.process_page(page)
        input_file.close()
        device.close()
        str = retstr.getvalue()
        retstr.close()
        return str

    def get_query_for_artifact(self, artifact, **kwargs):
        if hasattr(artifact, 'local_url'):
            query = self.get_query_for_url(artifact.local_url(), **kwargs)
        else:
            query = self.get_query_for_url(artifact.url(), **kwargs)
        query['refId'] = artifact.artifact_ref_id()
        return query
