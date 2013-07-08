# -*- coding: utf-8 -*-

"""
test_authorizer

@author: U{tannern<tannern@gmail.com>}
"""
import re
import unittest
import mock
from vulcanforge.websocket.authorizer import PatternMethodMap


PATTERN_TYPE = type(re.compile(''))


class PatternMethodMapTestCast(unittest.TestCase):

    def setUp(self):
        self.map = PatternMethodMap()

    def tearDown(self):
        del self.map

    def test_register(self):
        self.map.register(r'^foo$', lambda name, match: name)
        self.assertEqual(len(self.map._map), 1)
        entry = self.map._map[0]
        self.assertEqual(len(entry), 2)
        regex, method = entry
        self.assertIsInstance(regex, PATTERN_TYPE)
        self.assertTrue(hasattr(method, '__call__'))

    def test_register_assertions(self):
        with self.assertRaises(AssertionError):
            self.map.register(0, lambda name, match: name)
        with self.assertRaises(AssertionError):
            self.map.register('', 0)

    def test_decorate(self):
        self.map.decorate(r'^foo$')(lambda name, match: name)
        self.assertEqual(len(self.map._map), 1)
        entry = self.map._map[0]
        self.assertEqual(len(entry), 2)
        regex, method = entry
        self.assertIsInstance(regex, PATTERN_TYPE)
        self.assertTrue(hasattr(method, '__call__'))

    def test_double_decorate(self):
        method = lambda name, match: name
        self.map.decorate(r'^bar$')(self.map.decorate(r'^foo$')(method))
        self.assertEqual(len(self.map._map), 2)
        entry = self.map._map[0]
        self.assertEqual(len(entry), 2)
        regex, entry_method = entry
        self.assertEqual(entry_method, method)
        entry = self.map._map[1]
        self.assertEqual(len(entry), 2)
        regex, entry_method = entry
        self.assertEqual(entry_method, method)

    def test_decorate_assertions(self):
        with self.assertRaises(AssertionError):
            self.map.decorate(0)(lambda name, match: name)
        with self.assertRaises(AssertionError):
            self.map.decorate('')(0)

    def test_lookup(self):
        method = lambda name, match: name
        self.map._map = [
            (re.compile('^foo$'), method)
        ]
        found_method, match = self.map.lookup('foo')
        self.assertEqual(found_method, method)

    def test_lookup_ordering(self):
        method_foo = mock.Mock()
        method_bar = mock.Mock()
        method_all = mock.Mock()
        self.map._map = [
            (re.compile(r'^foo$'), method_foo),
            (re.compile(r'^foo\.bar$'), method_bar),
            (re.compile(r''), method_all)
        ]
        found_method, match = self.map.lookup('foo')
        self.assertEqual(found_method, method_foo)
        found_method, match = self.map.lookup('foo.bar')
        self.assertEqual(found_method, method_bar)
        found_method, match = self.map.lookup('')
        self.assertEqual(found_method, method_all)
        self.map._map = [
            (re.compile(r''), method_all),
            (re.compile(r'^foo$'), method_foo),
            (re.compile(r'^foo\.bar$'), method_bar)
        ]
        found_method, match = self.map.lookup('foo')
        self.assertEqual(found_method, method_all)
        found_method, match = self.map.lookup('foo.bar')
        self.assertEqual(found_method, method_all)

    def test_lookup_failed(self):
        with self.assertRaises(KeyError):
            self.map.lookup('foo')

    def test_lookup_assertions(self):
        with self.assertRaises(AssertionError):
            self.map.lookup(0)

    def test_apply(self):
        method = mock.Mock()
        method.return_value = 'bar'
        self.map._map = [
            (re.compile('^foo$'), method)
        ]
        result = self.map.apply('foo')
        self.assertEqual(result, 'bar')

    def test_apply_failed(self):
        with self.assertRaises(KeyError):
            self.map.apply('foo')

    def test_apply_assertions(self):
        with self.assertRaises(AssertionError):
            self.map.apply(0)


class DecorationTestCase(unittest.TestCase):

    class FancilyDecoratedGuy(object):
        _my_map = PatternMethodMap()

        def apply(self, name):
            return self._my_map.apply(name, context_self=self)

        @_my_map.decorate('^foo$')
        def foo(self, name, match):
            return True

    def test_fancy_decoration(self):
        guy = self.FancilyDecoratedGuy()
        self.assertTrue(guy.apply('foo'))
