# -*- coding: utf-8 -*-

"""
diff

@author: U{tannern<tannern@gmail.com>}
"""

import unittest

from vulcanforge.common.util.diff import DictDiffCalculator


class DictDifferHasKeyChangedTestCase(unittest.TestCase):
    def test_same(self):
        a = {'a': 1}
        b = {'a': 1}
        differ = DictDiffCalculator(a, b)
        self.assertFalse(differ.get_has_key_changed('a'))

    def test_same_nested(self):
        a = {'a': {'b': 0}}
        b = {'a': {'b': 0}}
        differ = DictDiffCalculator(a, b)
        self.assertFalse(differ.get_has_key_changed('a', 'b'))

    def test_changed(self):
        a = {'a': 1}
        b = {'a': 2}
        differ = DictDiffCalculator(a, b)
        self.assertTrue(differ.get_has_key_changed('a'))

    def test_changed_nested(self):
        a = {'a': {'b': 0}}
        b = {'a': {'b': 1}}
        differ = DictDiffCalculator(a, b)
        self.assertTrue(differ.get_has_key_changed('a'))
        differ = DictDiffCalculator(a, b)
        self.assertTrue(differ.get_has_key_changed('a', 'b'))

    def test_changed_list(self):
        a = {'a': [0]}
        b = {'a': [1]}
        differ = DictDiffCalculator(a, b)
        self.assertTrue(differ.get_has_key_changed('a'))
        differ = DictDiffCalculator(a, b)
        self.assertTrue(differ.get_has_key_changed('a', 0))
        a = {'a': [0, 1]}
        b = {'a': [0, 1, 2]}
        differ = DictDiffCalculator(a, b)
        self.assertTrue(differ.get_has_key_changed('a'))
        differ = DictDiffCalculator(a, b)
        self.assertTrue(differ.get_has_key_changed('a', 2))


class DictDifferChangedKeysTestCase(unittest.TestCase):
    def test_empty_same(self):
        a = {}
        b = {}
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, set())

    def test_nested_same(self):
        a = {'a': {'b': 0}}
        b = {'a': {'b': 0}}
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, set())

    def test_new_key(self):
        a = {}
        b = {'a': 0}
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, {'a'})

    def test_removed_key(self):
        a = {'a': 0}
        b = {}
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, {'a'})

    def test_changed_value(self):
        a = {'a': 0}
        b = {'a': 1}
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, {'a'})

    def test_new_nested_key(self):
        a = {
            'a': {}
        }
        b = {
            'a': {
                'b': 0
            }
        }
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, {'a', 'a.b'})

    def test_removed_nested_key(self):
        a = {
            'a': {
                'b': 0
            }
        }
        b = {
            'a': {}
        }
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, {'a', 'a.b'})

    def test_changed_nested_value(self):
        a = {
            'a': {
                'b': 0
            }
        }
        b = {
            'a': {
                'b': 1
            }
        }
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, {'a', 'a.b'})

    def test_changed_list_same(self):
        a = {
            'a': [1]
        }
        b = {
            'a': [1]
        }
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, set([]))

    def test_changed_list_changed(self):
        a = {
            'a': []
        }
        b = {
            'a': [1]
        }
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, {'a', 'a.0'})

    def test_changed_dict_in_list_same(self):
        a = {
            'a': [
                {'b': 0}
            ]
        }
        b = {
            'a': [
                {'b': 0}
            ]
        }
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, set([]))

    def test_changed_dict_in_list_changed(self):
        a = {
            'a': [
                {'b': 0}
            ]
        }
        b = {
            'a': [
                {'b': 1}
            ]
        }
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, {'a', 'a.0', 'a.0.b'})

    def test_changed_dict_to_list(self):
        a = {
            'a': {'b': 0}
        }
        b = {
            'a': [
                {'b': 1}
            ]
        }
        differ = DictDiffCalculator(a, b)
        changed_keys = differ.get_changed_keys()
        self.assertEqual(changed_keys, {'a'})


if __name__ == "__main__":
    unittest.main()
