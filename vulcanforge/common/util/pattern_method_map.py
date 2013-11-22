# -*- coding: utf-8 -*-

"""
pattern_method_map

@author: U{tannern<tannern@gmail.com>}
"""
import re


class PatternMethodMap(object):

    def __init__(self):
        self._map = []

    def register(self, regex, method):
        assert isinstance(regex, basestring), "regex must be a basestring"
        assert hasattr(method, '__call__'), "method must be callable"
        self._map.append((re.compile(regex), method,))

    def decorate(self, regex):
        def wrapper(method):
            self.register(regex, method)
            return method
        return wrapper

    def lookup(self, name):
        assert isinstance(name, basestring), "name must be a basestring"
        for pattern, method in self._map:
            match = pattern.match(name)
            if match is not None:
                return method, match
        raise KeyError("Pattern match not found")

    def apply(self, name, context_self=None):
        method, match = self.lookup(name)
        if method is not None:
            if context_self is not None:
                return method(context_self, name, match)
            else:
                return method(name, match)
        return None
