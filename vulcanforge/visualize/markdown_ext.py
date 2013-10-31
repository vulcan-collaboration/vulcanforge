# -*- coding: utf-8 -*-
import logging

from pylons import app_globals as g
import markdown

from vulcanforge.config.render.markdown_ext.mdx_stash import StashPattern

LOG = logging.getLogger(__name__)

# match in the form ^[vV](Resource Url)(Visualizer Height)
_POSTFIX = r'\(([^\)]*)\)(?:\(([^\)]*)\))?'
SIMPLE_VISUALIZER_RE = r'\^v' + _POSTFIX
FULL_VISUALIZER_RE = r'\^V' + _POSTFIX


class VisualizerPattern(StashPattern, markdown.inlinepatterns.LinkPattern):
    """embed a visualizer in markdown!"""
    pattern = SIMPLE_VISUALIZER_RE

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
        resource_url = mo.group(2).strip()
        shortname, height = self.parseArgs(mo.group(3))
        return self.display(resource_url, shortname, height=height)

    def display(self, resource_url, shortname=None, **kwargs):
        return g.visualize.render_url(resource_url, shortname, **kwargs)


class FullVisualizerPattern(VisualizerPattern):
    pattern = FULL_VISUALIZER_RE

    def display(self, resource_url, shortname=None, **kwargs):
        if shortname:
            shortnames = ','.split(shortname)
        else:
            shortnames = None
        return g.visualize.full_render_url(resource_url, shortnames, **kwargs)
