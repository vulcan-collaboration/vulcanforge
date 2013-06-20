# -*- coding: utf-8 -*-

"""
authorization

@author: U{tannern<tannern@gmail.com>}
"""
from vulcanforge.websocket.exceptions import NotAuthorized


class MessageAuthorizer(object):

    def authorize(self, listen_channels=None, publish_channels=None,
                  event_targets=None):
        if listen_channels:
            self.auth_listen(listen_channels)
        if publish_channels:
            self.auth_publish(publish_channels)
        if event_targets:
            self.auth_targets(event_targets)

    def fail(self, message=None):
        raise NotAuthorized(message or "Failed authorization")

    def auth_listen(self, channels):
        pass

    def auth_publish(self, channels):
        pass

    def auth_targets(self, targets):
        pass
