# -*- coding: utf-8 -*-

"""
worker

@author: U{tannern<tannern@gmail.com>}
"""
import json
import os
import logging
from paste.deploy.converters import asint
from redis import Redis
import sys

from webob import Request
from paste.deploy import loadapp
import pylons
from pylons import app_globals as g
from tg import config


LOG = logging.getLogger(__name__)


class EventdWorker(object):

    def __init__(self, config_path, relative_path=None, log=None):
        self.config_path = config_path
        self.relative_path = relative_path or os.getcwd()
        self.log = log or logging.getLogger(__name__)
        self.keep_running = True
        self.restart_when_done = False
        self.wsgi_app = None
        self.wsgi_error_log = None
        self.handlers = self.make_handler_map()
        self.event_queue_timeout = asint(config.get('event_queue.timeout', 2))

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
        wsgi_error_log_path = pylons.config.get('eventd.wsgi_log', '/dev/null')
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
                self.log.debug('eventd found event: {!r}'.format(item))
                return item

    def get_handler_for_event(self, event):
        handler = self.handlers.get(event['type'])
        if not handler:
            LOG.warn('no handler found for {!r}'.format(event))
        return handler

    @staticmethod
    def start_response(status, headers, exc_info=None):
        pass

    def handle_event_info(self, event_info):
        event = event_info['event']
        handler = self.get_handler_for_event(event)
        if handler is None:
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
        result = list(self.wsgi_app(r.environ, self.start_response))

    @classmethod
    def make_handler_map(cls):
        return {
            'test': cls.handle_test
        }

    @staticmethod
    def handle_test(name, targets, params):
        LOG.info('handling test event')
        redis = Redis()
        redis.publish(params['channel'], params['message'])
