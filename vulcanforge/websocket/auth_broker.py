# -*- coding: utf-8 -*-

"""
authorization

@author: U{tannern<tannern@gmail.com>}
"""
import json
import requests
from webob import Request
from vulcanforge.common.exceptions import ImproperlyConfigured
from vulcanforge.websocket.exceptions import NotAuthorized, NotAuthenticated


import logging
LOG = logging.getLogger(__name__)


class BaseWebSocketAuthBroker(object):

    def __init__(self, environ, config):
        self.config = config
        self.environ = environ

    def authenticate(self):
        #raise NotAuthenticated("Unable to authenticate request")
        pass

    def authorize(self, listen_channels=None, publish_channels=None,
                  event_targets=None):
        pass

    def fail(self, message=None):
        raise NotAuthorized(message or "Failed authorization")


class WebSocketAuthBroker(BaseWebSocketAuthBroker):

    def __init__(self, environ, config):
        super(WebSocketAuthBroker, self).__init__(environ, config)
        self.auth_api_root = config.get('websocket.auth_api_root')
        self.request = Request(environ)

    def authenticate(self):
        response = self._call_api_method('authenticate')
        if response.status_code != 200:
            raise NotAuthenticated("Could not authenticate")
        try:
            response_data = response.json()
        except ValueError:
            raise NotAuthenticated("Could not authenticate")
        if not response_data.get('authenticated'):
            raise NotAuthenticated("Authentication denied")
        self.environ['user_id'] = response_data.get('user_id')

    def authorize(self, listen_channels=None, publish_channels=None,
                  event_targets=None):
        data = {
            'listen_channels': list(listen_channels),
            'publish_channels': list(publish_channels),
            'event_targets': list(event_targets)
        }
        response = self._call_api_method('authorize', data=json.dumps(data))
        if response.status_code != 200:
            LOG.debug("sent:%s;received:%s", data, response)
            self.fail("Failed to authorize")
        try:
            response_data = response.json()
        except ValueError:
            self.fail("Failed to authorize")
        if not response_data.get('authorized'):
            LOG.debug("sent:%s;received:%s", data, response_data)
            self.fail("Authorization denied")

    def start_connection(self):
        response = self._call_api_method('start_connection')
        try:
            return response.json()
        except ValueError:
            self.fail("Failed to authorize")

    def end_connection(self):
        response = self._call_api_method('end_connection')
        try:
            return response.json()
        except ValueError:
            self.fail("Failed to authorize")

    def _get_headers(self):
        ws_token = self.config.get('auth.ws.token')
        if ws_token is None:
            raise ImproperlyConfigured("auth.ws.token must be present in "
                                       "websocket configuration")
        return {
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': '*/json',
            'Cookie': self.environ['HTTP_COOKIE'],
            'WS_TOKEN': ws_token
        }

    def _call_api_method(self, method_name, data=None):
        session_id = self.request.cookies.get('_session_id', None)
        url = '{}/{}?_session_id={}'.format(self.auth_api_root,
                                            method_name,
                                            session_id)
        return requests.post(url, headers=self._get_headers(), data=data,
                             verify=False)

