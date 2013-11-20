# -*- coding: utf-8 -*-

"""
controllers

@author: U{tannern<tannern@gmail.com>}
"""
import json
import logging
from markupsafe import Markup
from pylons import app_globals as g, tmpl_context as c, request
from tg import expose
from webob.exc import HTTPNotFound
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
        #redis = g.cache.redis
        #user_prefix = 'user.{}'.format(c.user.username)
        #
        #count_key = '{}.connection_count'.format(user_prefix)
        #count = redis.incr(count_key)
        #redis.expire(count_key, 65)
        #if count == 1:
        #    redis.publish(user_prefix, json.dumps({
        #        'type': 'UserConnect'
        #    }))
        #
        channels = []
        for project in c.user.my_projects():
            # skip neighborhood projects
            if project.shortname == '__init__':
                continue
            if project.shortname.startswith('u/'):
                continue
            channels.append('project.{}'.format(project.shortname))
        #
        return {
            'username': c.user.username,
            'user_id': str(c.user._id),
            'channels': channels
        }

    @expose('json')
    def end_connection(self):
        #redis = g.cache.redis
        #user_prefix = 'user.{}'.format(c.user.username)
        ##
        #count_key = '{}.connection_count'.format(user_prefix)
        #connection_count = redis.decr(count_key)
        #if connection_count <= 0:
        #    redis.delete(count_key)
        #    redis.publish(user_prefix, json.dumps({
        #        'type': 'UserDisconnect'
        #    }))
        return {}


class ChatAPIController(BaseController):

    @expose('json')
    def state(self):
        redis = g.cache.redis
        projects = []
        for project in c.user.my_projects():
            if project.shortname == '__init__':
                continue
            if project.shortname.startswith('u/'):
                continue
            project_data = project.__json__()
            chat_app_config = project.get_app_configs_by_kind('chat').first()
            project_prefix = 'project.{}'.format(project.shortname)
            # all users
            project_data['users'] = [u.username for u in project.users()]
            # connected users
            key = '{}.connected_users'.format(project_prefix)
            project_data['online_users'] = list(redis.smembers(key))
            # chat thread
            if chat_app_config is None:
                project_data['chatChannel'] = None
            else:
                chat_app = chat_app_config.load()(project, chat_app_config)
                thread = chat_app.get_active_thread()
                project_data['chatChannel'] = '{}.chat'.format(project_prefix)
                project_data['chatMessages'] = [
                    p.get_publish_dict()
                    for p in thread.query_posts(style="timestamp")
                ]
            projects.append(project_data)
        return {
            'projects': projects
        }

    @expose('json')
    def user(self, username):
        redis = g.cache.redis
        user = User.by_username(username)
        if user is None:
            raise HTTPNotFound()
        profile = user.get_profile_info()
        online = redis.exists('user.{username}.connection_count'.format(
            **profile))
        profile.update(
            profileImage=Markup(profile.get('profileImage')),
            online=online
        )
        return profile
