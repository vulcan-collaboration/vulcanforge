# -*- coding: utf-8 -*-

"""
authorization

@author: U{tannern<tannern@gmail.com>}
"""
from vulcanforge.websocket.exceptions import NotAuthorized


class BaseWebSocketAuthBroker(object):

    def __init__(self, environ, config):
        self.config = config
        self.environ = environ

    def authenticate(self):
        #raise NotAuthorized("Unable to authorize request")
        pass

    def authorize(self, listen_channels=None, publish_channels=None,
                  event_targets=None):
        pass

    def fail(self, message=None):
        raise NotAuthorized(message or "Failed authorization")
