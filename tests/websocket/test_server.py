# -*- coding: utf-8 -*-

"""
test_server

@author: U{tannern<tannern@gmail.com>}
"""
import json
from threading import Thread
import unittest
import mock
from vulcanforge.websocket import DEFAULT_SERVER_CONFIG
from vulcanforge.websocket.exceptions import WebSocketException
from vulcanforge.websocket.server import ConnectionController


class ConnectionControllerTestCase(unittest.TestCase):

    def setUp(self):
        self.websocket = mock.Mock()
        self.redis = mock.Mock()
        self.pubsub = mock.Mock()
        self.reactor = mock.Mock()
        self.controller = ConnectionController(DEFAULT_SERVER_CONFIG,
                                               self.websocket, self.redis,
                                               self.pubsub, self.reactor)

    def _receive_side_effect(self, queue):
        iterator = iter(queue)

        def side_effect():
            try:
                return iterator.next()
            except StopIteration:
                self.controller.connected = False
                return None
        return side_effect

    def _listen_side_effect(self, queue):
        iterator = iter(queue)

        def side_effect():
            try:
                yield iterator.next()
            except StopIteration:
                self.controller.connected = False
                raise StopIteration
        return side_effect

    def _raise_on_call(self, exception):

        def do_raise(*args, **kwargs):
            self.controller.connected = False
            raise exception
        return do_raise

    def test_loop_lost_connection(self):
        loop_thread = Thread(target=self.controller._loop, args=[lambda: None])
        loop_thread.start()
        self.websocket.socket = None  # simulate disconnect
        loop_thread.join(0.1)
        self.assertFalse(loop_thread.isAlive())

    def test_listener(self):
        msgs = ['hi', 'bye']
        self.websocket.receive.side_effect = self._receive_side_effect(msgs)
        listen_thread = Thread(target=self.controller.run_listener)
        listen_thread.start()
        listen_thread.join()
        self.reactor.react.assert_has_calls([
            mock.call('hi'),
            mock.call('bye')
        ])

    def test_listener_exception(self):
        self.websocket.receive.side_effect = self._receive_side_effect(['hi'])
        e = WebSocketException("foo")
        self.reactor.react = self._raise_on_call(e)
        listen_thread = Thread(target=self.controller.run_listener)
        listen_thread.start()
        listen_thread.join()
        self.websocket.send.assert_called_once_with(json.dumps({
            'error': {
                'kind': 'WebSocketException',
                'message': 'foo'
            }
        }))

    def test_speaker(self):
        msgs = [
            {
                'type': 'message',
                'pattern': None,
                'channel': 'foo',
                'data': 'hi'
            },
            {
                'type': 'message',
                'pattern': None,
                'channel': 'foo',
                'data': 'bye'
            }
        ]
        self.pubsub.listen.side_effect = self._listen_side_effect(msgs)
        speak_thread = Thread(target=self.controller.run_speaker)
        speak_thread.start()
        speak_thread.join()
        self.websocket.send.assert_has_calls([
            mock.call(json.dumps({
                'type': 'message',
                'pattern': None,
                'channel': 'foo',
                'data': 'hi'
            })),
            mock.call(json.dumps({
                'type': 'message',
                'pattern': None,
                'channel': 'foo',
                'data': 'bye'
            }))
        ])
