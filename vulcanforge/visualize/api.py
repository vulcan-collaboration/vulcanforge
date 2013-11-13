

from vulcanforge.visualize.resource_interface import (
    ArtifactResourceInterface,
    UrlResourceInterface
)
from vulcanforge.visualize.widgets import TabbedVisualizers, TabbedDiffs


class VisualizerAPI(object):
    """
    VisualizerAPI is the sole entry point throughout the forge to render
    content by the visualizer framework.

    Mounted on pylons.app_globals

    """
    full_render_widget = TabbedVisualizers()
    full_diff_widget = TabbedDiffs()

    artifact_interface_cls = ArtifactResourceInterface
    url_interface_cls = UrlResourceInterface

    _additional_text_extensions = {
        '.ini',
        '.gitignore',
        '.svnignore',
        'readme'
    }

    def full_render_artifact(self, artifact, **kwargs):
        """
        Render artifact with toolbar "chrome" on the top

        @param shortnames list of visualizer shortnames to use
        @param active_shortname str shortname of visualizer to make active
        @param kwargs passed on to the render_artifact function on the
            visualizer

        """
        interface = self.artifact_interface_cls(artifact, self)
        return interface.full_render(**kwargs)

    def full_render_url(self, url, **kwargs):
        """
        Render artifact with toolbar on the top

        @param shortnames list of visualizer shortnames to use
        @param active_shortname str shortname of visualizer to make active
        @param kwargs passed on to the render_url function on the
            visualizer

        """
        interface = self.url_interface_cls(url, self)
        return interface.full_render(**kwargs)

    def render_artifact(self, artifact, shortname=None, **kwargs):
        """Render an artifact with a single visualizer with no toolbar

        @param shortname: shortname of visualizer to use to render
        @param kwargs: kwargs to pass on to the render_artifact function of the
            visualizer

        """
        interface = self.artifact_interface_cls(artifact, self)
        return interface.render(shortname=shortname, **kwargs)

    def render_url(self, url, shortname=None, **kwargs):
        """Render a url with a single visualizer with no toolbar

        @param shortname: shortname of visualizer to use to render
        @param kwargs: kwargs to pass on to the render_artifact function of the
            visualizer

        """
        interface = self.url_interface_cls(url, self)
        return interface.render(shortname=shortname, **kwargs)

    def get_icon_url(self, url, shortname=None):
        interface = self.url_interface_cls(url, self)
        return interface.get_icon_url(shortname)

    def find_visualizers_by_url(self, url):
        interface = self.url_interface_cls(url, self)
        return interface.find_visualizers()

    def get_visualizer_by_url(self, url):
        interface = self.url_interface_cls(url, self)
        return interface.get_visualizer()

    def find_visualizers_by_artifact(self, artifact):
        interface = self.artifact_interface_cls(artifact, self)
        return interface.find_visualizers()

    def get_visualizer_by_artifact(self, artifact):
        interface = self.artifact_interface_cls(artifact, self)
        return interface.get_visualizer()

    def find_for_processing(self, artifact):
        interface = self.artifact_interface_cls(artifact, self)
        return interface.find_for_processing()

    def content_urls_for_artifact(self, artifact, visualizer,
                                  extra_params=None):
        interface = self.artifact_interface_cls(artifact, self)
        return interface.get_content_urls_for_visualizer(
            visualizer, extra_params)

    def content_urls_for_url(self, url, visualizer, extra_params=None):
        interface = self.url_interface_cls(url, self)
        return interface.get_content_urls_for_visualizer(
            visualizer, extra_params)

    def full_diff_artifact(self, artifact1, artifact2, shortnames=None,
                           **kwargs):
        interface = self.artifact_interface_cls(artifact1, self)
        return interface.full_diff(artifact2, shortnames=shortnames, **kwargs)

    def full_diff_url(self, url1, url2, shortnames=None, **kwargs):
        interface = self.url_interface_cls(url1, self)
        return interface.full_diff(url2, shortnames=shortnames, **kwargs)

    def diff_artifact(self, artifact1, artifact2, shortname=None, **kwargs):
        interface = self.artifact_interface_cls(artifact1, self)
        return interface.diff(artifact2, shortname=shortname, **kwargs)

    def diff_url(self, url1, url2, shortname=None, **kwargs):
        interface = self.url_interface_cls(url1, self)
        return interface.diff(url2, shortname=shortname, **kwargs)
