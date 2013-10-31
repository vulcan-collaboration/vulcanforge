from vulcanforge.visualize.widgets import IFrame, ArtifactIFrame


class BaseVisualizer(object):
    """
    Base class for server side visualizers. Default options are provided below.

    To create your own visualizer, subclass this and minimally override the
    `content_widget` attribute and `mime_types` and `extensions` keys in the
    `default_options` attribute.

    To register your visualizer, add it to your configuration file like so:

        visualizer.<SHORTNAME> = <PATH_TO_VISUALIZER>

    e.g.:

        visualizer.syntax = vulcanforge.visualize.syntax:SyntaxVisualizer

    """

    # `content_widget` is the widget responsible for rendering a resource
    # within an iframe. The url of the resource can be accessed through the
    # resource_url query parameter in this context.
    content_widget = None

    # the default options when populating the database document that
    # corresponds to this visualizer
    default_options = {
        "name": None,
        "mime_types": None,
        "extensions": ['*'],
        "description": None,
        "icon": None,
        "priority": 0
    }

    # These widgets are responsible for rendering the container of the
    # visualizer, which defaults to an iframe with a src that points to
    # `vulcanforge.visualize.controllers.VisualizerController.src` with
    # resource_url as a query parameter that points to the url of the resource
    # to be visualized. These widgets typically do not need to be overridden.
    artifact_widget = ArtifactIFrame()
    url_widget = IFrame()

    def __init__(self, config):
        super(BaseVisualizer, self).__init__()
        self.config = config

    @property
    def name(self):
        return self.config.name

    @property
    def icon_url(self):
        return self.config.icon

    @property
    def src_url(self):
        """Base url of the IFrame src used for rendering content"""
        return '/visualize/{}/content/'.format(self.config._id)

    @property
    def fs_url(self):
        """Fullscreen URL"""
        return '/visualize/{}/fs/'.format(self.config._id)

    def get_query_for_url(self, url):
        return {
            "env": "vf",
            "resource_url": url
        }

    # these methods are just here to provide hooks for visualizer developers,
    # though the standard way of developing a server side visualizer is to
    # mount the appropriate content_widget on the visualizer class
    def render_url(self, url, **kwargs):
        return self.url_widget.display(url, self, **kwargs)

    def render_artifact(self, artifact, **kwargs):
        return self.artifact_widget.display(artifact, self, **kwargs)

    def render_content(self, value, **kwargs):
        return self.content_widget.display(value, **kwargs)


