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
from ming import schema
from ming.utils import LazyProperty
from pylons import tmpl_context as c, app_globals as g

from vulcanforge.artifact.model import ArtifactReference
from vulcanforge.s3.model import File
from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.common.model.session import main_orm_session
from vulcanforge.auth.model import User
from vulcanforge.common.util.filesystem import import_object

LOG = logging.getLogger(__name__)

VISUALIZER_PREFIX = 'Visualizer/'


class VisualizerConfig(BaseMappedClass):

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
    priority = FieldProperty(int, if_missing=0)
    active = FieldProperty(bool, if_missing=True)
    creator_id = FieldProperty(schema.ObjectId, if_missing=lambda: c.user._id)
    created_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    modified_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    options = FieldProperty({})  # dumping ground for visualizer specific opts

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
    def find_for_mtype_ext(cls, mime_type=None, extensions=None):
        # find matching visualizers
        if extensions is None:
            extensions = []
        cur = cls.query.find({
            "extensions": {"$in": extensions + ['*']},
            "active": True
        }).sort('priority', pymongo.DESCENDING)

        # get visualizers
        if mime_type:
            visualizers = [v for v in cur if v._matches_mime_type(mime_type)]
        else:
            visualizers = [v for v in cur
                           if v._matches_explicit_extensions(extensions)]

        return visualizers

    @property
    def creator(self):
        if self.creator_id:
            return User.query.get(_id=self.creator_id)

    def load(self):
        path = '{0.module}:{0.classname}'.format(self.visualizer)
        try:
            cls = import_object(path)
            inst = cls(self)
        except ImportError:
            inst = None
        return inst

    def _matches_explicit_extensions(self, extensions):
        # no * matching
        return any(ext in self.extensions for ext in extensions)

    def _matches_mime_type(self, mime_type):
        if not self.mime_types:  # matches any
            return True
        for pattern in self.mime_types:  # find explicit match
            if re.search(pattern, mime_type):
                return True
        return False


class _BaseVisualizerFile(File):
    class __mongometa__:
        name = None

    visualizer_config_id = ForeignIdProperty(VisualizerConfig)
    visualizer = RelationProperty(VisualizerConfig, via="visualizer_id")


class ProcessedArtifactFile(_BaseVisualizerFile):
    """Represents visualizer-specific synthesized resources typically
    generated from processing an artifact. For example, the STEP visualizer
    will generate meshes for visualization in the forge.

    """
    class __mongometa__:
        name = 'visualizer_processed_artifact'

    ref_id = ForeignIdProperty(ArtifactReference, if_missing=None)

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


