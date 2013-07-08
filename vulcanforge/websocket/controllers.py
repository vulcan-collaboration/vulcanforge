# -*- coding: utf-8 -*-

"""
controllers

@author: U{tannern<tannern@gmail.com>}
"""
import json
import logging
from pylons import tmpl_context as c, request
from tg import expose
from vulcanforge.auth.model import User
from vulcanforge.common.controllers import BaseController
from vulcanforge.websocket.authorizer import WebSocketAuthorizer
from vulcanforge.websocket.exceptions import NotAuthorized


LOG = logging.getLogger(__name__)


class WebSocketAPIController(BaseController):

    def __init__(self):
        self._authorizer = WebSocketAuthorizer()

    @expose('json')
    def authenticate(self, **kwargs):
        if c.user == User.anonymous():
            authenticated = False
        elif c.user.active():
            authenticated = True
        else:
            authenticated = False
        return {
            'authenticated': authenticated,
            'user_id': str(c.user._id)
        }

    @expose('json')
    def authorize(self, **kwargs):
        try:
            data = json.loads(request.body)
            listen_channels = data.get('listen_channels')
            publish_channels = data.get('publish_channels')
            event_targets = data.get('event_targets')
            if listen_channels:
                self._auth_listen(listen_channels)
            if publish_channels:
                self._auth_publish(publish_channels)
            if event_targets:
                self._auth_targets(event_targets)
        except NotAuthorized:
            authorized = False
        except:
            raise
        else:
            authorized = True
        return {
            'authorized': authorized
        }

    def _auth_listen(self, listen_channels):
        for channel in listen_channels:
            self._authorizer.can_listen(channel)

    def _auth_publish(self, publish_channels):
        for channel in publish_channels:
            self._authorizer.can_publish(channel)

    def _auth_targets(self, event_targets):
        for target in event_targets:
            self._authorizer.can_trigger(target)
