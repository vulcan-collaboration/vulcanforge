# -*- coding: utf-8 -*-

"""
server

@author: U{tannern<tannern@gmail.com>}
"""
import logging
import json
from paste.deploy.converters import asint
import redis
import gevent
import gevent.baseserver
import gevent.pool
from gevent.pywsgi import WSGIServer
import geventwebsocket
import time
from vulcanforge.websocket import load_auth_broker
from vulcanforge.websocket.exceptions import WebSocketException, \
    LostConnection, InvalidMessageException, NotAuthorized
from vulcanforge.websocket.reactor import MessageReactor


LOG = logging.getLogger(__name__)


class WebSocketApp(object):

    def __init__(self, config):
        super(WebSocketApp, self).__init__()
        self.config = config
        self.redis = redis.Redis(host=config['redis.host'],
                                 port=asint(config.get('redis.port', 6379)),
                                 db=asint(config.get('redis.db', 0)))

    def __call__(self, environ, start_response):
        websocket = environ.get('wsgi.websocket')
        if websocket is None:
            return self._http_handler(environ, start_response)
        pubsub = self.redis.pubsub()
        auth_broker_class = load_auth_broker(self.config)
        broker = auth_broker_class(environ, self.config)
        reactor = MessageReactor(environ, self.config, broker, self.redis, pubsub)
        controller = ConnectionController(environ, self.config, broker, websocket,
                                          self.redis, pubsub, reactor)
        group = gevent.pool.Group()
        listener = gevent.Greenlet(controller.run_listener)
        speaker = gevent.Greenlet(controller.run_speaker)

        def break_out(*args):
            controller.connected = False
            group.kill()
        try:
            listener.link_exception(break_out)
            speaker.link_exception(break_out)
            group.add(listener)
            group.add(speaker)
            listener.start()
            speaker.start()
            while controller.is_connected():
                time.sleep(0.1)
        except:
            LOG.exception("unknown exception")
            break_out()
        finally:
            group.kill()
            websocket.close()
            del listener
            del speaker

    @staticmethod
    def _http_handler(environ, start_response):
        start_response("400 Bad Request", [])
        return ["WebSocket connection expected"]


class ConnectionController(object):

    def __init__(self, environ, config, broker, websocket, redis, pubsub,
                 reactor):
        super(ConnectionController, self).__init__()
        self.environ = environ
        self.config = config
        self.broker = broker
        self.websocket = websocket
        self.redis = redis
        self.pubsub = pubsub
        self.reactor = reactor
        self.connected = True
        try:
            self.broker.authenticate()
        except NotAuthorized, e:
            self._send_exception(e)
        else:
            connection_info = self.broker.start_connection()
            channels = ['system'] + connection_info.get('channels', [])
            self.pubsub.subscribe(channels)

    def __del__(self):
        self.broker.end_connection()

    def _loop(self, method):
        try:
            while self.is_connected():
                method()
        except (
            gevent.GreenletExit,
            geventwebsocket.WebSocketError,
            WebSocketException,
            LostConnection
        ):
            self.connected = False

    def is_connected(self):
        return self.connected and self.websocket.socket is not None

    def run_listener(self):
        self._loop(self._listen_frame)

    def run_speaker(self):
        self._loop(self._speak_frame)

    def _listen_frame(self):
        try:
            message = self.websocket.receive()
            LOG.debug("received:%s", message)
        except:
            LOG.exception("websocket.receive failed")
            raise LostConnection()
        if message is None:
            return
        try:
            self.reactor.react(message)
        except InvalidMessageException, e:
            self._send_exception(e)
        except NotAuthorized, e:
            self._send_exception(e)
        except:
            LOG.exception("reactor.react failed")

    def _speak_frame(self):
        for message in self.pubsub.listen():
            message.pop('pattern', None)
            self.send(message)

    def send(self, message):
        try:
            json_message = json.dumps(message)
            LOG.debug("sending:%s", json_message)
            self.websocket.send(json_message)
        except:
            LOG.exception("websocket.send failed")
            raise LostConnection()

    def _send_error(self, kind, message):
        self.send({
            'type': 'error',
            'data': {
                'kind': kind,
                'message': message
            }
        })

    def _send_exception(self, e):
        self._send_error(e.__class__.__name__, unicode(e))


def make_server(config, listener=None):
    if listener is None:
        host = config['websocket.host']
        port = int(config['websocket.port'])
        listener = gevent.baseserver._tcp_listener((host, port))
    app = WebSocketApp(config)
    server = WSGIServer(listener, app,
                        handler_class=geventwebsocket.WebSocketHandler)
    return server
