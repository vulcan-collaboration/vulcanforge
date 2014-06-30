import os
import posixpath
import mimetypes
from urlparse import urlparse

from pylons import app_globals as g
from vulcanforge.common.helpers import urlunquote

from vulcanforge.visualize.widgets import TabbedVisualizers, TabbedDiffs
from vulcanforge.visualize.exceptions import VisualizerError
from vulcanforge.visualize.model import VisualizerConfig


def raise_error(msg):
    raise VisualizerError(msg)


class BaseVisualizerAPI(object):
    """
    VisualizerAPI is the sole entry point throughout the forge to render
    content by the visualizer framework.

    Mounted on pylons.app_globals

    """
    full_render_widget = TabbedVisualizers()
    full_diff_widget = TabbedDiffs()

    def __init__(self, resource):
        self.resource = resource
        super(BaseVisualizerAPI, self).__init__()

    def full_render(self, shortnames=None, active_shortname=None,
                    extra_params=None, on_unvisualizable=None, **kwargs):
        """
        Render resource with toolbar "chrome" on the top

        @param shortnames list of visualizer shortnames to use
        @param active_shortname str shortname of visualizer to make active
        @param kwargs passed on to the appropriate render function on the
            visualizer

        """
        specs = []
        visualizers = self._find_with_optional_shortnames(shortnames)
        if not visualizers:
            if on_unvisualizable:
                return on_unvisualizable(self.resource)
            else:
                return ''

        is_first = True
        for visualizer in visualizers:
            # is active visualizer
            if not active_shortname and is_first:
                is_active = True
            else:
                is_active = active_shortname == visualizer.config.shortname

            # get fs_url, src
            iframe_url, fs_url = self.get_content_urls_for_visualizer(
                visualizer, extra_params)
            spec = {
                "name": visualizer.name,
                "iframe_url": iframe_url,
                "fullscreen_url": fs_url,
                "active": is_active
            }
            specs.append(spec)
            is_first = False

        return self.full_render_widget.display(
            specs,
            filename=os.path.basename(urlunquote(self.url)),
            download_url=self.download_url,
            **kwargs)

    def render(self, shortname=None, on_unvisualizable=None, **kwargs):
        visualizer = self._get_with_optional_shortname(shortname)
        if visualizer is None:
            if on_unvisualizable:
                return on_unvisualizable(self.resource)
            else:
                return ''
        return self.render_for_visualizer(visualizer, **kwargs)

    def find_visualizers(self):
        configs = g.visualizer_mapper.find_for_visualization(self.filename)
        return [vc.load() for vc in configs]

    def get_visualizer(self):
        config = g.visualizer_mapper.get_for_visualization(self.filename)
        if config:
            return config.load()

    def get_icon_url(self, shortname=None):
        visualizer = self._get_with_optional_shortname(shortname)
        if visualizer:
            return visualizer.icon_url

    def diff(self, resource, shortname=None, on_unvisualizable=None, **kwargs):
        visualizer = self._get_with_optional_shortname(shortname)
        if visualizer is None:
            if on_unvisualizable:
                return on_unvisualizable(self.resource)
            else:
                return ''
        return self.render_diff_for_visualizer(resource, visualizer, **kwargs)

    def full_diff(self, resource, shortnames=None, on_unvisualizable=None,
                  **kwargs):
        specs = []
        visualizers = self._find_with_optional_shortnames(shortnames)
        if not visualizers:
            if on_unvisualizable:
                return on_unvisualizable(self.resource)
            else:
                return ''

        for visualizer in visualizers:
            # get fs_url, src
            spec = {
                "name": visualizer.name,
                "content": self.render_diff_for_visualizer(
                    resource, visualizer, **kwargs),
            }
            specs.append(spec)

        return self.full_diff_widget.display(
            specs, filename=os.path.basename(self.url), **kwargs)

    def _find_with_optional_shortnames(self, shortnames=None):
        # get all visualizers for this resource, or specified shortnames
        if shortnames:
            cur = VisualizerConfig.query.find(
                {"shortname": {"$in": shortnames}})
            visualizers = [config.load() for config in cur]
        else:
            visualizers = self.find_visualizers()
        return visualizers

    def _get_with_optional_shortname(self, shortname=None):
        visualizer = None
        if shortname:
            config = VisualizerConfig.query.get(shortname=shortname)
            if config:
                visualizer = config.load()
        else:
            visualizer = self.get_visualizer()
        return visualizer

    @property
    def filename(self):
        parsed = urlparse(self.url)
        return os.path.basename(parsed.path)

    @property
    def url(self):
        raise NotImplementedError('url')

    @property
    def download_url(self):
        raise NotImplementedError('download_url')

    def render_for_visualizer(self, visualizer, **kwargs):
        raise NotImplementedError('render_for_visualizer')

    def get_content_urls_for_visualizer(self, visualizer, extra_params=None):
        raise NotImplementedError('get_content_urls_for_visualizer')

    def render_diff_for_visualizer(self, resource, visualizer, **kwargs):
        raise NotImplementedError('render_diff_for_visualizer')


class ArtifactVisualizerInterface(BaseVisualizerAPI):
    @property
    def url(self):
        return self.resource.url()

    @property
    def download_url(self):
        return self.resource.raw_url()

    def find_visualizers(self):
        configs = g.visualizer_mapper.find_for_all(
            self.filename, unique_id=self.resource.get_unique_id())
        return [vc.load() for vc in configs]

    def find_for_processing(self):
        configs = g.visualizer_mapper.find_for_processing(
            self.filename, unique_id=self.resource.get_unique_id())
        return [vc.load() for vc in configs]

    def get_visualizer(self):
        config = g.visualizer_mapper.get_for_all(
            self.filename, unique_id=self.resource.get_unique_id())
        if config:
            return config.load()

    def render_for_visualizer(self, visualizer, **kwargs):
        return visualizer.render_artifact(self.resource, **kwargs)

    def get_content_urls_for_visualizer(self, visualizer, extra_params=None):
        return visualizer.artifact_widget.get_full_urls(
            self.resource, visualizer, extra_params)

    def render_diff_for_visualizer(self, resource, visualizer, **kwargs):
        return visualizer.render_diff_artifact(
            self.resource, resource, **kwargs)


class UrlVisualizerInterface(BaseVisualizerAPI):
    @property
    def url(self):
        return self.resource

    @property
    def download_url(self):
        return self.resource

    def find_for_processing(self):
        return []  # no processing from urls

    def render_for_visualizer(self, visualizer, **kwargs):
        return visualizer.render_url(self.resource, **kwargs)

    def get_content_urls_for_visualizer(self, visualizer, extra_params=None):
        return visualizer.url_widget.get_full_urls(
            self.resource, visualizer, extra_params)

    def render_diff_for_visualizer(self, resource, visualizer, **kwargs):
        return visualizer.render_diff_url(
            self.resource, resource, **kwargs)
