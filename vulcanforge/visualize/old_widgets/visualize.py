import logging
import mimetypes
import ew
import urllib
import urlparse
import os
import random
import string
import re
from formencode.variabledecode import variable_decode

from pylons import request, response, app_globals as g
import tg
from vulcanforge.common.helpers import urlquote
from vulcanforge.common.util.diff import unified_diff
from vulcanforge.common.util.filesystem import import_object

from vulcanforge.resources.widgets import Widget, CSSLink, JSLink, JSScript
from vulcanforge.visualize.model import VisualizerConfig
from vulcanforge.visualize.util import (
    get_iframe_url,
    get_fs_url,
    url_iframe_json
)

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.visualize:templates/widgets/'


class NoResourceError(Exception):
    """Exception when No resource is defined"""
    pass


class DispatchWidget(Widget):
    """
    Base class for rendering a resource in a context based on its visualizer

    If visualizer associated with the file has a widget attribute, it looks
    for that key in its widgets attribute. Barring that, it looks for a
    "default" key.

    If no visualizers are associated with the url, it first looks for a
    "no_vis" key before defaulting to "default".

    """
    widgets = dict()

    def _get_widget(self, url=None, visualizers=None, visualizer=None):
        if visualizer is None:
            if visualizers is None:
                visualizers = VisualizerConfig.get_for_resource(url)
            if visualizers:
                visualizer = visualizers[0]
                widget = self.widgets.get(visualizer.widget)
            else:
                widget = self.widgets.get('no_vis')
        else:
            widget = self.widgets.get(visualizer.widget)
        if widget is None:
            widget = self.widgets['default']
        return widget, visualizers, visualizer

    def get_url(self, value):
        return value.url()

    def display(self, value=None, visualizers=None, visualizer=None, **kw):
        widget, visualizers, visualizer = self._get_widget(
            url=self.get_url(value),
            visualizers=visualizers,
            visualizer=visualizer
        )
        g.resource_manager.register(widget)
        return widget.display(
            value1=value, visualizer=visualizer, visualizers=visualizers, **kw
        )


## Widgets for rendering contents of visualized resource ##
class BaseContentWidget(Widget):
    """
    Base class for visualized resource

    This is generally contained within an iframe, which this widget does not
    render
    """

    def sanitize_value(self, value):
        return urllib.quote(value.replace('"', '\\"'), safe=':/?=&%')

    def display(self, value=None, **kw):
        if value:
            value = self.sanitize_value(value)
        return super(BaseContentWidget, self).display(value=value, **kw)


class ImageContent(BaseContentWidget):
    template = TEMPLATE_DIR + 'image.html'


class RetrieveContent(BaseContentWidget):  # pragma no cover
    """
    For files that are required server side, like the old syntax visualization

    """
    template = TEMPLATE_DIR + 'retrieve.html'
    js_template = '''
    $(document).ready(function(){
        var visContainer = $('#retrieveVis');
        visContainer.load("{{url|safe}}");
    });'''

    def display(self, value=None, visualizer=None, **kw):
        base_url, query = urllib.splitquery(value)
        url = '%s?%s' % (base_url, urllib.urlencode(dict(
            embed_vis='true', visualizer_id=str(visualizer._id)
        )))
        return super(RetrieveContent, self).display(url=url, **kw)


class JSSyntax(BaseContentWidget):
    template = TEMPLATE_DIR + 'jssyntax.html'

    def __init__(self, *args, **kw):
        super(JSSyntax, self).__init__(*args, **kw)
        self.escape_re = re.compile(r'\.(html|xml|xme|xsl|js|css)\??.*$')

    def needs_escaping(self, value):
        return bool(self.escape_re.search(value))

    def display(self, value=None, with_credentials=None, **kw):
        prefix = ''.join(random.sample(string.ascii_uppercase, 8))
        if False and self.needs_escaping(value):
            if '?' in value:
                value += '&escape=true'
            else:
                value += '?escape=true'
        with_credentials = "true"
        return super(JSSyntax, self).display(
            prefix=prefix,
            value=value,
            with_credentials=with_credentials,
            **kw
        )


class DesignContent(BaseContentWidget):
    template = TEMPLATE_DIR + 'design.html'

    def resources(self):
        return []


class PDFContent(BaseContentWidget):
    template = TEMPLATE_DIR + 'pdf.html'

    def resources(self):
        pdfbase = "visualize/pdf/"
        buildbase = pdfbase + "build/"
        webbase = pdfbase + "web/"
        yield JSLink(buildbase + "pdf.js")
        page_JS_urls = [
            'compatibility.js',
            'debugger.js',
            'l10n.js',
            'viewer.js'
        ]
        for url in page_JS_urls:
            yield JSLink(webbase + url)
        yield CSSLink(webbase + "viewer.css")
        worker_url = buildbase + "pdf.worker.js"
        worker_link = JSLink(worker_url)
        yield worker_link
        worker_url = worker_link.manager.absurl(worker_url)
        yield JSScript("PDFJS.workerSrc = '{}';".format(worker_url))


class S3Content(BaseContentWidget):
    """
    Makes a request to a visualizer stored on S3 with the url of the resource
    to be visualized

    """

    def display(self, value=None, visualizer=None, **kwargs):
        # assemble path
        try:
            key = request.path.split('/content/', 1)[1]
        except IndexError:
            key = None
        if not key:
            key = visualizer.entry_point

        key = visualizer.key_prefix + key
        #        else:
        #            uri, ext = os.path.splitext(request.path)
        #            value += ext

        # render page from s3
        r = g.make_s3_request("GET", key)
        headers = dict(r.getheaders())
        mime_type = mimetypes.guess_type(key)[0]
        if mime_type:  # content-type bug
            headers.update({
                'content-type': mime_type
            })
        for header, val in headers.iteritems():
            response.headers[header] = val
        return r.read()


class ContentVisualizer(DispatchWidget):
    """
    Renders the visualized resource by dispatching the rendering to the
    appropriate content widget

    """
    widgets = dict(
        image=ImageContent(),
        syntax=JSSyntax(),
        pdf=PDFContent(),
        design=DesignContent(),
        cad=WebGLCADContent(),
        default=S3Content(),
        design_space=DesignSpace()
    )

    def __init__(self, **kw):
        super(ContentVisualizer, self).__init__(**kw)
        config = variable_decode(tg.config)
        content_widgets = config.get('visualize', {}).get('widgets', {})
        for key, path in content_widgets.items():
            widget_cls = import_object(path)
            self.widgets[key] = widget_cls()

    def get_url(self, value):
        return value


## Visualizers that require the resource within the server for processing
class Syntax(ew.Widget):
    """
    Builtin syntax visualizer

    Uses python pygments to highlight syntax

    """
    template = TEMPLATE_DIR + 'syntax.html'

    def display(self, value=None, filename=None, content=None, **kw):
        if content is None:
            content = value.text
        return super(Syntax, self).display(
            value=value,
            content=content,
            filename=filename,
            **kw
        )


class ArtifactRenderVisualizer(DispatchWidget):
    widgets = dict(
        default=Syntax()
    )


## Embed Visualizers -- Renders the iframe, tabs, etc
class NotFoundLink(Widget):
    template = TEMPLATE_DIR + 'urlnovis.html'
    defaults = dict(
        force_display=False
    )
    syntax_widget = JSSyntax()


class OldFile(ew.Widget):
    template = TEMPLATE_DIR + 'oldfile.html'

    def display(self, value=None, force=False, **kw):
        return super(OldFile, self).display(
            value=value, blob=value, force_display=force, **kw
        )


class LoadingAlt(ew.Widget):
    template = TEMPLATE_DIR + 'loadingalt.html'


class IFrame(Widget):
    """
    Simple iFrame for embedding a visualizer

    """
    template = TEMPLATE_DIR + 'iframe.html'
    defaults = dict(
        Widget.defaults,
        no_iframe_msg=(
            'Please install iframes in your browser to view this content'),
        mew_window_button=False
    )

    def get_query_params(self, extra_params=None):
        if extra_params is None:
            extra_params = {}
        extra_params.setdefault('env', 'vf')
        return urllib.urlencode(extra_params)

    def display(self, value=None, visualizer=None, extra_params=None,
                new_window_button=False, fs_url=None, **kw):
        encoded_params = self.get_query_params(extra_params=extra_params)
        src = get_iframe_url(value, visualizer, encoded_params)
        if new_window_button:
            fs_url = get_fs_url(value, visualizer=visualizer)
        return Widget.display(self, value=value, src=src, fs_url=fs_url, **kw)


class TabbedIFrame(IFrame):
    """
    Renders iFrame and fun tabs around it

    takes a url as value

    """
    template = TEMPLATE_DIR + 'tabbediframe.html'
    js_template = '''
    $(document).ready(function(){
         $vf.EmbedVisualizer({
            src: "{{active_url|safe}}",
            after: $('#{{id_prefix}}visualizerHat'),
            resource: "{{value|safe}}",
            filename: "{{filename}}",
            tabUrls: {{iframe_urls|safe}},
            iframeAttrs: {
                height: "{{height or ''}}"
            },
            hideTabBar: {{hide_tabs}}
         });
    });
    '''

    #noinspection PyMethodOverriding
    def display(self, value=None, visualizer=None, visualizers=None,
                extra_params=None, filename=None, hide_tabs=False, **kw):
        if filename is None:
            filename = os.path.split(urllib.splitquery(value)[0])[1]

        encoded_params = self.get_query_params(extra_params)
        active_url = get_iframe_url(value, visualizer, encoded_params)
        iframe_urls = url_iframe_json(value, visualizers, encoded_params)

        return Widget.display(
            self,
            value=value.replace('"', '\\"'),
            active_url=active_url.replace('"', '\\"'),
            iframe_urls=iframe_urls,
            filename=filename.replace('"', '\\"'),
            id_prefix=''.join(random.sample(string.ascii_uppercase, 8)),
            hide_tabs='true' if hide_tabs else 'false',
            **kw
        )


class ArtifactIFrame(TabbedIFrame):
    """Renders tabbed iframe given an artifact"""

    def display(self, value=None, visualizer=None, visualizers=None,
                extra_params=None, hide_tabs=False, **kw):
        if extra_params is None:
            extra_params = dict()
        elif isinstance(extra_params, basestring):
            extra_params = dict(
                urlparse.parse_qsl(urllib.unquote(extra_params)))
        extra_params.update({
            'refId': value.index_id(),
            'altRest': value.alternate_rest_url()
        })

        encoded = self.get_query_params(extra_params)
        escaped_url = urlquote(value.url_for_visualizer())

        active_url = get_iframe_url(escaped_url, visualizer, encoded)
        iframe_urls = url_iframe_json(escaped_url, visualizers, encoded)

        return Widget.display(self,
                              value=value.raw_url(),
                              active_url=active_url,
                              iframe_urls=iframe_urls,
                              filename=value.link_text_short(),
                              id_prefix=''.join(
                                  random.sample(string.ascii_uppercase, 8)),
                              hide_tabs='true' if hide_tabs else 'false',
                              **kw
        )


class UrlEmbedVisualizer(DispatchWidget):
    """
    Renders embedded visualizer given a resource url

    """
    widgets = dict(
        default=TabbedIFrame(),
        no_vis=NotFoundLink()
    )

    def get_url(self, value):
        return value


class ArtifactEmbedVisualizer(DispatchWidget):
    """
    Embeds a forge artifact visualization.

    value should behave like Artifact, in that it has a url_for_visualizer
    method.

    Currently used in the repository browser to view files.

    """
    widgets = dict(
        loading=LoadingAlt(),
        default=ArtifactIFrame(),
        no_vis=OldFile()
    )

    def get_url(self, value):
        return value.url_for_visualizer()

    def display(self, value=None, **kw):
        #if value.alt_loading:
        #    return self.widgets['loading'].display(value=value)
        return DispatchWidget.display(self, value=value, **kw)


# Widgets for displaying thumbnails
class Thumb(ew.Widget):
    template = TEMPLATE_DIR + 'thumb.html'

    def prepare_context(self, context):
        response = super(Thumb, self).prepare_context(context)
        response['get_fs_url'] = get_fs_url
        return response


class ImageThumb(Thumb):
    template = TEMPLATE_DIR + 'imagethumb.html'


class ThumbnailVisualizer(DispatchWidget):
    widgets = dict(
        image=ImageThumb(),
        default=Thumb()
    )


# Widgets for diffing
class DiffWidget(Widget):
    defaults = dict(Widget.defaults, a=None, b=None)

    @staticmethod
    def _get_diff(a, b):
        i = unified_diff(
            a.open().read().split('\n'),
            b.open().read().split('\n'),
            ('a' + a.path).encode('utf-8'),
            ('b' + b.path).encode('utf-8')
        )
        diff = ''.join(i)
        return diff


class DirectDiff(DiffWidget):
    template = TEMPLATE_DIR + 'diff_direct.html'

    def prepare_context(self, context):
        context = super(DirectDiff, self).prepare_context(context)
        context.update({
            'diff': self._get_diff(context['a'], context['b']),
        })
        return context


class SyntaxDiff(DiffWidget):
    template = TEMPLATE_DIR + 'diff_syntax.html'

    def prepare_context(self, context):
        context = super(SyntaxDiff, self).prepare_context(context)
        context.update({
            'diff': self._get_diff(context['a'], context['b']),
        })
        return context

    def resources(self):
        yield JSLink('css/hilite.css')


class DiffVisualizer(DispatchWidget):
    widgets = dict(
        syntax=SyntaxDiff(),
        default=DirectDiff()
    )

    def display(self, a=None, visualizers=None, visualizer=None, **kw):
        return super(DiffVisualizer, self).display(
            value=a, a=a, visualizer=visualizer, visualizers=visualizers, **kw
        )
