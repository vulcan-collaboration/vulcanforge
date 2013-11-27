import logging

from ming.odm import session
from pylons import app_globals as g

from vulcanforge.taskd import model_task
from vulcanforge.visualize.model import ProcessedArtifactFile
from vulcanforge.visualize.widgets import (
    IFrame,
    ArtifactIFrame,
    ArtifactDiff,
    UrlDiff)

LOG = logging.getLogger(__name__)


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
        "processing_mime_types": None,
        "processing_extensions": None,
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

    # Diff widgets (defaults to rendering content side by side)
    artifact_diff_widget = ArtifactDiff()
    url_diff_widget = UrlDiff()

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

    def get_query_for_artifact(self, artifact):
        query = self.get_query_for_url(artifact.raw_url())
        query['refId'] = artifact.artifact_ref_id()
        return query

    # these methods are just here to provide hooks for visualizer developers,
    # though the standard way of developing a server side visualizer is to
    # mount the appropriate content_widget on the visualizer class
    def render_url(self, url, **kwargs):
        return self.url_widget.display(url, self, **kwargs)

    def render_artifact(self, artifact, **kwargs):
        return self.artifact_widget.display(artifact, self, **kwargs)

    def render_content(self, value, **kwargs):
        return self.content_widget.display(value, **kwargs)

    def render_diff_url(self, url1, url2, **kwargs):
        return self.url_diff_widget.display(url1, url2, self, **kwargs)

    def render_diff_artifact(self, artifact1, artifact2, **kwargs):
        return self.artifact_diff_widget.display(
            artifact1, artifact2, self, **kwargs)

    # hooks
    def on_upload(self, artifact):
        pass

    def on_config_delete(self):
        pass

    def on_artifact_delete(self, artifact):
        pass


class _BaseProcessingVisualizer(BaseVisualizer):

    def get_query_for_artifact(self, artifact):
        query = super(_BaseProcessingVisualizer, self).get_query_for_artifact(
            artifact)
        cur = ProcessedArtifactFile.find_from_visualizable(
            artifact, visualizer_config_id=self.config._id)
        for pfile in cur:
            query[pfile.query_param] = pfile.url()
            if pfile.status == "error":
                query.update({
                    "processingStatus": "error",
                    "processingResourceId": pfile.unique_id
                })
            elif pfile.status == "loading" and not query.get(
                    "processingStatus"):
                query.update({
                    "processingStatus": "loading",
                    "processingResourceId": pfile.unique_id
                })
        return query

    def get_processing_status(self, artifact):
        """
        :return str (unprocessed, loading, ready, error)

        """
        pfile = ProcessedArtifactFile.get_from_visualizable(
            artifact, visualizer_config_id=self.config._id)
        if pfile:
            status = pfile.status
        else:
            status = 'unprocessed'
        return status

    def on_artifact_delete(self, artifact):
        cur = ProcessedArtifactFile.find_from_visualizable(
            artifact, visualizer_config_id=self.config._id)
        for pfile in cur:
            pfile.delete()

    def process_artifact(self, artifact):
        # subclasses should implement this
        pass


class OnDemandProcessingVisualizer(_BaseProcessingVisualizer):

    def get_query_for_artifact(self, artifact):
        # Looking at the query params means its time to process (it can't be on
        # render_artifact because full_render and visualizer options widget
        # do not call render_artifact
        status = self.get_processing_status(artifact)
        if status == 'unprocessed':
            self.process_artifact(artifact)
        super_func = super(
            OnDemandProcessingVisualizer, self).get_query_for_artifact
        return super_func(artifact)


class OnUploadProcessingVisualizer(OnDemandProcessingVisualizer):
    """
    Processes files on upload. If the file is not finished processing or
    for some reason hasn't been processed yet (for example, if the file is
    older than the visualizer), it reverts to the behavior of the
    OnDemandProcessingVisualizer.

    """

    def on_upload(self, artifact):
        self.process_artifact(artifact)


# For Visualizable artifacts and mapped classes
class VisualizableMixIn(object):

    # subclasses should implement the following not implemented methods
    def unique_id(self):
        """Globally unique identifier across all visualizable documents"""
        raise NotImplementedError('unique_id')

    def artifact_ref_id(self):
        pass

    def read(self):
        raise NotImplementedError('read')

    def url(self):
        raise NotImplementedError('url')

    def raw_url(self):
        return self.url()

    @model_task
    def trigger_vis_upload_hook(self):
        for visualizer in g.visualize_artifact(self).find_for_processing():
            try:
                visualizer.on_upload(self)
            except Exception:
                LOG.exception('Error running on_upload hook on %s in %s',
                              self.unique_id(), visualizer.name)

    @model_task
    def trigger_vis_delete_hook(self):
        for visualizer in g.visualize_artifact(self).find_for_processing():
            try:
                visualizer.on_delete(self)
            except Exception:
                LOG.exception('Error running on_delete hook on %s in %s',
                              self.unique_id(), visualizer.name)


class BaseFileProcessor(object):
    """Generates a single file from an artifact"""
    check_for_duplicate = True

    def __init__(self, artifact, visualizer):
        self.artifact = artifact
        self.visualizer = visualizer
        super(BaseFileProcessor, self).__init__()

    def run(self, pfile):
        raise NotImplementedError('run')

    @property
    def processed_filename(self):
        raise NotImplementedError('processed_filename')

    def make_processed_file(self, status="loading"):
        pfile = ProcessedArtifactFile.upsert_from_visualizable(
            self.artifact,
            self.processed_filename,
            visualizer_config_id=self.visualizer.config._id,
            status=status
        )
        session(ProcessedArtifactFile).flush(pfile)
        return pfile

    def full_run(self):
        LOG.info("Running file processor %s on %s", self.__class__.__name__,
                 self.artifact.unique_id())
        pfile = self.make_processed_file()

        # check for duplicate files
        do_run = True
        if self.check_for_duplicate:
            duplicate_pfile = pfile.find_duplicate()
            if duplicate_pfile:
                pfile.set_contents_from_string(duplicate_pfile.read())
                pfile.status = 'ready'
                do_run = False

        # call the run method
        if do_run:
            try:
                self.run(pfile)
            except Exception, e:
                LOG.info("Error processing {}:{} for {}\n{}".format(
                    self.artifact,
                    self.artifact.unique_id(),
                    self.visualizer,
                    e
                ))
                pfile.status = "error"
            else:
                pfile.status = "ready"

        return pfile
