# -*- coding: utf-8 -*-

"""
authorization

@author: U{tannern<tannern@gmail.com>}
"""
import json
import requests
from webob import Request
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


class WebSocketAuthBroker(BaseWebSocketAuthBroker):

    def __init__(self, environ, config):
        super(WebSocketAuthBroker, self).__init__(environ, config)
        self.auth_api_root = config.get('websocket.auth_api_root')
        self.request = Request(environ)

    def authenticate(self):
        session_id = self.request.cookies.get('_session_id', None)
        url = self.auth_api_root + '/authenticate?_session_id=' + session_id
        headers = {
            'Accept': '*/json',
            'Cookie': self.environ['HTTP_COOKIE']
        }
        response = requests.post(url, headers=headers)
        if response.status_code != 200:
            self.fail("Could not authenticate")
        try:
            response_data = response.json()
        except ValueError:
            self.fail("Could not authenticate")
        if not response_data.get('authenticated'):
            self.fail("Authentication denied")
        self.environ['user_id'] = response_data.get('user_id')

    def authorize(self, listen_channels=None, publish_channels=None,
                  event_targets=None):
        session_id = self.request.cookies.get('_session_id', None)
        url = self.auth_api_root + '/authorize?_session_id=' + session_id
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': '*/json',
            'Cookie': self.environ['HTTP_COOKIE']
        }
        data = {
            'listen_channels': list(listen_channels),
            'publish_channels': list(publish_channels),
            'event_targets': list(event_targets)
        }
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code != 200:
            self.fail("Failed to authorize")
        try:
            response_data = response.json()
        except ValueError:
            self.fail("Failed to authorize")
        if not response_data.get('authorized'):
            self.fail("Authorization denied")
