# -*- coding: utf-8 -*-

"""
cache

@author: U{tannern<tannern@gmail.com>}
"""
from pylons import app_globals as g
#import tg

from vulcanforge.command import base


class CleanupForApplicationStart(base.Command):
    min_args = 1
    max_args = 1
    usage = '<ini file>'
    summary = 'Cleans special application caches after a restart.'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        if g.cache and hasattr(g.cache, 'redis'):
            g.cache.redis.expire('navdata', 0)
