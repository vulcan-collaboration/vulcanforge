import hashlib
import logging
from datetime import datetime
import os

import pymongo
from ming.odm.property import (
    FieldProperty,
    ForeignIdProperty,
    RelationProperty
)
from ming import schema
from ming.odm import session
from ming.utils import LazyProperty
from pylons import tmpl_context as c
from pymongo.errors import DuplicateKeyError

from vulcanforge.s3.model import File
from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.common.model.session import (
    main_orm_session,
    project_orm_session
)
from vulcanforge.auth.model import User
from vulcanforge.common.util.filesystem import import_object

LOG = logging.getLogger(__name__)

VISUALIZER_PREFIX = 'Visualizer/'


def _get_context():
    context = {}
    if getattr(c, 'app', None):
        context['app_config_id'] = c.app.config._id
    if getattr(c, 'project', None):
        context['project_id'] = c.project._id
    if getattr(c, 'neighborhood', None):
        context['neighborhood_id'] = c.neighborhood._id
    return context


class VisualizerConfig(BaseMappedClass):
    """
    Database representation of a Forge Visualizer

    :param name: str display name of the visualizer
    :param shortname: str unique str
    :param description: str
    :param visualizer: dict path to Visualizer object
    :param icon: str url of icon to use for this visualizer
    :param mime_types: list of mimetypes to match to invoke this visualizer
    :param extensions: list of extensions to match (default all)
    :param processing_mime_types: list of mimetypes to match to invoke the
        visualizers pre-processing hooks
    :param processing_extensions: list of extensions to match to invoke the
        visualizers pre-processing hooks
    :param processing_status_exclude: list of `ProcessingStatus.status`
        values for a given visualizable that will prevent the visualizer from
        being invoked (e.g. set to ["error"] to not invoke visualizer if there
        is a processing error)
    :param priority: determines order for tabbed visualizer display
    :param active: bool
    :param creator_id: user_id
    :param created_date: date uploaded/created
    :param modified_date: date modified
    :param options: dict dumping ground for visualizer specific opts

    """

    class __mongometa__:
        name = 'visualizer'
        session = main_orm_session
        indexes = [('active', 'priority'), ('_id', 'priority')]
        unique_indexes = ['shortname']

        def before_save(data):
            data['modified_date'] = datetime.utcnow()

    _id = FieldProperty(schema.ObjectId)
    name = FieldProperty(str)
    shortname = FieldProperty(str)
    description = FieldProperty(str, if_missing='')
    visualizer = FieldProperty(schema.Object({
        'classname': str,
        'module': str
    }))
    icon = FieldProperty(str)
    mime_types = FieldProperty([str])
    extensions = FieldProperty([str], if_missing=['*'])
    processing_mime_types = FieldProperty([str], if_missing=None)
    processing_extensions = FieldProperty([str], if_missing=[])
    processing_status_exclude = FieldProperty([str], if_missing=[])
    priority = FieldProperty(int, if_missing=0)
    active = FieldProperty(bool, if_missing=True)
    creator_id = FieldProperty(schema.ObjectId, if_missing=lambda: c.user._id)
    created_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    modified_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    options = FieldProperty(None, if_missing={})

    @staticmethod
    def strip_name(name):
        """Used to autocreate the shortname"""
        stripped = name.lower()\
            .replace('visualizer', '').strip()\
            .replace(' ', '_')
        return stripped

    @classmethod
    def from_visualizer(cls, visualizer, shortname=None, **kwargs):
        attrs = visualizer.default_options
        attrs.update(kwargs)
        vis_config = cls(
            shortname=shortname,
            visualizer={
                "classname": visualizer.__name__,
                "module": visualizer.__module__
            },
            **attrs)
        if not vis_config.shortname and vis_config.name:
            vis_config.shortname = cls.strip_name(vis_config.name)
        elif not vis_config.name and vis_config.shortname:
            vis_config.name = vis_config.shortname.capitalize()
        return vis_config

    @classmethod
    def find_active(cls, query):
        query['active'] = True
        return cls.query.find(query).sort('priority', pymongo.DESCENDING)

    @property
    def creator(self):
        if self.creator_id:
            return User.query.get(_id=self.creator_id)

    def delete(self):
        visualizer = self.load()
        visualizer.on_config_delete()
        super(VisualizerConfig, self).delete()

    def load(self):
        path = '{0.module}:{0.classname}'.format(self.visualizer)
        try:
            cls = import_object(path)
            inst = cls(self)
        except ImportError:
            inst = None
        return inst


class _BaseVisualizerFile(File):
    class __mongometa__:
        name = '_base_visualizer_file'

    visualizer_config_id = ForeignIdProperty(VisualizerConfig, if_missing=None)
    visualizer = RelationProperty(VisualizerConfig, via="visualizer_config_id")

    @staticmethod
    def calculate_hash(data):
        md5 = hashlib.md5()
        md5.update(data)
        return md5.hexdigest()


class ProcessingStatus(BaseMappedClass):
    """Represents the status of processing for a visualizable object and
    visualizer, so that a loading animation can be displayed, an error
    message, etc.

    """
    class __mongometa__:
        name = 'visualizer_processing_status'
        session = project_orm_session
        unique_indexes = [('unique_id', 'visualizer_config_id')]

    unique_id = FieldProperty(str)  # unique_id of Visualizable
    visualizer_config_id = ForeignIdProperty(VisualizerConfig, if_missing=None)
    status = FieldProperty(
        schema.OneOf('loading', 'ready', 'error', if_missing='loading'))
    reason = FieldProperty(str, if_missing=None)

    # the following properties are only used for management purposes
    visualizable_kind = FieldProperty(str, if_missing=None)
    context = FieldProperty(schema.Object({
        "app_config_id": schema.ObjectId(if_missing=None),
        "project_id": schema.ObjectId(if_missing=None),
        "neighborhood_id": schema.ObjectId(if_missing=None)
    }))

    @classmethod
    def get_status_str(cls, unique_id, visualizer_config):
        st_obj = cls.query.get(unique_id=unique_id,
                               visualizer_config_id=visualizer_config._id)
        if st_obj:
            status = st_obj.status
        else:
            status = 'unprocessed'
        return status

    @classmethod
    def set_status_str(cls, unique_id, visualizer_config, status, reason=None):
        """
        Immediately sets status to :status  (does not wait for flush)

        """
        query = {
            "unique_id": unique_id,
            "visualizer_config_id": visualizer_config._id
        }
        cls.query.update(query, {"$set": {"status": status, "reason": reason}},
                         upsert=True)

    @classmethod
    def get_or_create(cls, visualizable, visualizer_config):
        st_obj = cls.query.get(unique_id=visualizable.get_unique_id(),
                               visualizer_config_id=visualizer_config._id)
        is_new = False
        if st_obj is None:
            try:
                st_obj = cls(unique_id=visualizable.get_unique_id(),
                             visualizable_kind=visualizable.visualizable_kind,
                             context=_get_context(),
                             visualizer_config_id=visualizer_config._id)
                session(cls).flush(st_obj)
            except DuplicateKeyError:  # pragma no cover
                session(cls).expunge(st_obj)
                st_obj = cls.query.get(
                    unique_id=visualizable.get_unique_id(),
                    visualizer_config_id=visualizer_config._id)
            else:
                is_new = True
        return st_obj, is_new


class BaseVisualizableFile(_BaseVisualizerFile):
    """File associated with a Visualizable object"""
    unique_id = FieldProperty(str)  # unique_id of Visualizable
    ref_id = ForeignIdProperty("ArtifactReference", if_missing=None)

    # the following properties are only used for management purposes
    visualizable_kind = FieldProperty(str, if_missing=None)
    context = FieldProperty(schema.Object({
        "app_config_id": schema.ObjectId(if_missing=None),
        "project_id": schema.ObjectId(if_missing=None),
        "neighborhood_id": schema.ObjectId(if_missing=None)
    }))

    @classmethod
    def get_from_visualizable(cls, visualizable, **kwargs):
        return cls.find_from_visualizable(visualizable, **kwargs).first()

    @classmethod
    def find_from_visualizable(cls, visualizable, **kwargs):
        kwargs['unique_id'] = visualizable.get_unique_id()
        return cls.query.find(kwargs)

    @classmethod
    def upsert_from_visualizable(cls, visualizable, filename,
                                 visualizer_config_id, **kwargs):
        pfile = cls.find_from_visualizable(
            visualizable,
            filename=filename,
            visualizer_config_id=visualizer_config_id).first()
        if not pfile:
            try:
                pfile = cls(
                    unique_id=visualizable.get_unique_id(),
                    visualizable_kind=visualizable.visualizable_kind,
                    visualizer_config_id=visualizer_config_id,
                    context=_get_context(),
                    filename=filename)
                session(cls).flush(pfile)
            except DuplicateKeyError:  # pragma no cover
                session(pfile).expunge(pfile)
                pfile = cls.find_from_visualizable(
                    visualizable, filename=filename).first()
        kwargs.setdefault('ref_id', visualizable.artifact_ref_id())
        for name, value in kwargs.items():
            setattr(pfile, name, value)
        return pfile

    @LazyProperty
    def artifact(self):
        """Associated artifact (if any) for access control purposes.

        Note that this is not necessarily the original visualizable object.

        """
        from vulcanforge.artifact.model import ArtifactReference
        if self.ref_id:
            return ArtifactReference.artifact_by_index_id(self.ref_id)

    # the following are implemented for process chaining
    def get_unique_id(self):
        return self.unique_id

    def artifact_ref_id(self):
        return self.ref_id


class ProcessedArtifactFile(BaseVisualizableFile):
    """Represents visualizer-specific synthesized resources
    generated from processing a resource. For example, the STEP visualizer
    will generate meshes for visualization in the forge.

    By default (using `vulcanforge.visualize.widgets.IFrame`), the url of any
    these files will be included in the query str of the iframe src for use
    by the visualizer, with the parameter name determined by `query_param`.
    To hide the url of the original resource, provide `resource_url` as the
    value of `query_param`. If `query_param` is None, it will not show up in
    the iframe query.

    `unique_id` uniquely identifies a given resource within the forge, and is
    used to map a resource to its processed files (the reverse lookup is
    currently unnecessary).

    `ref_id` associates a resource with a corresponding Artifact (if any)
    for access control purposes.

    """
    class __mongometa__:
        name = 'visualizer_processed_artifact'
        unique_indexes = [('unique_id', 'filename')]

    query_param = FieldProperty(None, if_missing='resource_url')
    origin_hash = FieldProperty(str, if_missing=None)

    @classmethod
    def upsert_from_visualizable(cls, visualizable, filename,
                                 visualizer_config_id, **kwargs):
        pfile = super(ProcessedArtifactFile, cls).upsert_from_visualizable(
            visualizable, filename, visualizer_config_id, **kwargs)
        if not pfile.origin_hash:
            pfile.origin_hash = cls.calculate_hash(visualizable.read())
        return pfile

    def find_duplicates(self):
        duplicate_query = {
            "origin_hash": self.origin_hash,
            "_id": {"$ne": self._id}
        }
        return self.__class__.query.find(duplicate_query)


class S3VisualizerFile(_BaseVisualizerFile):
    """File object uploaded by the s3hosted visualizer"""
    class __mongometa__:
        name = 's3_visualizer_file'

    parent_folder = FieldProperty(str, if_missing=None)
    # content hash is used to manage updating modified files
    content_hash = FieldProperty(str, if_missing=None)

    def __init__(self, **kw):
        super(S3VisualizerFile, self).__init__(**kw)
        if self.parent_folder is None:
            self.parent_folder = os.path.dirname(self.filename)
        self.__calculate_hash = True

    @classmethod
    def upsert_from_data(cls, filename, visualizer_config_id, data, **kw):
        obj = cls.query.get(filename=filename,
                            visualizer_config_id=visualizer_config_id)
        if not obj:
            obj = cls.from_data(filename, data,
                                visualizer_config_id=visualizer_config_id)
            return obj

        data_hash = cls.calculate_hash(data)
        if obj.content_hash != data_hash:
            obj.__calculate_hash = False
            obj.set_contents_from_string(data)
            obj.content_hash = data_hash
        return obj

    @property
    def default_keyname(self):
        return os.path.join(
            'Visualizer',
            str(self.visualizer_config_id),
            super(_BaseVisualizerFile, self).default_keyname)

    def _update_metadata(self):
        super(S3VisualizerFile, self)._update_metadata()
        if self.__calculate_hash:
            self.content_hash = self.calculate_hash(self.read())
        else:
            self.__calculate_hash = True
