# -*- coding: utf-8 -*-
import logging
import random
import string

import markdown
from markdown.util import etree

from vulcanforge.visualize.model import Visualizer


LOG = logging.getLogger(__name__)

# ^v(Resource Url)(Visualizer Height)
VISUALIZER_RE = r'\^v' + r'\(([^\)]*)\)' + r'(?:\(([^\)]*)\))?'


class StashPattern(markdown.inlinepatterns.Pattern):
    """
    Used to insert a placeholder for a pattern, then sub another value in after
    the rest of the patterns have been run. The purpose of this is to prevent
    corruption by other patterns or processors in the markdown stack.

    """

    pattern = None

    def __init__(self, parent, pattern=None, markdown_instance=None,
                 id_tag=None):
        self.parent = parent
        self.counter = 0
        self.id_tag = id_tag
        if pattern is None and self.pattern:
            pattern = self.pattern
        if self.id_tag is None:
            self.id_tag = '^' + ''.join(
                random.sample(string.ascii_uppercase, 8))
        markdown.inlinepatterns.Pattern.__init__(
            self, pattern, markdown_instance=markdown_instance)

    def handleMatch(self, mo):
        converted = self.convertPattern(mo)
        if converted:
            placeholder = '%s^%d^%s' % (self.id_tag, self.counter, self.id_tag)
            self.counter += 1
            self.parent.register_match(placeholder, converted)
            return placeholder

    def convertPattern(self, mo):
        raise NotImplementedError('Stash Pattern is a base class, dummy')


class VisualizerPattern(StashPattern, markdown.inlinepatterns.LinkPattern):
    """embed a visualizer in markdown!"""
    pattern = VISUALIZER_RE

    def parseArgs(self, group):
        shortname, height = None, None
        if group:
            args = group.strip().split()
            if len(args) == 1:
                try:
                    height = int(args[0])
                except ValueError:
                    shortname = args[0]
            else:
                shortname, height = args
                height = int(height)
        return shortname, height

    def convertPattern(self, mo):
        from vulcanforge.visualize.widgets.visualize import UrlEmbedVisualizer
        embed_visualizer_widget = UrlEmbedVisualizer()
        resource_url = mo.group(2).strip()
        shortname, height = self.parseArgs(mo.group(3))
        if shortname:
            visualizer = Visualizer.query.get(shortname=shortname)
        else:
            visualizer = None

        return embed_visualizer_widget.display(
            value=resource_url,
            visualizer=visualizer,
            height=height
        )


class SimpleVisualizer(VisualizerPattern):
    """used to embed a visualizer w/o the toolbar"""
    def convertPattern(self, mo):
        resource_url = mo.group(2).strip()
        shortname, height = self.parseArgs(mo.group(3))
        if shortname:
            visualizer = Visualizer.query.get(shortname=shortname)
        else:
            try:
                visualizer = Visualizer.get_for_resource(
                    resource_url,
                    context="markdown"
                )[0]
            except IndexError:
                visualizer = None
        if visualizer:
            result = etree.Element('iframe')
            raw = '/visualize/%s/src/?resource_url=%s?format=raw&mode=embed'
            src = raw.format(
                str(visualizer._id), self.sanitize_url(resource_url))
            result.set('class', 'visualizerContainer')
            result.set('src', src)
            if height:
                result.set('style', 'height:%dpx' % height)
            result.append(
                etree.Element('p', text="Please enable iframes on your browser "
                                        "to view this resource")
            )
        else:
            # turn it into a link if there are no visualizers
            result = etree.Element("a")
            result.text = resource_url
            result.set("href", self.sanitize_url(resource_url))

        return etree.tostring(result, 'utf-8')


class StashProcessor(object):
    """coordinates stash pattern and stash postprocessor"""
    def __init__(self, markdown=None, patterns=None, pattern_kwargs=None,
                 pattern_locations=None):
        self.markdown = markdown
        self.patterns = patterns or {}
        self.pattern_kwargs = pattern_kwargs or {}
        self.pattern_locations = pattern_locations or {}
        self.postprocessor = StashPostProcessor(
            markdown_instance=self.markdown)

    def install(self):
        # currently only inline patterns allowed
        for k, pattern_cls in self.patterns.iteritems():
            kwargs = self.pattern_kwargs.get(k, {})
            pattern = pattern_cls(parent=self, markdown_instance=self.markdown,
                                  **kwargs)
            location = self.pattern_locations.get(k, '_end')
            self.markdown.inlinePatterns.add(k, pattern, location)
        self.markdown.postprocessors['stashpost'] = self.postprocessor

    def register_match(self, placeholder, converted):
        self.postprocessor.store_match(placeholder, converted)


class StashPostProcessor(markdown.postprocessors.Postprocessor):

    def __init__(self, *args, **kwargs):
        self.store = {}
        markdown.postprocessors.Postprocessor.__init__(self, *args, **kwargs)

    def store_match(self, placeholder, converted):
        self.store[placeholder] = converted

    def run(self, text):
        # NOTE: make this more efficient someday
        for placeholder, converted in self.store.iteritems():
            text = text.replace(placeholder, converted)
        return text
