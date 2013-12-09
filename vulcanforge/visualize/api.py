import os
import posixpath
import mimetypes
from urlparse import urlparse

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

    _additional_text_extensions = {
        '.ini',
        '.gitignore',
        '.svnignore',
        'readme'
    }

    def __init__(self, resource):
        self.resource = resource
        super(BaseVisualizerAPI, self).__init__()

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

    def find_visualizers(self):
        return [vc.load() for vc in self._find_configs()]

    def get_visualizer(self):
        configs = self._find_configs()
        if configs:
            return configs[0].load()

    def _find_configs(self):
        mtype, extensions = self._get_mimetype_ext()
        configs = VisualizerConfig.find_for_mtype_ext(
            mime_type=mtype, extensions=extensions)
        return configs

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

        is_active = False
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
            filename=os.path.basename(self.url),
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

    def _get_mimetype_ext(self):
        parsed = urlparse(self.url)
        filename = os.path.basename(parsed.path)
        extensions = []
        base = filename.lower()
        remainder = ''
        mtype = None
        while True:
            base, ext = posixpath.splitext(base)
            if ext in self._additional_text_extensions or (
                    not ext and not mtype and
                        base in self._additional_text_extensions):
                mtype = 'text/plain'
            if not ext:
                break
            while ext in mimetypes.suffix_map:
                base, ext = posixpath.splitext(
                    base + mimetypes.suffix_map[ext])
            if ext in mimetypes.encodings_map:
                base, ext = posixpath.splitext(base)
            extensions.append(ext + remainder)
            remainder = ext + remainder

        if not mtype:
            mtype = mimetypes.guess_type(filename)[0]

        return mtype, extensions


class ArtifactVisualizerInterface(BaseVisualizerAPI):
    @property
    def url(self):
        return self.resource.url()

    @property
    def download_url(self):
        return self.resource.raw_url()

    def _find_configs(self):
        # differs from base class in that it finds visualizers with processing
        # hooks as well
        mtype, extensions = self._get_mimetype_ext()
        configs = VisualizerConfig.find_for_all_mtype_ext(
            mime_type=mtype, extensions=extensions)
        return configs

    def find_for_processing(self):
        mtype, extensions = self._get_mimetype_ext()
        cur = VisualizerConfig.find_for_processing_mtype_ext(
            mime_type=mtype, extensions=extensions)
        return [vc.load() for vc in cur]

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