# -*- coding: utf-8 -*-

"""
worker

@author: U{tannern<tannern@gmail.com>}
"""
import sys
import os
import json
import logging
from beaker.middleware import SessionMiddleware
from ming.odm import ThreadLocalODMSession
from paste.deploy.converters import asint
import re
from paste.registry import RegistryManager
from redis import Redis

from webob import Request
from paste.deploy import loadapp
from pylons import app_globals as g, tmpl_context as c
import tg
from vulcanforge.auth.middleware import AuthMiddleware


class AbstractEventdWorker(object):

    def __init__(self, config_path, relative_path=None, log=None):
        self.config_path = config_path
        self.relative_path = relative_path or os.getcwd()
        self.log = log or logging.getLogger(__name__)
        self.keep_running = True
        self.restart_when_done = False
        self.wsgi_app = None
        self.wsgi_error_log = None
        self.handlers = self.make_handler_map()
        raw_timeout = tg.config.get('event_queue.timeout', 2)
        self.event_queue_timeout = asint(raw_timeout)

    def graceful_restart(self, signum, frame):
        self.log.info('eventd pid %s recieved signal %s restarting gracefully',
                      os.getpid(), signum)
        self.restart_when_done = True
        self.keep_running = False

    def graceful_stop(self, signum, frame):
        self.log.info('eventd pid %s recieved signal %s stopping gracefully',
                      os.getpid(), signum)
        self.keep_running = False

    def start_app(self):
        self.wsgi_app = loadapp(
            'config:%s#event' % self.config_path,
            relative_to=self.relative_path)

        # this is only present to avoid errors within weberror's
        # ErrorMiddleware if the default error stream (stderr?) doesn't work
        wsgi_error_log_path = tg.config.get('eventd.wsgi_log', '/dev/null')
        self.wsgi_error_log = open(wsgi_error_log_path, 'a')

    def event_loop(self):
        self.start_app()
        while self.keep_running:
            event_info = self.get_next_event_info()
            if event_info is None:
                continue
            try:
                event_dict = json.loads(event_info)
                self.handle_event_info(event_dict)
            except ValueError:
                self.log.exception('event error: invalid JSON: {}'.format(
                    event_info))
            except:
                self.log.exception('event error: {}'.format(event_info))
            finally:
                self.wsgi_error_log.flush()

        self.log.info('eventd pid %s stopping gracefully.', os.getpid())

        if self.restart_when_done:
            self.log.info('eventd pid %s restarting itself.', os.getpid())
            os.execv(sys.argv[0], sys.argv)

    def get_next_event_info(self):
        while self.keep_running:
            item = g.event_queue.get(timeout=self.event_queue_timeout)
            if item:
                return item

    def get_handler_for_event(self, event):
        handler = self.handlers.get(event['type'])
        return handler

    @staticmethod
    def start_response(status, headers, exc_info=None):
        pass

    def handle_event_info(self, event_info):
        event = event_info['event']
        handler = self.get_handler_for_event(event)
        if handler is None:
            self.log.warn('no handler found for {!r}'.format(event))
            return
        r = Request.blank(
            '/__event__/{type}/'.format(**event),
            environ={
                'event.type': event['type'],
                'event.targets': event['targets'],
                'event.params': event['params'],
                'event.handler': handler,
                'wsgi.errors': self.wsgi_error_log or self.log,
            },
            headers={
                'Cookie': str(event_info['cookie'])
            })
        return list(self.wsgi_app(r.environ, self.start_response))

    def make_handler_map(self):
        """
        should be overridden in subclass, example method included to show format
        """
        return {
            'test': self.handle_test
        }

    def handle_test(self, name, targets, params):
        """
        example method, should be overridden or excluded from handler map
        """
        redis = Redis()
        for target in targets:
            redis.publish(target, params['message'])


class EventdWorker(AbstractEventdWorker):

    def make_handler_map(self):
        return {
            'PostChatMessage': self.handle_post_chat_message,
            'ShareLocationWithChat': self.handle_share_location
        }

    def handle_post_chat_message(self, name, targets, params):
        from vulcanforge.project.model import Project
        message_text = params.get('message', None)
        if message_text is None or message_text == '':
            self.log.warn("invalid message params: %r", params)
        for target in targets:
            match = re.match(r'^project\.([^\.]+).chat$', target)
            shortname = match.group(1)
            project = Project.by_shortname(shortname)
            if project is None:
                self.log.warn("No project found with shortname: %s", shortname)
                continue
            chat_app_config = project.get_app_configs_by_kind('chat').first()
            if chat_app_config is None:
                self.log.warn("No chat app found for project: %s", shortname)
                continue
            with g.context_manager.push(app_config_id=chat_app_config._id):
                chat_app = chat_app_config.app(project, chat_app_config)
                thread = chat_app.get_active_thread()
                thread.post(message_text)

    def handle_share_location(self, name, targets, params):
        from vulcanforge.project.model import Project
        expected_keys = {'title', 'href', 'timestamp'}
        if expected_keys.difference(params):
            self.log.warn("invalid message params: %r", params)
        for target in targets:
            match = re.match(r'^project\.([^\.]+).chat$', target)
            shortname = match.group(1)
            project = Project.by_shortname(shortname)
            if project is None:
                self.log.warn("No project found with shortname: %s", shortname)
                continue
            chat_app_config = project.get_app_configs_by_kind('chat').first()
            if chat_app_config is None:
                self.log.warn("No chat app found for project: %s", shortname)
                continue
            redis = g.cache.redis
            params.update(author=c.user.username)
            msg = json.dumps({
                'type': 'LocationShared',
                'data': params
            })
            redis.publish(target, msg)
