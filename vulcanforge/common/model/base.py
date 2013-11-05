# -*- coding: utf-8 -*-

from ming.odm.declarative import MappedClass


class BaseMappedClass(MappedClass):

    query = None
    # @type: ming.odm.mapper._ClassQuery

    class __mongometa__:
        abstract = True

    def flush_self(self):
        self.query.session.flush(self)
