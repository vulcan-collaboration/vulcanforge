import json
import random
import string
import urllib
from urlparse import urlparse

from pylons import app_globals as g
from vulcanforge.common.helpers import slugify

from vulcanforge.resources.widgets import Widget, JSLink, CSSLink, JSScript
from vulcanforge.visualize.model import ProcessedArtifactFile


class BaseContentWidget(Widget):

    def resources(self):
        yield JSLink('js//lib/jquery/jquery.1.7.2.min.js', scope="forge")
        yield JSLink('js/lib/jquery/jquery-ui.1.10.3.js', scope="forge")
        yield JSLink('visualize/js/visualize.js', scope="forge")

        yield CSSLink('css/core.scss')
        yield CSSLink('css/hilite.css')
        yield CSSLink('theme/css/theme.scss')
        yield CSSLink('visualize/css/visualize.css')

    def needs_credentials(self, value):
        needs_creds = False
        parsed = urlparse(value)
        base_url = '{}://{}/'.format(parsed.scheme, parsed.netloc)
        if not g.s3_serve_local and g.base_s3_url == base_url:
            needs_creds = True
        return needs_creds

    def display(self, value, uid=None, **kw):
        if uid is None:
            uid = ''.join(random.sample(string.ascii_uppercase, 8))
        with_credentials = self.needs_credentials(value)
        return super(BaseContentWidget, self).display(
            value=value, uid=uid, with_credentials=with_credentials, **kw)


class ProcessingContentWidget(BaseContentWidget):
    """For visualizers that implement preprocessing hooks"""
    def resources(self):
        for r in super(ProcessingContentWidget, self).resources():
            yield r
        yield JSScript('''
        $(VIS).on("initConfig", function(e, config){
            config.loadingImg = "%s";
        });
        ''' % g.resource_manager.absurl("images/PleaseWait.gif"))


class IFrame(Widget):
    """
    Simple iframe for embedding a visualizer

    """
    template = 'visualize/widgets/iframe.html'
    defaults = dict(
        Widget.defaults,
        no_iframe_msg=(
            'Please install iframes in your browser to view this content'),
        fs_url=None,
        src=None,
        new_window_button=False
    )

    def get_query(self, value, visualizer, extra_params=None):
        query = visualizer.get_query_for_url(value)
        if extra_params:
            query.update(extra_params)
        return query

    def get_full_urls(self, value, visualizer, extra_params=None):
        query = self.get_query(value, visualizer, extra_params)
        encoded_params = urllib.urlencode(query)
        src_url = visualizer.src_url + '?' + encoded_params
        fs_url = visualizer.fs_url + '?' + encoded_params
        return src_url, fs_url

    def display(self, value, visualizer, extra_params=None,
                new_window_button=False, **kwargs):
        src_url, fs_url = self.get_full_urls(value, visualizer, extra_params)
        kwargs['src'] = src_url
        if new_window_button:
            kwargs['fs_url'] = fs_url
        return Widget.display(self, **kwargs)


class ArtifactIFrame(IFrame):
    """Renders iframe given an artifact"""

    def get_query(self, value, visualizer, extra_params=None):
        query = visualizer.get_query_for_artifact(value)
        if extra_params:
            query.update(extra_params)
        return query


class TabbedVisualizers(Widget):
    template = 'visualize/widgets/tabbedvisualizers.html'
    js_template = '''
    $(function(){
        $("#visualizerTabs_{{uid}}").tabbedVisualizer({
            visualizerSpecs: JSON.parse('{{ visualizer_specs }}'),
            downloadUrl: "{{ download_url }}",
            filename: "{{ filename }}"
        });
    });
    '''

    defaults = dict(
        Widget.defaults,
        filename='',
        download_url='',
        new_window_button=True
    )

    def resources(self):
        yield JSLink('visualize/js/tabbed_visualizer.js')

    def display(self, visualizer_specs, uid=None, **kw):
        """
        @param visualizer_specs list of dictoniaries:
        [{
            "name": str name of visualizer,
            "iframe_url": str from Visualizer.render_url or
                Visualizer.render_artifact
            "fullscreen_url": str optional url for fullscreen window button
            "active": bool optional default False
        }, ...]

        """
        if uid is None:
            uid = ''.join(random.sample(string.ascii_lowercase, 8))
        visualizer_specs = json.dumps(visualizer_specs).replace('\\', '\\\\')
        return super(TabbedVisualizers, self).display(
            visualizer_specs=visualizer_specs, uid=uid, **kw)


class UrlDiff(Widget):
    template = 'visualize/widgets/diff.html'
    defaults = dict(
        Widget.defaults,
        no_iframe_msg=(
            'Please install iframes in your browser to view this content')
    )

    def get_queries(self, value, value2, visualizer, extra_params=None):
        query1 = visualizer.get_query_for_url(value)
        query2 = visualizer.get_query_for_url(value2)
        if extra_params:
            query1.update(extra_params)
            query2.update(extra_params)
        return query1, query2

    def get_src_urls(self, value, value2, visualizer, extra_params=None):
        query1, query2 = self.get_queries(
            value, value2, visualizer, extra_params)
        base_url = visualizer.src_url + '?'
        url1 = base_url + urllib.urlencode(query1)
        url2 = base_url + urllib.urlencode(query2)
        return url1, url2

    def display(self, value, value2, visualizer, extra_params=None, **kwargs):
        url1, url2 = self.get_src_urls(value, value2, visualizer, extra_params)
        return super(UrlDiff, self).display(url1=url1, url2=url2)


class ArtifactDiff(UrlDiff):
    def get_queries(self, value, value2, visualizer, extra_params=None):
        query1 = visualizer.get_query_for_artifact(value)
        query2 = visualizer.get_query_for_artifact(value2)
        if extra_params:
            query1.update(extra_params)
            query2.update(extra_params)
        return query1, query2


class TabbedDiffs(Widget):
    template = 'visualize/widgets/tabbed_diffs.html'
    js_template = '''
    $(function(){
        $('#visualizerDiffTabs_{{ uid }}').tabs();
    });
    '''

    def display(self, diff_specs, uid=None, **kw):
        """
        @param diff_specs: list of dictoniaries:
        [{
            "name": str name of visualizer,
            "content": str html content of diff
            "slug": str optional default sluggified name
        }, ...]


        """
        for spec in diff_specs:
            spec.setdefault('slug', slugify(spec["name"]))
        if uid is None:
            uid = ''.join(random.sample(string.ascii_lowercase, 8))
        return super(TabbedDiffs, self).display(
            diff_specs=diff_specs, uid=uid, **kw)
