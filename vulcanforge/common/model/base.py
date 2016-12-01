# -*- coding: utf-8 -*-
import bson

from ming import schema
from ming.odm import FieldProperty, session
from ming.odm.declarative import MappedClass


class BaseMappedClass(MappedClass):

    _id = FieldProperty(schema.ObjectId)
    query = None
    # @type: ming.odm.mapper._ClassQuery

    class __mongometa__:
        abstract = True

    def flush_self(self):
        self.query.session.flush(self)

    @classmethod
    def get_pymongo_db(cls):
        return session(cls).impl.bind.db

    @classmethod
    def get_pymongo_db_and_collection(cls):
        db = cls.get_pymongo_db()
        return db, db[cls.__mongometa__.name]

    @property
    def created_date(self):
        if self._id:
            return self._id.generation_time.replace(tzinfo=None)
