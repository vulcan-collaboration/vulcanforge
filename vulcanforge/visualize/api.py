import os
import posixpath
import mimetypes
import urllib
from urlparse import urlparse

from vulcanforge.visualize.exceptions import VisualizerError
from vulcanforge.visualize.model import VisualizerConfig
from vulcanforge.visualize.widgets import TabbedVisualizers


def raise_error(msg):
    raise VisualizerError(msg)


class VisualizerAPI(object):
    """
    VisualizerAPI is the sole entry point throughout the forge to render
    content by the visualizer framework.

    Mounted on pylons.app_globals

    """
    full_render_widget = TabbedVisualizers()

    _additional_text_extensions = {
        '.ini',
        '.gitignore',
        '.svnignore',
        'readme'
    }

    def full_render_artifact(self, artifact, shortnames=None, active=None,
                             extra_params=None, **kwargs):
        """
        Render artifact with toolbar "chrome" on the top

        @param shortnames list of visualizer shortnames to use
        @param active str shortname of visualizer to make active
        @param kwargs passed on to the render_artifact function on the
            visualizer

        """
        specs = []
        if shortnames:
            cur = VisualizerConfig.query.find(
                {"shortname": {"$in": shortnames}})
            visualizers = [config.load() for config in cur]
        else:
            visualizers = self.find_visualizers_by_artifact(artifact)
        for visualizer in visualizers:
            if not active:
                active = visualizer.config.shortname
            spec = self._make_spec_for_full(
                artifact.url(), visualizer, extra_params, active)
            spec["content"] = visualizer.render_artifact(
                artifact, extra_params=extra_params, **kwargs)
            specs.append(spec)
        return self.full_render_widget.display(
            specs,
            filename=os.path.basename(artifact.url()),
            download_url=artifact.raw_url(),
            **kwargs)

    def full_render_url(self, url, shortnames=None, active=None,
                        extra_params=None, **kwargs):
        """
        Render artifact with toolbar on the top

        @param shortnames list of visualizer shortnames to use
        @param active str shortname of visualizer to make active
        @param kwargs passed on to the render_url function on the
            visualizer

        """
        specs = []
        if shortnames:
            cur = VisualizerConfig.query.find(
                {"shortname": {"$in": shortnames}})
            visualizers = [config.load() for config in cur]
        else:
            visualizers = self.find_visualizers_by_url(url)
        for visualizer in visualizers:
            if not active:
                active = visualizer.config.shortname
            spec = self._make_spec_for_full(
                url, visualizer, extra_params, active)
            spec["content"] = visualizer.render_url(
                url, extra_params=extra_params, **kwargs)
            specs.append(spec)
        return self.full_render_widget.display(
            specs,
            filename=os.path.basename(url),
            download_url=url,
            **kwargs)

    def render_artifact(self, artifact, shortname=None,
                        on_not_found=raise_error, **kwargs):
        visualizer = self._get_visualizer_for_render(
            artifact.url(), shortname, on_not_found=on_not_found)
        return visualizer.render_artifact(artifact, **kwargs)

    def render_url(self, s, shortname=None, on_not_found=raise_error,
                   **kwargs):
        visualizer = self._get_visualizer_for_render(
            s, shortname, on_not_found=on_not_found)
        return visualizer.render_url(s, **kwargs)

    def get_icon_url(self, s, shortname=None):
        visualizer = self._get_visualizer_for_render(s, shortname)
        if visualizer:
            return visualizer.icon_url

    def find_configs_by_url(self, url):
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        mtype, extensions = self._get_mimetype_ext(filename)
        cur = VisualizerConfig.find_for_mtype_ext(
            mime_type=mtype, extensions=extensions)
        return cur

    def find_visualizers_by_url(self, url):
        return [vc.load() for vc in self.find_configs_by_url(url)]

    def get_visualizer_by_url(self, url):
        vc = self.find_configs_by_url(url).first()
        if vc:
            return vc.load()

    def find_visualizers_by_artifact(self, artifact):
        return [vc.load() for vc in self.find_configs_by_url(artifact.url())]

    def get_visualizer_by_artifact(self, artifact):
        vc = self.find_configs_by_url(artifact.url()).first()
        if vc:
            return vc.load()

    def _make_spec_for_full(self, url, visualizer, extra_params=None,
                            active=None):
        query = visualizer.get_query_for_url(url)
        if extra_params:
            query.update(extra_params)
        query_str = urllib.urlencode(query)
        spec = {
            "name": visualizer.name,
            "fullscreen_url": visualizer.fs_url + '?' + query_str,
            "active": active and visualizer.config.shortname == active,
        }
        return spec

    def _get_visualizer_for_render(self, url, shortname=None,
                                   on_not_found=None):
        visualizer = None
        if shortname:
            config = VisualizerConfig.query.get(shortname=shortname)
            if config:
                visualizer = config.load()
            elif on_not_found:
                on_not_found()
        else:
            visualizer = self.get_visualizer_by_url(url)
        return visualizer

    def _get_mimetype_ext(self, filename):
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
