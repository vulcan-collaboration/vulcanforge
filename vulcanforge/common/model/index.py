from pprint import pformat
import logging
from cPickle import dumps, loads

import bson
import pymongo
from pylons import app_globals as g
from ming import schema as S
from ming.utils import LazyProperty
from ming.odm import (
    FieldProperty, session, Mapper
)

from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.common.model.session import (
    main_orm_session, solr_indexed_session
)


LOG = logging.getLogger(__name__)


class GlobalObjectReference(BaseMappedClass):
    class __mongometa__:
        session = main_orm_session
        name = 'global_reference'

    _id = FieldProperty(str)
    object_reference = FieldProperty(S.Object(dict(
        cls=S.Binary,
        object_id=S.Anything(if_missing=None)
    )))

    @classmethod
    def from_object(cls, object_):
        """
        Upsert logic to generate a GlobalObjectReference object from a global
        object

        """
        obj = cls.query.get(_id=object_.index_id())
        if obj is not None:
            return obj
        try:
            obj = cls(
                _id=object_.index_id(),
                object_reference=dict(
                    cls=bson.Binary(dumps(object_.__class__)),
                    object_id=object_._id))
            session(obj).flush(obj)
            return obj
        except pymongo.errors.DuplicateKeyError:  # pragma no cover
            session(obj).expunge(obj)
            return cls.query.get(_id=object_.index_id())

    @LazyProperty
    def object(self):
        """Look up the artifact referenced"""
        oref = self.object_reference
        try:
            cls = loads(str(oref.cls))
            return cls.query.get(_id=oref.object_id)
        except Exception:
            LOG.exception('Error loading object for %s: %r', self._id, oref)


class SOLRIndexed(BaseMappedClass):
    """
    The base class for SOLR indexed objects. Objects can extend this just like
    they would BaseMappedClass. The only difference is that the __mongometa__
    inner class should use the `solr_indexed_session` session.

    It will automatically be added to solr (see index() method).

    """

    class __mongometa__:
        session = solr_indexed_session
        name = 'solr_indexed'

    read_roles = ['authenticated']
    type_s = 'Indexed Object'

    # Base schema
    _id = FieldProperty(S.ObjectId)

    def index_id(self, cls=None):
        """
        Globally unique artifact identifier.  Used for SOLR ID, and maybe
        elsewhere
        """
        if cls is None:
            cls = self.__class__
        id_ = '%s.%s#%s' % (cls.__module__, cls.__name__, self._id)
        return id_.replace('.', '/')

    def index(self, text_objects=None, **kwargs):
        """
        """
        text_objects = text_objects or []
        index = dict(
            id=self.index_id(),
            url_s=self.url(),
            read_roles=self.get_read_roles(),
            is_history_b=False,
            type_s=self.type_s,
            can_reference_b=False
        )
        index.update(**kwargs)
        # extend with property method
        index.update(self.index_dict)
        # set text with property method
        index_text = self.index_text
        if index_text:
            index['text'] = index_text
        # no text, generate a sensible default
        text_objects += self.index_text_objects
        if 'text' not in index.keys() and not text_objects:
            index['text'] = " ".join(map(str, map(pformat, [
                index[k] for k in index.keys()
                if k in g.index_default_text_fields
            ])))
        # append these objects to the text
        index['text'] = index.get('text', '') + " ".join(
            map(str, map(lambda x:
                         x.encode('ascii', "xmlcharrefreplace")
                         if type(x) == unicode else x, text_objects))
        )
        # Add the access rights
        index['read_roles'] = self.get_read_roles()

        #log.info("Indexed stuff: "+str(index))
        return index

    @property
    def index_dict(self):
        """
        Build a dictionary of index fields for SOLR. This will update the
        default index method.
        """
        return {}

    @property
    def index_text(self):
        """
        Compile the full text string that the SOLR index will query against.

        If this returns None then the default index method will generate the
        full text.
        """
        return None

    @property
    def index_text_objects(self):
        """
        Make a list of objects to be added into the index text.
        """
        return []

    def indexable(self):
        """
        This method determines if the object itself should be indexed
        """
        return True

    def url(self):
        """
        Subclasses should implement this, providing the URL to the artifact
        """
        raise NotImplementedError('url')  # pragma no cover

    def get_read_roles(self):
        return self.read_roles



