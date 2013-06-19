# -*- coding: utf-8 -*-

"""
server

@author: U{tannern<tannern@gmail.com>}
"""
from gevent.pywsgi import WSGIServer
import geventwebsocket
import redis
from vulcanforge.websocket.reactor import MessageReactor


class WebSocketApp(object):

    def __init__(self):
        self.redis_client = redis.Redis()

    def __call__(self, environ, start_response):
        websocket = environ.get('wsgi.websocket')
        if websocket is None:
            return self._http_handler(environ, start_response)
        pubsub_client = self.redis_client.pubsub()
        message_reactor = MessageReactor(self.redis_client, pubsub_client)
        # spawn socket listener
        # spawn socket speaker

    def _http_handler(self, environ, start_response):
        start_response("400 Bad Request", [])
        return ["WebSocket connection expected"]


def run_web_socket_server(host='', port='8001'):
    import gevent.monkey
    gevent.monkey.patch_all(dns=False)
    app = WebSocketApp()
    server = WSGIServer((host, port), app,
                        handler_class=geventwebsocket.WebSocketHandler)
    server.serve_forever()
