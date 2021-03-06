# -*- coding: utf-8 -*-
import re
import logging
from urlparse import urljoin

from tg import config
from pylons import tmpl_context as c, app_globals as g, request
from BeautifulSoup import BeautifulSoup
from feedparser import _HTMLSanitizer

import bleach
import markdown
from markdown.util import etree
from mdx_oembed import OEmbedExtension
from mdx_oembed.inlinepatterns import OEMBED_LINK_RE, OEmbedLinkPattern
from webhelpers import html
import webhelpers

from vulcanforge.project.model import Project
from vulcanforge.artifact.model import Shortlink
from vulcanforge.artifact.widgets import ArtifactLink
from vulcanforge.common.helpers import urlquote

from . import markdown_macro
from .mdx_stash import StashProcessor, StashPattern
from vulcanforge.visualize.markdown_ext import (
    VisualizerPattern,
    FullVisualizerPattern
)


LOG = logging.getLogger(__name__)
SHORTLINK_PATTERN = r'(?<![\[\\])\[([^\\\]\[]*(?:\\[\[\]\\][^\\\]\[]*)*)\](?![\(])'
ARTIFACT_RE = re.compile(r'((.*?):)?((.*?):)?(.+)')


class ForgeExtension(OEmbedExtension):

    def __init__(self, wiki=False, email=False, macro_context=None,
                 simple_links=None):
        if simple_links is None:
            simple_links = email
        markdown.Extension.__init__(self)
        self._use_wiki = wiki
        self._is_email = email
        self._macro_context = macro_context
        self._simple_links = simple_links

    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        md.preprocessors['fenced-code'] = FencedCodeProcessor()
        md.preprocessors['comments'] = CommentProcessor()
        md.parser.blockprocessors.add('readmore',
                                      ReadMoreProcessor(md.parser),
                                      '<paragraph')
        # Sanitize HTML
        md.postprocessors['sanitize_html'] = SanitizeHTMLWithBleachProcessor()

        # shortlinks, relative urls, etc
        self.forge_processor = ForgeProcessor(
            self._use_wiki, md, macro_context=self._macro_context,
            simple_alinks=self._simple_links
        )
        self.forge_processor.install()

        # oembed media links
        self.oembed_consumer = self.prepare_oembed_consumer()

        # Visualizer Guy (must be after sanitize html and before link eater)
        if not self._simple_links:
            self.stash_processor = StashProcessor(
                markdown=md,
                patterns={
                    'visualizer': VisualizerPattern,
                    'oembed': OEmbedStashedPattern,
                    'full_visualizer': FullVisualizerPattern
                },
                pattern_kwargs={
                    'oembed': {
                        'oembed_consumer': self.oembed_consumer,
                    },
                },
                pattern_locations={
                    'visualizer': '_begin',
                    'oembed': '<image_link',
                }
            )
            self.stash_processor.install()

        md.inlinePatterns['autolink_1'] = AutolinkPattern(
            r'(http(?:s?)://[a-zA-Z0-9./\-_0%?&=+#;~:]+)')

        md.postprocessors['rewrite_relative_links'] = RelativeLinkRewriter(md,
            make_absolute=self._is_email)
        # Put a class around markdown content for custom css
        md.postprocessors['add_custom_class'] = AddCustomClass()
        md.postprocessors['mark_safe'] = MarkAsSafe()

    def reset(self):
        self.forge_processor.reset()


class OEmbedStashedPattern(StashPattern, OEmbedLinkPattern):
    pattern = OEMBED_LINK_RE

    def __init__(self, parent, pattern=None, markdown_instance=None,
                 id_tag=None, oembed_consumer=None):
        StashPattern.__init__(self, parent, pattern=pattern,
                              markdown_instance=markdown_instance,
                              id_tag=id_tag)
        self.consumer = oembed_consumer

    def convertPattern(self, mo):
        html = self.get_oembed_html_for_match(mo)
        if html is not None:
            html = html.replace('http://', 'https://')
        return html


class FencedCodeProcessor(markdown.preprocessors.Preprocessor):
    pattern = '~~~~'

    def run(self, lines):
        in_block = False
        new_lines = []
        for line in lines:
            if line.lstrip().startswith(self.pattern):
                in_block = not in_block
                continue
            if in_block:
                new_lines.append('    ' + line)
            else:
                new_lines.append(line)
        return new_lines


class ForgeProcessor(object):
    alink_pattern = SHORTLINK_PATTERN
    macro_pattern = r'\[(\[([^\]\[]*)\])\]'
    placeholder_prefix = '#jgimwge'
    placeholder = '%s:%%s:%%.4d#khjhhj' % placeholder_prefix
    placeholder_re = re.compile('%s:(\\w+):(\\d+)#khjhhj' % placeholder_prefix, re.UNICODE)

    def __init__(self, use_wiki=False, markdown=None, macro_context=None,
                 simple_alinks=False):
        self.markdown = markdown
        self.markdown.forge_processor = self
        self._use_wiki = use_wiki
        self._macro_context = macro_context
        self._simple_alinks = simple_alinks
        self.inline_patterns = {
            'forge.alink': ForgeInlinePattern(self, self.alink_pattern),
            'forge.macro': ForgeInlinePattern(self, self.macro_pattern)}
        self.postprocessor = ForgePostprocessor(self)
        self.tree_processor = ForgeTreeProcessor(self)
        self.reset()
        self.artifact_re = ARTIFACT_RE
        self.macro_re = re.compile(self.alink_pattern)

        self.artifact_link = ArtifactLink()

    def install(self):
        for k, v in self.inline_patterns.iteritems():
            self.markdown.inlinePatterns[k] = v
        if self._use_wiki:
            self.markdown.treeprocessors['forge'] = self.tree_processor
        self.markdown.postprocessors['forge'] = self.postprocessor

    def store(self, raw):
        if self.macro_re.match(raw):
            stash = 'macro'
            raw = raw[1:-1]  # strip off the enclosing []
        elif self.artifact_re.match(raw):
            stash = 'artifact'
            raw = self._de_escape_link(raw)
        else:
            return raw
        return self._store(stash, raw)

    def _store(self, stash_name, value):
        placeholder = self.placeholder % (
            stash_name,
            len(self.stash[stash_name])
        )
        self.stash[stash_name].append(value)
        return placeholder

    def lookup(self, stash, id):
        stash = self.stash.get(stash, [])
        if id >= len(stash):
            return ''
        return stash[id]

    def compile(self):
        if self.stash['artifact'] or self.stash['link']:
            self.alinks = Shortlink.from_links(*self.stash['artifact'])
            self.alinks.update(Shortlink.from_links(*self.stash['link']))
        self.stash['artifact'] = map(self._expand_alink,
                                     self.stash['artifact'])
        self.stash['link'] = map(self._expand_link, self.stash['link'])
        self.stash['macro'] = map(markdown_macro.parse(self._macro_context),
                                  self.stash['macro'])

    def reset(self):
        self.stash = dict(
            artifact=[],
            macro=[],
            link=[])
        self.alinks = {}
        self.compiled = False

    def _de_escape_link(self, link):
        return link.replace("\\]", "]").replace("\\[", "[").replace("\\\\", "\\")

    def _expand_alink(self, link):
        # try to find an artifact reference
        new_link = self.alinks.get(link, None)
        if new_link:
            link_html = None
            if not self._simple_alinks:
                artifact = g.artifact.get_artifact_by_index_id(
                    new_link.ref_id)
                try:
                    link_html = self.artifact_link.display(
                        value=artifact, tag="span")
                except Exception:  # pragma no cover
                    # shortlink without artifact reference?
                    LOG.exception("Error rendering artifact link")
            if not link_html:
                link_html = u'<a href="%s">[%s]</a>' % (new_link.url, link)
            return link_html

        # if we're on a wiki then link to a non-existant page
        if self._use_wiki and u':' not in link:
            utf_link = unicode(link).encode('utf-8')
            return '<a href="{}" class="notfound">[{}]</a>'.format(
                urlquote(utf_link), utf_link)

        ###
        parts = link.split(':')
        url_method = None
        project_cls = g.context_manager.get_project_cls()
        project = project_cls.by_shortname(parts[0])
        if project:
            parts.pop(0)
        else:
            project = getattr(c, 'project', None)
        if project:
            url_method = project.url
            if len(parts):
                app_config = project.app_config(parts[0])
                if app_config:
                    url_method = app_config.url
        if callable(url_method):
            return u'<a href="{}" class="notfound">[{}]</a>'.format(
                url_method(), link)
        ###

        # fallback is to print the link as it was formatted
        return u"[{}]".format(link)

    def _expand_link(self, link):
        if link.startswith('#'):
            return
        reference = self.alinks.get(link)
        if not reference:
            return 'notfound'
        else:
            return ''


class ForgeInlinePattern(markdown.inlinepatterns.Pattern):

    def __init__(self, parent, pattern):
        self.parent = parent
        markdown.inlinepatterns.Pattern.__init__(
            self, pattern, parent.markdown)

    def handleMatch(self, m):
        return self.parent.store(m.group(2))


class ForgePostprocessor(markdown.postprocessors.Postprocessor):

    def __init__(self, parent):
        self.parent = parent
        markdown.postprocessors.Postprocessor.__init__(
            self, parent.markdown)

    def run(self, text):
        self.parent.compile()

        def repl(mo):
            item = self.parent.lookup(mo.group(1), int(mo.group(2)))
            if isinstance(item,str):
                item = item.decode('utf-8')

            return item

        return self.parent.placeholder_re.sub(repl, text)


class ForgeTreeProcessor(markdown.treeprocessors.Treeprocessor):
    '''This flags intra-wiki links that point to non-existent pages'''

    def __init__(self, parent):
        self.parent = parent

    def run(self, root):
        for node in root.getiterator('a'):
            href = node.get('href')
            if not href:
                continue
            if '/' in href:
                continue
            classes = (node.get('class', '').split() +
                       [self.parent._store('link', href)])
            node.attrib['class'] = ' '.join(classes)
        return root


class MarkAsSafe(markdown.postprocessors.Postprocessor):

    def run(self, text):
        return webhelpers.html.literal(text)


class AddCustomClass(markdown.postprocessors.Postprocessor):

    def run(self, text):
        return '<div class="markdown_content">%s</div>' % text


class RelativeLinkRewriter(markdown.postprocessors.Postprocessor):

    def __init__(self, md, make_absolute=False):
        super(RelativeLinkRewriter, self).__init__(markdown_instance=md)
        self._make_absolute = make_absolute

    def run(self, text):
        try:
            if not request.path_info.endswith('/'):
                return text
        except Exception:
            # Must be being called outside the request context
            pass
        soup = BeautifulSoup(text)
        if self._make_absolute:
            rewrite = self._rewrite_abs
        else:
            rewrite = self._rewrite
        for link in soup.findAll('a'):
            rewrite(link, 'href')
        for link in soup.findAll('img'):
            rewrite(link, 'src')
        return unicode(soup)

    def _rewrite(self, tag, attr):
        val = tag.get(attr)
        if val is None:
            return
        if ' ' in val:
            # Don't urllib.quote to avoid possible double-quoting
            # just make sure no spaces
            val = val.replace(' ', '%20')
            tag[attr] = val
        if '://' in val:
            return
            # if 'base_url' in config and config['base_url'] in val:
            #     return
            # else:
            #     tag[attr] = '/nf/redirect/?path=%s' % urlquote(val)
            #     tag['rel'] = 'nofollow'
            #     return
        if val.startswith('/') or val.startswith('.') or val.startswith('#'):
            return
        tag[attr] = '../' + val

    def _rewrite_abs(self, tag, attr):
        self._rewrite(tag, attr)
        val = tag.get(attr)
        base_url = config.get('base_url')
        if base_url:
            val = urljoin(base_url, val)
        tag[attr] = val


class ForgeHTMLSanitizer(_HTMLSanitizer):
    acceptable_elements = _HTMLSanitizer.acceptable_elements.\
        difference({'form', 'noscript', 'sound'})

    acceptable_attributes = _HTMLSanitizer.acceptable_attributes.\
        difference({'action', 'method'})

    def __init__(self, encoding, _type=''):
        try:
            _HTMLSanitizer.__init__(self, encoding)
        except TypeError:
            _HTMLSanitizer.__init__(self, encoding, _type)


class SanitizeHTMLProcessor(markdown.postprocessors.Postprocessor):

    def run(self, text):
        sanitizer = ForgeHTMLSanitizer('utf-8')
        sanitizer.feed(text.encode('utf-8'))
        return unicode(sanitizer.output(), 'utf-8')


class SanitizeHTMLWithBleachProcessor(markdown.postprocessors.Postprocessor):
    """ Sanitize the markdown output with bleach. """

    def __init__(self):
        vf_tags = bleach.ALLOWED_TAGS + [
            'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'img', 'p', 'pre',
            'div', 'span', 'table', 'th', 'td', 'tr', 'thead', 'tbody'
        ]
        vf_attr = {'a': ['href', 'title', 'class'],
                   'img': ['src', 'title', 'alt', 'width'],
                   'div': ['class'],
                   'td': ['align'],
                   'table': ['class']}
        self.tags = vf_tags
        self.attributes = vf_attr
        self.protocols = bleach.ALLOWED_PROTOCOLS
        self.styles = bleach.ALLOWED_STYLES
        self.strip = True
        self.strip_comments = True

    def run(self, text):
        """ Sanitize the markdown output. """
        return bleach.clean(text,
                            tags=self.tags,
                            attributes=self.attributes,
                            styles=self.styles,
                            protocols=self.protocols,
                            strip=self.strip,
                            strip_comments=self.strip_comments
        )


class AutolinkPattern(markdown.inlinepatterns.LinkPattern):
    def handleMatch(self, mo):
        old_link = mo.group(2)
        result = etree.Element('a')
        result.text = old_link
        result.set('href', old_link)
        return result


class ReadMoreProcessor(markdown.blockprocessors.BlockProcessor):

    css_class = "md-read-more"
    md_prefix = r'//'
    RE = re.compile(r'(?:^|\n)[ ]{0,3}' + md_prefix + r'(::)? (.*)')

    def test(self, parent, block):
        return bool(self.RE.search(block))

    def run(self, parent, blocks):
        block = blocks.pop(0)
        m = self.RE.search(block)
        start = m.start()
        label = None
        if m:
            before = block[:start]
            self.parser.parseBlocks(parent, [before])
            block_buffer = []
            for line in block[start:].split('\n'):
                m = self.RE.match(line)
                stripped = line.strip()
                if stripped == self.md_prefix:
                    block_buffer.append("")
                elif m is None:
                    block_buffer.append(line)
                else:
                    prefix, content = m.groups()
                    if prefix is not None:
                        label = label or content
                    else:
                        block_buffer.append(content)
            block = '\n'.join(block_buffer)
        sibling = self.lastChild(parent)
        if (
            getattr(sibling, 'tag', None) == "div" and
            sibling.attrib.get('class', None) == self.css_class
        ):
            element = sibling
        else:
            element = markdown.util.etree.SubElement(parent, 'div')
            element.set('class', self.css_class)
        if label is not None:
            LOG.info('setting label')
            element.set('title', label)
        self.parser.parseChunk(element, block)


class CommentProcessor(markdown.preprocessors.Preprocessor):
    """
    This preprocessor removes comments of the form /*...*/
    If a line contains only a comment, it is removed.  Otherwise,
    what remains on a line after removing all comments is preserved.
    
    It uses a greedy regular expression.  Otherwise a line
    "/* comment1 */ Hello /* comment2 */" would be completely filtered.
    
    Limitations:
    1. No nesting: "/* Blah /* nested */ Blah2 */" returns a line " Blah2 */"
    """
    RE = re.compile(r'/\*.*?\*/')

    def run(self, lines):
        new_lines = []
        for line in lines:
            revised, count = self.RE.subn('', line)
            if count and revised:
                new_lines.append(revised)
            elif not count:
                new_lines.append(line)
        return new_lines
