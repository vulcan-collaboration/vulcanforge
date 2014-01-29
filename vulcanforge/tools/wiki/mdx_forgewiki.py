# -*- coding: utf-8 -*-
import re
import logging
import StringIO

import markdown
import markdown.blockprocessors
import markdown.preprocessors
import markdown.postprocessors
from markdown.extensions.headerid import slugify, unique, itertext
import markdown.extensions.toc
from markdown.util import etree
from pylons import tmpl_context as c
import pymongo
from webhelpers.html import literal
from vulcanforge.common.util.urls import rebase_url
from vulcanforge.tools.wiki.model import Page


LOG = logging.getLogger(__name__)


# Processors


class WikiPageIncludePreprocessor(markdown.preprocessors.Preprocessor):
    """
    format:

        [[include Other Page Title]]

    A little hackish but it requires that c.wikipage is set to remap links.

    Should be registered as first preprocessor.

    TODO: make embeddable in nested blocks
            (i.e. include inside a readmore block)
    """
    include_pattern = re.compile(r'^[ ]{0,3}\[\[include +([^\]]+)]]\s*$')
    not_found_template = u'> *\[\[include {}\]\]: Page not found.*'

    def __init__(self, markdown_instance=None, extension=None):
        super(WikiPageIncludePreprocessor, self).__init__(markdown_instance)
        self.extension = extension

    def run(self, lines):
        # skip running if someone forgot to set the wikipage
        page = getattr(c, 'wikipage', False)
        if not page:
            return lines
        page_class = page.query.mapped_class
        page_title = page.title.strip()
        # include pages
        context_stack = []
        line_cursor = 0
        while line_cursor < len(lines):
            line = lines[line_cursor]
            # pop the context
            if line == self.extension.include_end and len(context_stack):
                context_stack.pop()

            include_match = self.include_pattern.match(line)
            if include_match is None:
                line_cursor += 1
                continue
            lines.pop(line_cursor)  # remove the include tag

            # find the requested page
            include_title = include_match.group(1).strip()
            if include_title == page_title or include_title in context_stack:
                continue
            include_page = page_class.query.get(
                app_config_id=page.app_config_id,
                title=include_title)
            if include_page is None:
                lines.insert(line_cursor,
                             self.not_found_template.format(include_title))
                line_cursor += 1
                continue
            include_url = include_page.url()
            include_lines = include_page.text.split('\n')

            # insert the included page text (markdown) surrounded by flags for
            # the postprocessor
            new_lines = (
                [self.extension.include_start.format(include_url)] +
                include_lines +
                [self.extension.include_end]
            )
            lines = lines[:line_cursor] + new_lines + lines[line_cursor:]
            # push the context
            context_stack.append(include_title)

        return lines


class WikiPageIncludePostprocessor(markdown.postprocessors.Postprocessor):
    def __init__(self, markdown_instance=None, extension=None):
        super(WikiPageIncludePostprocessor, self).__init__(markdown_instance)
        self.extension = extension

    def run(self, text):
        """
        Rebase all of the "href" and "src" attributes for included pages.
        """
        # skip running if someone forgot to set the wikipage
        page = getattr(c, 'wikipage', False)
        if not page:
            return text
        page_url = page.url()
        old_text = StringIO.StringIO(text)
        new_text = StringIO.StringIO()
        include_stack = []
        active_buffer = StringIO.StringIO()

        def replace_attr(match):
            attribute_name, url = match.groups()
            new_url = rebase_url(url, include_stack[-1], page_url)
            return u' {}="{}"'.format(attribute_name, new_url)

        def flush_buffer(new_text, buffer):
            buffer.seek(0)
            new_text.write(re.sub(ur' (href|src)="([^"]+)"', replace_attr,
                                  buffer.read()))

        for line in old_text:
            # does line start new context?
            match = self.extension.include_start_pattern.match(line)
            if match is not None:
                content_before, include_title, content_after = match.groups()
                if include_stack:
                    flush_buffer(new_text, active_buffer)
                    active_buffer = StringIO.StringIO()
                include_stack.append(include_title)
                new_text.write(content_before)
                new_text.write(content_after)
                continue
            # does the line end a context?
            match = self.extension.include_end_pattern.match(line)
            if match:
                content_before, content_after = match.groups()
                flush_buffer(new_text, active_buffer)
                active_buffer = StringIO.StringIO()
                include_stack.pop()
                new_text.write(content_before)
                new_text.write(content_after)
                continue
            # are we even in a context?
            if not include_stack:
                new_text.write(line)
                continue
            ## rebase urls for the current context in this line
            #new_text += re.sub(ur' (href|src)="([^"]+)"', replace_attr, line)
            # add the line to the buffer
            active_buffer.write(line)
        new_text.seek(0)
        return literal(new_text.read())


class WikiPageTreeBlockProcessor(markdown.blockprocessors.BlockProcessor):
    """
    Inserts nested UL elements with links to wiki pages along a tree specified.

    Requires `c.app` to be set to an instance of the ForgeWiki tool.

    usage examples:
        {PageTree}              full tree starting at wiki root
        {PageTree My Page}      full tree starting at "My Page"
        {PageTree:2 My Page}    2 level tree starting at "My Page"

    @status: working
    @todo: simplify some of the logic, make it more straight-forward
    """
    regex = re.compile(r'^\{PageTree(?::(\d+))?(?: (.+))?\}$')

    def test(self, parent, block):
        """
        Check the given block to see if it should be processed with `run`
        """
        if not hasattr(c, 'app'):  # ensure proper context
            return False
        m = self.regex.match(block)  # check for match
        if m is None:
            return False
        tree_depth = m.group(1)  # check depth argument type
        if tree_depth is not None:
            try:
                int(tree_depth)
            except ValueError:
                return False
        return True  # nothing failed

    def run(self, parent, blocks):
        """
        Process the remaining blocks of the page
        (only the first has passed `test`)
        """
        block = blocks.pop(0)
        m = self.regex.match(block)
        tree_depth = m.group(1)
        try:  # convert optional depth argument to integer
            tree_depth = int(tree_depth)
        except (ValueError, TypeError):  # fallback to no depth limit
            tree_depth = None
        page_title = m.group(2)
        tree_index = self._get_tree_index(page_title)
        # write markdown for other processors
        if page_title is not None:
            root_depth = tree_index.get_root_node().depth
        else:
            root_depth = 0
        new_block = ""
        for node in tree_index:
            depth = node.depth0 - root_depth
            if tree_depth is not None and depth >= tree_depth or depth < 0:
                continue
            new_block += "{}- [{}]({})\n".format(depth * "    ", node.label,
                                                 node.url)
        blocks.insert(0, new_block)

    def _get_page_query_params(self, **extra_params):
        params = {
            'app_config_id': c.app.config._id,
            'deleted': False
        }
        params.update(**extra_params)
        return params

    def _get_page_cursor(self):
        params = self._get_page_query_params()
        cursor = Page.query.find(params)
        cursor.sort('title', pymongo.ASCENDING)
        return cursor

    def _get_page_cursor_by_pattern(self, pattern):
        params = self._get_page_query_params(title={'$regex': pattern})
        cursor = Page.query.find(params)
        cursor.sort('title', pymongo.ASCENDING)
        return cursor

    def _get_tree_index(self, page_title):
        if page_title is None:
            cursor = self._get_page_cursor()
        else:
            pattern = '^{}/'.format(page_title)
            cursor = self._get_page_cursor_by_pattern(pattern)
        tree_index = WikiPageTreeIndex(page_title)
        tree_index.add_from_page_cursor(cursor)
        return tree_index


class TableOfContentsTreeProcessor(markdown.extensions.toc.TocTreeprocessor):
    config = {}

    # Iterator wrapper to get parent and child all at once
    def iterparent(self, root):
        for parent in root.iter():
            for child in parent:
                yield parent, child

    def run(self, doc):
        """
        @type doc: xml.etree.ElementTree.Element
        """
        toc_div = etree.Element("div")
        toc_div.attrib["class"] = "toc"
        header_rgx = re.compile("[Hh][123456]")

        self.use_anchors = self.config["anchorlink"] in [1, '1', True, 'True',
                                                         'true']

        # Get a list of id attributes
        used_ids = set()
        for element in doc.iter():
            if "id" in element.attrib:
                used_ids.add(element.attrib["id"])

        toc_list = []
        marker_found = False
        header_count = 0
        for (p, element) in self.iterparent(doc):
            text = ''.join(itertext(element))
            text = self.markdown.forge_processor.placeholder_re.sub('', text)
            text = text.strip()
            if not text:
                continue

            # To keep the output from screwing up the
            # validation by putting a <div> inside of a <p>
            # we actually replace the <p> in its entirety.
            # We do not allow the marker inside a header as that
            # would causes an enless loop of placing a new TOC
            # inside previously generated TOC.
            is_marker = (element.text and
                         element.text.strip() == self.config["marker"] and
                         not header_rgx.match(element.tag) and
                         element.tag not in ['pre', 'code'])
            if is_marker:
                for i in range(len(p)):
                    if p[i] == element:
                        p[i] = toc_div
                        break
                marker_found = True

            if header_rgx.match(element.tag):

                # Do not override pre-existing ids
                if not "id" in element.attrib:
                    slug = self.config["slugify"](unicode(text), '-')
                    intended_id = "markdown-header-" + slug
                    elem_id = unique(intended_id, used_ids)
                    element.attrib["id"] = elem_id
                else:
                    elem_id = element.attrib["id"]

                tag_level = int(element.tag[-1])

                toc_list.append({'level': tag_level,
                                 'id': elem_id,
                                 'name': text})

                self.add_anchor(element, elem_id)
                header_count += 1

        toc_list_nested = markdown.extensions.toc.order_toc_list(toc_list)
        self.build_toc_etree(toc_div, toc_list_nested)
        prettify = self.markdown.treeprocessors.get('prettify')
        if prettify:
            prettify.run(toc_div)
        if not marker_found and header_count > 0:
            app = getattr(c, 'app', None)
            show_table_of_contents = getattr(
                app, 'show_table_of_contents', None)
            if show_table_of_contents is not None and show_table_of_contents:
                doc.insert(0, toc_div)


# Extension


class ForgeWikiExtension(markdown.Extension):

    include_start = u'\n¶¶¶begin-include {}¶¶¶\n'
    include_end = u'\n¶¶¶end-include¶¶¶\n'
    include_start_pattern = re.compile(ur'([^¶]*)¶¶¶begin-include (.+)¶¶¶(.*)')
    include_end_pattern = re.compile(ur'([^¶]*)¶¶¶end-include¶¶¶(.*)')

    def extendMarkdown(self, md, md_globals):
        # includes
        include_preprocessor = WikiPageIncludePreprocessor(md, self)
        md.preprocessors.add('forgewiki_include',
                             include_preprocessor,
                             '_begin')
        include_postprocessor = WikiPageIncludePostprocessor(md, self)
        md.postprocessors.add('forgewiki_include',
                              include_postprocessor,
                              '_end')

        # {Table of Contents}
        table_of_contents_config = {
            'marker': '{Table of Contents}',
            'slugify': markdown.extensions.headerid.slugify,
            'title': 'Table of Contents',
            'anchorlink': False
        }
        table_of_contents_tree_processor = TableOfContentsTreeProcessor(md)
        table_of_contents_tree_processor.config = table_of_contents_config
        md.treeprocessors.add('toc', table_of_contents_tree_processor,
                              '<prettify')
        # {PageTree}
        page_tree_block_processor = WikiPageTreeBlockProcessor(md.parser)
        md.parser.blockprocessors.add("forgewiki_pagetree",
                                      page_tree_block_processor, '_begin')


# Types and Utilities


class WikiPageTreeNode(object):
    def __init__(self, title):
        self.title = title
        self.label = self.title.split('/')[-1]
        self.url = '{}{}'.format(c.app.url, title)
        self.title_segments = self.title.split('/')
        self.depth = len(self.title_segments)
        self.depth0 = self.depth - 1
        self.parent_title = '/'.join(self.title_segments[:self.depth0])
        self.children = []

    def iter_ancestor_titles(self):
        for i in range(1, len(self.title_segments)):
            yield '/'.join(self.title_segments[:i])


class WikiPageTreeIndex(object):
    def __init__(self, root_title=None):
        self.root_title = root_title or ''
        self.title_index = {}
        self.nodes = []
        self.add_node(WikiPageTreeNode(self.root_title))

    def __iter__(self):
        for node in self.nodes:
            if node.title is not self.root_title:
                yield node

    def add_node(self, node):
        self.title_index[node.title] = len(self.nodes)
        self.nodes.append(node)
        if not node.title.endswith(node.parent_title):
            parent_node = self.get_by_title(node.parent_title)
            if parent_node is not None:
                parent_node.children.append(node)

    def add_from_page_cursor(self, cursor):
        for page in cursor:
            self.add_from_page(page)

    def add_from_page(self, page):
        node = WikiPageTreeNode(page.title)
        for title in node.iter_ancestor_titles():
            if not self.has_title(title):
                self.add_node(WikiPageTreeNode(title))
        self.add_node(node)

    def has_title(self, title):
        return title in self.title_index

    def get_by_title(self, title):
        try:
            return self.nodes[self.title_index[title]]
        except KeyError:
            return None

    def get_root_node(self):
        return self.nodes[self.title_index[self.root_title]]
