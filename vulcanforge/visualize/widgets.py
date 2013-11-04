import json
import random
import string
import urllib
from urlparse import urlparse

from pylons import app_globals as g

from vulcanforge.resources.widgets import Widget
from vulcanforge.visualize.model import ProcessedArtifactFile


class BaseContentWidget(Widget):

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


class BaseArtifactDirect(Widget):
    """For direct visualization of an artifacts content, instead of placing it
    inside an iframe

    """
    pass


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
        params = visualizer.get_query_for_url(value)
        if extra_params:
            params.update(extra_params)
        return params

    def display(self, value, visualizer, extra_params=None,
                new_window_button=False, **kw):
        query = self.get_query(value, visualizer, extra_params)
        encoded_params = urllib.urlencode(query)
        src = visualizer.src_url + '?' + encoded_params
        if new_window_button:
            fs_url = visualizer.fs_url + '?' + encoded_params
            kw['fs_url'] = fs_url
        return Widget.display(self, value=value, src=src, **kw)


class ArtifactIFrame(IFrame):
    """Renders iframe given an artifact"""

    def get_resource_url(self, value, visualizer):
        return value.raw_url()

    def get_query(self, value, visualizer, extra_params=None):
        resource_url = self.get_resource_url(value, visualizer)
        query = super(ArtifactIFrame, self).get_query(
            resource_url, visualizer, extra_params)
        query['refId'] = value.artifact_ref_id()
        cur = ProcessedArtifactFile.find_from_visualizable(
            value, visualizer_config_id=visualizer.config._id)
        for pfile in cur:
            query[pfile.query_param] = pfile.url()
        return query


class TabbedVisualizers(Widget):
    template = 'visualize/widgets/tabbedvisualizers.html'
    js_template = '''
    $(function(){
        $("#visualizerTabs_{{uid}}").tabbedVisualizer({
            visualizerSpecs: JSON.parse({{ visualizer_specs }}),
            downloadUrl: {{ download_url }},
            filename: {{ filename }}
        });
    });
    '''

    defaults = dict(
        Widget.defaults,
        filename='',
        download_url='',
        new_window_button=True
    )

    def display(self, visualizer_specs, uid=None, **kw):
        """
        @param visualizer_specs list of dictoniaries:
        [{
            "name": str name of visualizer,
            "content": str from Visualizer.render_url or
                Visualizer.render_artifact
            "fullscreen_url": str optional url for fullscreen window button
            "active": bool optional default False
        }, ...]

        """
        if uid is None:
            uid = ''.join(random.sample(string.ascii_lowercase, 8))
        visualizer_specs = json.dumps(visualizer_specs)
        return super(TabbedVisualizers, self).display(
            visualizer_specs=visualizer_specs, uid=uid, **kw)

