# -*- coding: utf-8 -*-

"""
diff

@author: U{tannern<tannern@gmail.com>}
"""

import unittest

from vulcanforge.common.util.diff import DictDiffCalculator


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


if __name__ == "__main__":
    unittest.main()
