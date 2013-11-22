# -*- coding: utf-8 -*-
from ming import schema
from ming.odm import FieldProperty
from ming.odm.declarative import MappedClass


class BaseMappedClass(MappedClass):

    _id = FieldProperty(schema.ObjectId)
    query = None
    # @type: ming.odm.mapper._ClassQuery

    class __mongometa__:
        abstract = True

    def flush_self(self):
        self.query.session.flush(self)
