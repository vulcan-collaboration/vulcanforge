import logging

from ming.odm import session
from pylons import app_globals as g

from vulcanforge.visualize.model import (
    ProcessedArtifactFile,
    ProcessingStatus,
    VisualizerConfig
)
from vulcanforge.visualize.tasks import visualizable_task
from vulcanforge.visualize.widgets import (
    IFrame,
    ArtifactIFrame,
    ArtifactDiff,
    UrlDiff
)

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

    def get_query_for_url(self, url, **kwargs):
        query = {
            "env": "vf",
            "resource_url": url
        }
        query.update(kwargs)
        return query

    def get_query_for_artifact(self, artifact, **kwargs):
        query = self.get_query_for_url(artifact.raw_url(), **kwargs)
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


class _BaseProcessingVisualizer(BaseVisualizer):

    def get_query_for_artifact(self, artifact, **kwargs):
        query = super(_BaseProcessingVisualizer, self).get_query_for_artifact(
            artifact, **kwargs)
        unique_id = artifact.get_unique_id()
        if "processingStatus" not in query:
            status = ProcessingStatus.get_status_str(unique_id, self.config)
            query["processingStatus"] = status
        query["processingResourceId"] = unique_id
        cur = ProcessedArtifactFile.find_from_visualizable(
            artifact, visualizer_config_id=self.config._id)
        for pfile in cur:
            query[pfile.query_param] = pfile.url()
        return query

    def process_artifact(self, artifact):
        # subclasses should implement this
        pass


class OnDemandProcessingVisualizer(_BaseProcessingVisualizer):

    def get_query_for_artifact(self, artifact, **kwargs):
        # Looking at the query params means its time to process (it can't be on
        # render_artifact because full_render and visualizer options widget
        # do not call render_artifact
        st_obj, is_new = ProcessingStatus.get_or_create(artifact, self.config)
        if is_new:
            artifact.process_for_visualizer.post(self.config._id)
        kwargs["processingStatus"] = st_obj.status
        func = super(OnDemandProcessingVisualizer, self).get_query_for_artifact
        return func(artifact, **kwargs)


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
    def get_unique_id(self):
        """Globally unique identifier across all visualizable documents"""
        raise NotImplementedError('unique_id')

    def artifact_ref_id(self):
        """For access control purposes"""
        pass

    def read(self):
        raise NotImplementedError('read')

    def url(self):
        raise NotImplementedError('url')

    def raw_url(self):
        return self.url()

    def find_processed_files(self, **query):
        return ProcessedArtifactFile.find_from_visualizable(self, **query)

    @classmethod
    def find_for_task(cls, _id):
        """Initialize this object with the arguments from get_task_lookup_args

        By default, assumes this is a MappedClass and uses the _id to query

        """
        return cls.query.get(_id=_id)

    def get_task_lookup_args(self):
        """Used in conjunction with find_for_task to reinitialize this object
        for asynchronous operations

        """
        return [self._id]

    @visualizable_task
    def trigger_vis_upload_hook(self):
        for visualizer in g.visualize_artifact(self).find_for_processing():
            try:
                visualizer.on_upload(self)
            except Exception:
                LOG.exception('Error running on_upload hook on %s in %s',
                              self.get_unique_id(), visualizer.name)

    @visualizable_task
    def process_for_visualizer(self, visualizer_config_id):
        vc = VisualizerConfig.query.get(_id=visualizer_config_id)
        visualizer = vc.load()
        visualizer.process_artifact(self)


class BaseFileProcessor(object):

    def __init__(self, artifact, visualizer):
        self.artifact = artifact
        self.visualizer = visualizer
        super(BaseFileProcessor, self).__init__()

    def run(self):
        """Subclasses implement this"""
        raise NotImplementedError('run')

    def make_processed_file(self, filename, **kwargs):
        pfile = ProcessedArtifactFile.upsert_from_visualizable(
            self.artifact,
            filename,
            visualizer_config_id=self.visualizer.config._id,
            **kwargs
        )
        session(ProcessedArtifactFile).flush(pfile)
        return pfile

    def set_status(self, status):
        ProcessingStatus.set_status_str(
            self.artifact.get_unique_id(), self.visualizer.config, status)

    def check_for_duplicates(self):
        """
        Find duplicates and copy if found

        Return true if duplicates found (will skip run)

        """
        return False

    def full_run(self):
        LOG.info("Running file processor %s on %s", self.__class__.__name__,
                 self.artifact.get_unique_id())
        self.set_status("loading")

        try:
            self.pre_duplicate_check()
            has_duplicate = self.check_for_duplicates()

            if not has_duplicate:
                try:
                    self.run()
                except Exception as exc:
                    self.on_error(exc)
                    raise
                else:
                    LOG.info("Finished Running file processor %s on %s",
                             self.__class__.__name__,
                             self.artifact.get_unique_id())
                    self.on_success()

                self.post_run()

        except Exception as exc:
            LOG.exception("Error processing {}:{} for {}".format(
                self.artifact,
                self.artifact.get_unique_id(),
                self.visualizer
            ))

    # hooks
    def pre_duplicate_check(self):
        pass

    def post_run(self):
        pass

    def on_error(self, exc):
        self.set_status('error')

    def on_success(self):
        self.set_status("ready")


class SingleFileProcessor(BaseFileProcessor):
    """Generates a single file from an artifact

    Will auto-create the ProcessedArtifact instance for you based on property
    `processed_filename`. Access through `self.result_file`

    """
    query_param = 'resource_url'

    def __init__(self, artifact, visualizer):
        super(SingleFileProcessor, self).__init__(artifact, visualizer)
        self.result_file = None

    @property
    def processed_filename(self):
        raise NotImplementedError('processed_filename')

    def make_result_file(self):
        self.result_file = self.make_processed_file(
            self.processed_filename,
            query_param=self.query_param)
        return self.result_file

    def pre_duplicate_check(self):
        self.make_result_file()

    def check_for_duplicates(self):
        duplicate_pfile = self.result_file.find_duplicates().first()
        if duplicate_pfile:
            has_duplicate = True
            LOG.info("Duplicate file found, using contents from %s",
                     duplicate_pfile.url())
            # NOTE: could optimize with in-server copy
            self.result_file.set_contents_from_string(duplicate_pfile.read())
            self.set_status("ready")
        else:
            has_duplicate = False
        return has_duplicate

    def on_error(self, exc):
        super(SingleFileProcessor, self).on_error(exc)
        if self.result_file:
            self.result_file.delete()
