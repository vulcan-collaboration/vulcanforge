# -*- coding: utf-8 -*-

from ming.odm.declarative import MappedClass


class BaseMappedClass(MappedClass):

    query = None  # TODO: confirm this doesn't break automatic assignment
    # @type: ming.odm.mapper._ClassQuery

    class __mongometa__:
        abstract = True
