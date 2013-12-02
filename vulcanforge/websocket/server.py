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
from vulcanforge.websocket import load_auth_broker
from vulcanforge.websocket.exceptions import WebSocketException, \
    LostConnection, InvalidMessageException, NotAuthorized, NotAuthenticated
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
        LOG.debug("new connection")
        websocket = environ.get('wsgi.websocket')
        if websocket is None:
            return self._http_handler(environ, start_response)
        pubsub = self.redis.pubsub()
        auth_broker_class = load_auth_broker(self.config)
        broker = auth_broker_class(environ, self.config)
        reactor = MessageReactor(environ, self.config, broker, self.redis,
                                 pubsub)
        controller = ConnectionController(environ, self.config, broker,
                                          websocket, self.redis, pubsub,
                                          reactor)
        try:
            controller.authenticate()
        except NotAuthenticated:
            LOG.debug("closed connection")
            return
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
                group.join(0.1)
        except:
            LOG.exception("unknown exception")
            break_out()
        finally:
            group.kill()
            websocket.close()
            LOG.debug("closed connection")

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
        self._authenticated = False
        self.pubsub.subscribe(['system'])

    def __del__(self):
        if self._authenticated:
            self._decrement_count()

    def authenticate(self):
        try:
            self.broker.authenticate()
        except NotAuthenticated, e:
            self._send_exception(e)
            raise
        else:
            self._authenticated = True
            self.connection_info = self.broker.start_connection()
            channels = self.connection_info.get('channels', [])
            self._user_count_key = 'user.{username}.connection_count'.format(
                **self.connection_info)
            self._user_channel_key = 'user.{username}'.format(
                **self.connection_info)
            self._increment_count()
            self._extend_count_expire()
            self.pubsub.subscribe(channels)

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
            raise LostConnection()
        self._extend_count_expire()
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
        self._extend_count_expire()
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

    def _increment_count(self):
        count = self.redis.incr(self._user_count_key)
        self._extend_count_expire()
        if count == 1:
            self.redis.publish(self._user_channel_key, json.dumps({
                'type': 'UserOnline'
            }))

    def _extend_count_expire(self):
        if not hasattr(self, 'connection_info'):
            return
        self.redis.expire(self._user_count_key, 65)

    def _decrement_count(self):
        count = self.redis.decr(self._user_count_key)
        if count <= 0:
            ttl = 5
            self.redis.expire(self._user_count_key, ttl)
            gevent.sleep(ttl + 1)
            if self.redis.exists(self._user_count_key):
                return
            self.redis.publish(self._user_channel_key, json.dumps({
                'type': 'UserOffline'
            }))


def make_server(config, listener=None):
    if listener is None:
        host = config['websocket.host']
        port = int(config['websocket.port'])
        listener = gevent.baseserver._tcp_listener((host, port))
    app = WebSocketApp(config)
    server = WSGIServer(listener, app,
                        handler_class=geventwebsocket.WebSocketHandler)
    return server
