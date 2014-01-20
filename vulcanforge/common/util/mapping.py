# -*- coding: utf-8 -*-

"""
mapping

@author: U{tannern<tannern@gmail.com>}
"""
from collections import defaultdict
import re


class PatternValueMap(object):
    """
    Register a group of values to regular expression patterns.
    Then lookup all the values for a given string.

    example and doctest:

        >>> m = PatternValueMap()
        >>> m.register(r'^a', 'A')
        >>> m.register(r'b$', 'B')
        >>> m.lookup('a')
        set(['A'])
        >>> m.lookup('a-')
        set(['A'])
        >>> m.lookup('-b')
        set(['B'])
        >>> m.lookup('a-b')
        set(['A', 'B'])
        >>> m.clear()
        >>> m.lookup('a')
        set([])
    """

    def __init__(self):
        self._patterns = {}
        self._values = defaultdict(set)

    def register(self, pattern, value):
        id_ = hash(pattern)
        self._patterns[id_] = re.compile(pattern)
        self._values[id_].add(value)

    def lookup(self, string_under_test):
        matching_ids = set()
        for id_, pattern in self._patterns.iteritems():
            if pattern.search(string_under_test) is not None:
                matching_ids.add(id_)
        values = set()
        for id_ in matching_ids:
            values.update(self._values[id_])
        return values

    def clear(self):
        self._patterns.clear()
        self._values.clear()
