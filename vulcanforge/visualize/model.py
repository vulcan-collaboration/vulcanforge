import re
import logging
from datetime import datetime
import os

import pymongo
from ming.odm.property import (
    FieldProperty,
    ForeignIdProperty,
    RelationProperty
)
from ming import schema, session
from ming.utils import LazyProperty
from pylons import tmpl_context as c
from pymongo.errors import DuplicateKeyError

from vulcanforge.artifact.model import ArtifactReference
from vulcanforge.s3.model import File
from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.common.model.session import main_orm_session
from vulcanforge.auth.model import User
from vulcanforge.common.util.filesystem import import_object

LOG = logging.getLogger(__name__)

VISUALIZER_PREFIX = 'Visualizer/'


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
        indexes = ['extensions', ('extensions', 'active')]
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
    processing_mime_types = FieldProperty([str])
    processing_extensions = FieldProperty([str], if_missing=['*'])
    priority = FieldProperty(int, if_missing=0)
    active = FieldProperty(bool, if_missing=True)
    creator_id = FieldProperty(schema.ObjectId, if_missing=lambda: c.user._id)
    created_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    modified_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    options = FieldProperty({})

    @staticmethod
    def strip_name(name):
        """Used to autocreate the shortname"""
        stripped = name.lower()\
            .replace('visualizer', '').strip()\
            .replace(' ', '_')
        return stripped

    @classmethod
    def from_visualizer(cls, visualizer, shortname=None):
        vis_config = cls(
            shortname=shortname,
            visualizer={
                "classname": visualizer.__name__,
                "module": visualizer.__module__
            },
            **visualizer.default_options)
        if not vis_config.shortname and vis_config.name:
            vis_config.shortname = cls.strip_name(vis_config.name)
        elif not vis_config.name and vis_config.shortname:
            vis_config.name = vis_config.shortname.capitalize()
        return vis_config

    @classmethod
    def find_active(cls, query):
        query['active'] = True
        return cls.query.find(query).sort('priority', pymongo.DESCENDING)

    @classmethod
    def find_for_mtype_ext(cls, mime_type=None, extensions=None):
        configs = []
        query = {"extensions": {"$in": extensions + ['*']}}
        cur = cls.query.find_active(query)

        if mime_type:
            configs = [vc for vc in cur if cls._matches_mime_type(
                mime_type, vc.mime_types)]
        elif extensions:
            configs = [vc for vc in cur if cls._matches_extensions(
                extensions, vc.extensions)]

        return configs

    @classmethod
    def find_for_processing_mtype_ext(cls, mime_type=None, extensions=None):
        configs = []
        query = {"processing_extensions": {"$in": extensions + ['*']}}
        cur = cls.query.find_active(query)

        if mime_type:
            configs = [vc for vc in cur if cls._matches_mime_type(
                mime_type, vc.processing_mime_types)]
        elif extensions:
            configs = [vc for vc in cur if cls._matches_extensions(
                extensions, vc.processing_extensions)]

        return configs

    @classmethod
    def find_for_all_mtype_ext(cls, mime_type=None, extensions=None):
        configs = cls.find_for_mtype_ext(mime_type, extensions)
        seen_ids = set(v._id for v in configs)
        for vc in cls.find_for_processing_mtype_ext(mime_type, extensions):
            if vc._id not in seen_ids:
                configs.append(vc)
        return configs

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

    @staticmethod
    def _matches_extensions(extensions, ext_opts):
        # no * matching
        return any(ext in ext_opts for ext in extensions)

    @staticmethod
    def _matches_mime_type(mime_type, mime_types):
        if not mime_types:  # matches any
            return True
        for pattern in mime_types:  # find explicit match
            if re.search(pattern, mime_type):
                return True
        return False


class _BaseVisualizerFile(File):
    class __mongometa__:
        name = '_base_visualizer_file'

    visualizer_config_id = ForeignIdProperty(VisualizerConfig, if_missing=None)
    visualizer = RelationProperty(VisualizerConfig, via="visualizer_id")


class ProcessedArtifactFile(_BaseVisualizerFile):
    """Represents visualizer-specific synthesized resources typically
    generated from processing a resource. For example, the STEP visualizer
    will generate meshes for visualization in the forge.

    By default (using `vulcanforge.visualize.widgets.IFrame`), the url of any
    these files will be included in the query str of the iframe src for use
    by the visualizer, with the parameter name determined by `query_param`.
    To hide the url of the original resource, provide `resource_url` as the
    value of `query_param`.

    `unique_id` uniquely identifies a given resource within the forge, and is
    used to map a resource to its processed files (the reverse lookup is
    currently unnecessary).

    `ref_id` associates a resource with a corresponding Artifact (if any)
    for access control purposes.

    """
    class __mongometa__:
        name = 'visualizer_processed_artifact'
        unique_indexes = [('unique_id', 'filename')]

    query_param = FieldProperty(str, if_missing='resource_url')
    unique_id = FieldProperty(str)
    ref_id = ForeignIdProperty(ArtifactReference, if_missing=None)
    status = FieldProperty(
        schema.OneOf('loading', 'ready', if_missing='ready'))

    @classmethod
    def get_from_visualizable(cls, visualizable, **kwargs):
        return cls.find_from_visualizable(visualizable, **kwargs).first()

    @classmethod
    def find_from_visualizable(cls, visualizable, **kwargs):
        kwargs['unique_id'] = visualizable.unique_id()
        return cls.query.get(**kwargs)

    @classmethod
    def upsert_from_visualizable(cls, visualizable, filename, **kwargs):
        pfile = cls.find_from_visualizable(
            visualizable, filename=filename).first()
        if not pfile:
            try:
                pfile = cls(
                    unique_id=visualizable.unique_id(),
                    filename=filename)
                session(pfile).flush(pfile)
            except DuplicateKeyError:  # pragma no cover
                session(pfile).expunge(pfile)
        kwargs.setdefault('ref_id', visualizable.artifact_ref_id())
        for name, value in kwargs.items():
            setattr(pfile, name, value)
        return pfile

    @LazyProperty
    def artifact(self):
        if self.ref_id:
            aref = ArtifactReference.query.get(_id=self.ref_id)
            if aref:
                return aref.artifact


class S3VisualizerFile(_BaseVisualizerFile):
    """File object uploaded by the s3hosted visualizer"""
    class __mongometa__:
        name = 's3_visualizer_file'

    parent_folder = FieldProperty(str, if_missing=None)

    def __init__(self, **kw):
        super(S3VisualizerFile, self).__init__(**kw)
        if self.parent_folder is None:
            self.parent_folder = os.path.dirname(self.filename)

    @property
    def default_keyname(self):
        return os.path.join(
            'Visualizer',
            str(self.visualizer_config_id),
            super(_BaseVisualizerFile, self).default_keyname)
