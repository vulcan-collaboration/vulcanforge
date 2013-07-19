# -*- coding: utf-8 -*-
import re
import logging
from urllib import quote
from urlparse import urljoin

from tg import config
from pylons import tmpl_context as c, request
from BeautifulSoup import BeautifulSoup
import feedparser

import markdown
from markdown.util import etree
from mdx_oembed import OEmbedExtension
from mdx_oembed.inlinepatterns import OEMBED_LINK_RE, OEmbedLinkPattern
from webhelpers import html
import webhelpers
from vulcanforge.config.markdown_ext import markdown_macro

from vulcanforge.project.model import Project
from vulcanforge.artifact.model import Shortlink, ArtifactReference
from vulcanforge.artifact.widgets import ArtifactLink

from .mdx_visualizer import StashProcessor, VisualizerPattern, StashPattern


LOG = logging.getLogger(__name__)
SHORTLINK_PATTERN = r'(?<![\[])\[([^\]\[]*)\]'
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
        md.parser.blockprocessors.add('readmore',
                                      ReadMoreProcessor(md.parser),
                                      '<paragraph')
        md.treeprocessors['br'] = LineOrientedTreeProcessor(md)

        # Sanitize HTML
        md.postprocessors['sanitize_html'] = HTMLSanitizer()

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
    placeholder_re = re.compile('%s:(\\w+):(\\d+)#khjhhj' % placeholder_prefix)

    def __init__(self, use_wiki=False, markdown=None, macro_context=None,
                 simple_alinks=False):
        self.markdown = markdown
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

    def _expand_alink(self, link):
        # try to find an artifact reference
        new_link = self.alinks.get(link, None)
        if new_link:
            link_html = None
            if not self._simple_alinks:
                artifact = ArtifactReference.artifact_by_index_id(
                    new_link.ref_id)
                try:
                    link_html = self.artifact_link.display(
                        value=artifact, tag="span")
                except Exception:  # pragma no cover
                    LOG.exception("Error rendering artifact link")
            if not link_html:
                link_html = '<a href="%s">[%s]</a>' % (new_link.url, link)
            return link_html

        # if we're on a wiki then link to a non-existant page
        if self._use_wiki and ':' not in link:
            return '<a href="{}" class="notfound">[{}]</a>'.format(
                quote(link), link)

        ###
        parts = link.split(':')
        url_method = None
        project = Project.query.get(shortname=parts[0])
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
            return '<a href="{}" class="notfound">[{}]</a>'.format(
                url_method(), link)
        ###

        # fallback is to print the link as it was formatted
        return "[{}]".format(link)

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
            return self.parent.lookup(mo.group(1), int(mo.group(2)))

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
            if 'base_url' in config and config['base_url'] in val:
                return
            else:
                tag[attr] = '/nf/redirect/?path=%s' % quote(val)
                tag['rel'] = 'nofollow'
                return
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


class HTMLSanitizer(markdown.postprocessors.Postprocessor):

    def run(self, text):
        try:
            p = feedparser._HTMLSanitizer('utf-8')
        except TypeError:  # $@%## pre-released versions from SOG
            p = feedparser._HTMLSanitizer('utf-8', '')

        p.feed(text.encode('utf-8'))
        return unicode(p.output(), 'utf-8')


class LineOrientedTreeProcessor(markdown.treeprocessors.Treeprocessor):
    """Once MD is satisfied with the etree, this runs to replace \n with <br/>
    within <p>s.
    """

    # TODO: tanner: fix call to superclass
    def __init__(self, md):
        self._markdown = md

    def run(self, root):
        for node in root.getiterator('p'):
            if not node.text:
                continue
            if '\n' not in node.text:
                continue
            text = self._markdown.serializer(node)
            text = self._markdown.postprocessors['raw_html'].run(text)
            text = text.strip().encode('utf-8')
            if '\n' not in text:
                continue
            new_text = (text
                        .replace('<br>', '<br/>')
                        .replace('\n', '<br/>'))
            new_node = None
            try:
                new_node = etree.fromstring(new_text)
            except SyntaxError:
                try:
                    new_node = etree.fromstring(
                        unicode(BeautifulSoup(new_text)))
                except Exception:
                    #log.exception(
                    #    'Error adding <br> tags: new text is %s', new_text)
                    pass
            if new_node:
                node.clear()
                node.text = new_node.text
                node[:] = list(new_node)
        return root


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
    RE = re.compile(r'(^|\n)[ ]{0,3}' + md_prefix + r' ?(.*)')

    def test(self, parent, block):
        return bool(self.RE.search(block))

    def run(self, parent, blocks):
        block = blocks.pop(0)
        m = self.RE.search(block)
        start = m.start()
        if m:
            before = block[:start]
            self.parser.parseBlocks(parent, [before])
            block = '\n'.join([self.clean(line)for line in
                              block[start:].split('\n')])
        sibling = self.lastChild(parent)
        if sibling and sibling.tag == "div" \
                and sibling.attrib.get('class', None) == self.css_class:
            element = sibling
        else:
            element = markdown.util.etree.SubElement(parent, 'div')
            element.set('class', self.css_class)
        self.parser.parseChunk(element, block)

    def clean(self, line):
        m = self.RE.match(line)
        if line.strip() == self.md_prefix:
            return ""
        elif m:
            return m.group(2)
        else:
            return line
