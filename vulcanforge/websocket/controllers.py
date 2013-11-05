# -*- coding: utf-8 -*-

"""
controllers

@author: U{tannern<tannern@gmail.com>}
"""
import json
import logging
from pylons import app_globals as g, tmpl_context as c, request
from tg import expose
from vulcanforge.auth.model import User
from vulcanforge.common.controllers import BaseController
from vulcanforge.websocket.authorizer import WebSocketAuthorizer
from vulcanforge.websocket.exceptions import NotAuthorized


LOG = logging.getLogger(__name__)


class WebSocketAPIController(BaseController):

    def __init__(self):
        self._authorizer = WebSocketAuthorizer()
        self.chat = ChatAPIController()

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
            'user': {
                '_id': str(c.user._id),
                'username': c.user.username
            }
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
        except (NotAuthorized, ValueError):
            authorized = False
        except:
            raise
        else:
            authorized = True
        return {
            'authorized': authorized,
            'user': {
                '_id': str(c.user._id),
                'username': c.user.username
            }
        }

    def _auth_listen(self, listen_channels):
        for channel in listen_channels:
            self._authorizer.can_listen(channel)

    def _auth_publish(self, publish_channels):
        for channel in publish_channels:
            self._authorizer.can_publish(channel)

    def _auth_targets(self, event_targets):
        for target in event_targets:
            self._authorizer.can_target(target)

    @expose('json')
    def start_connection(self):
        redis = g.cache.redis
        count_key = 'user.{}.connection_count'.format(c.user.username)
        redis.incr(count_key)
        channels = []
        for project in c.user.my_projects():
            # mark user as connected
            key = 'project.{}.connected_users'.format(project.shortname)
            redis.sadd(key, c.user.username)
            # skip neighborhood projects
            if project.shortname == '__init__':
                continue
            if project.shortname.startswith('u/'):
                continue
            channels.append('project.{}'.format(project.shortname))
        return {
            'username': c.user.username,
            'channels': channels
        }

    @expose('json')
    def end_connection(self):
        redis = g.cache.redis
        count_key = 'user.{}.connection_count'.format(c.user.username)
        connection_count = redis.decr(count_key)
        if connection_count <= 0:
            redis.set(count_key, 0)
            for project in c.user.my_projects():
                # mark user as disconnected
                key = 'project.{}.connected_users'.format(project.shortname)
                redis.srem(key, c.user.username)
        return {}


class ChatAPIController(BaseController):

    @expose('json')
    def projects(self):
        redis = g.cache.redis
        projects = []
        for project in c.user.my_projects():
            project_data = project.__json__()
            if project.shortname == '__init__':
                continue
            if project.shortname.startswith('u/'):
                continue
            key = 'project.{}.connected_users'.format(project.shortname)
            project_data['online_users'] = list(redis.smembers(key))
            projects.append(project_data)
        return {
            'projects': projects
        }
