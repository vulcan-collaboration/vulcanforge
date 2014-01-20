# -*- coding: utf-8 -*-

"""
mapping

@author: U{tannern<tannern@gmail.com>}
"""
import unittest
from vulcanforge.common.util.mapping import PatternValueMap


class PatternValueMapTestCase(unittest.TestCase):

    def test_basic_use_case(self):
        self.pattern_map = PatternValueMap()

        self.pattern_map.register(r'^a', 'A')
        self.pattern_map.register(r'a$', 'A')

        self.pattern_map.register(r'^b', 'B')
        self.pattern_map.register(r'b$', 'B')

        self.pattern_map.register(r'^a.*', 'A or B')
        self.pattern_map.register(r'.*b$', 'A or B')

        self.assertEqual(self.pattern_map.lookup('a'), {'A', 'A or B'})
        self.assertEqual(self.pattern_map.lookup('b'), {'B', 'A or B'})
        self.assertEqual(self.pattern_map.lookup('ab'), {'A', 'B', 'A or B'})
        self.assertEqual(self.pattern_map.lookup('ba'), {'A', 'B'})


if __name__ == '__main__':
    unittest.main()
