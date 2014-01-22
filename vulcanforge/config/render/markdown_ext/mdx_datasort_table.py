# -*- coding: utf-8 -*-

"""
mdx_forge_tables

@author: U{tannern<tannern@gmail.com>}
"""
import re
from markdown import Extension
from markdown.extensions.tables import TableProcessor
from markdown.util import etree


class DataSortTableProcessor(TableProcessor):
    """ Process Tables. """

    identifier_row_pattern = re.compile(r'\|?-data-\|?')

    def test(self, parent, block):
        rows = block.split('\n')
        return (
            len(rows) > 3 and
            self.identifier_row_pattern.match(rows[0]) and
            '|' in rows[1] and
            '|' in rows[2] and
            '-' in rows[2] and
            rows[2].strip()[0] in ['|', ':', '-']
        )

    def run(self, parent, blocks):
        """ Parse a table block and build table. """
        block = blocks.pop(0).split('\n')
        header = block[1].strip()
        seperator = block[2].strip()
        rows = block[3:]
        # Get format type (bordered by pipes or not)
        border = False
        if header.startswith('|'):
            border = True
        # Get alignment of columns
        align = []
        for c in self._split_row(seperator, border):
            if c.startswith(':') and c.endswith(':'):
                align.append('center')
            elif c.startswith(':'):
                align.append('left')
            elif c.endswith(':'):
                align.append('right')
            else:
                align.append(None)
        # Build table
        table = etree.SubElement(parent, 'table')
        table.set('class', 'datasort-table')
        thead = etree.SubElement(table, 'thead')
        self._build_row(header, thead, align, border)
        tbody = etree.SubElement(table, 'tbody')
        for row in rows:
            self._build_row(row.strip(), tbody, align, border)


class DataSortTableExtension(Extension):
    """ Add tables to Markdown. """

    def extendMarkdown(self, md, md_globals):
        """ Add an instance of TableProcessor to BlockParser. """
        md.parser.blockprocessors.add('datasort-table',
                                      DataSortTableProcessor(md.parser),
                                      '<hashheader')


def makeExtension(configs={}):
    return DataSortTableExtension(configs=configs)
