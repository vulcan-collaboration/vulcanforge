# -*- coding: utf-8 -*-

"""
server

@author: U{tannern<tannern@gmail.com>}
"""
import logging
import sys
import json
import redis
import gevent
import gevent.pool
from gevent.pywsgi import WSGIServer
import geventwebsocket
from vulcanforge.websocket.exceptions import WebSocketException, LostConnection
from vulcanforge.websocket.reactor import MessageReactor


LOG = logging.getLogger(__name__)


class WebSocketApp(object):

    def __init__(self, config):
        self.config = config
        self.redis = redis.Redis(host=config['redis.host'],
                                 port=int(config['redis.port']))

    def __call__(self, environ, start_response):
        websocket = environ.get('wsgi.websocket')
        if websocket is None:
            return self._http_handler(environ, start_response)
        pubsub = self.redis.pubsub()
        reactor = MessageReactor(self.config, self.redis, pubsub)
        controller = ConnectionController(self.config, websocket, self.redis,
                                          pubsub, reactor)
        group = gevent.pool.Group()

        def break_out(*args):
            controller.connected = False
            group.kill()
        try:
            listener = gevent.Greenlet(controller.run_listener)
            speaker = gevent.Greenlet(controller.run_speaker)
            listener.link_exception(break_out)
            speaker.link_exception(break_out)
            group.add(listener)
            group.add(speaker)
            listener.start()
            speaker.start()
            while controller.is_connected():
                group.join(timeout=0.5)
        except:
            break_out()
        finally:
            group.kill()
            websocket.close()

    @staticmethod
    def _http_handler(environ, start_response):
        start_response("400 Bad Request", [])
        return ["WebSocket connection expected"]


class ConnectionController(object):

    def __init__(self, config, websocket, redis, pubsub, reactor):
        self.config = config
        self.websocket = websocket
        self.redis = redis
        self.pubsub = pubsub
        self.pubsub.subscribe(['system'])
        self.reactor = reactor
        self.connected = True

    def _loop(self, method):
        while self.is_connected():
            try:
                method()
            except (geventwebsocket.WebSocketError, WebSocketException):
                self.connected = False
                pass

    def is_connected(self):
        return self.connected and self.websocket.socket is not None

    def run_listener(self):
        self._loop(self._listen_frame)

    def run_speaker(self):
        self._loop(self._speak_frame)

    def _listen_frame(self):
        try:
            message = self.websocket.receive()
        except:
            raise LostConnection()
        if message is None:
            raise LostConnection()
        try:
            self.reactor.react(message)
        except WebSocketException, e:
            self.websocket.send(json.dumps({
                'error': {
                    'kind': e.__class__.__name__,
                    'message': unicode(e)
                }
            }))

    def _speak_frame(self):
        for message in self.pubsub.listen():
            try:
                self.websocket.send(json.dumps(message))
            except:
                raise LostConnection()


def get_config(filename):
    import ConfigParser
    parser = ConfigParser.ConfigParser()
    with open(filename, 'r') as fp:
        parser.readfp(fp)
    section_name = "websocketserver"
    config = {}
    try:
        for option in parser.options(section_name):
            config[option] = parser.get(section_name, option)
    except ConfigParser.NoSectionError:
        sys.stderr.write("config file does not contain the required section "
                         "[{}]\n".format(section_name))
        return
    return config


def make_server(config):
    host = config['host']
    port = int(config['port'])
    app = WebSocketApp(config)
    server = WSGIServer((host, port), app,
                        handler_class=geventwebsocket.WebSocketHandler)
    return server
