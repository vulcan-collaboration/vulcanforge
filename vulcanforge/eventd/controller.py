# -*- coding: utf-8 -*-

"""
event

@author: U{tannern<tannern@gmail.com>}
"""


import logging
from pylons import tmpl_context as c, app_globals as g
LOG = logging.getLogger(__name__)


class EventController(object):

    def __call__(self, environ, start_response):
        c.neighborhood = c.project = c.app = None
        c.memoize_cache = {}
        c.user = g.auth_provider.authenticate_request()
        assert c.user is not None, \
            'c.user should always be at least User.anonymous()'
        event_type = environ['event.type']
        targets = environ['event.targets']
        params = environ['event.params']
        handler = environ['event.handler']
        result = handler(event_type, targets, params)
        start_response('200 OK', [])
        return [True]
