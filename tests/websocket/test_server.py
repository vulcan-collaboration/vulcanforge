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
from vulcanforge.websocket.exceptions import WebSocketException, \
    InvalidMessageException
from vulcanforge.websocket.server import ConnectionController


class ConnectionControllerTestCase(unittest.TestCase):

    def setUp(self):
        self.websocket = mock.Mock()
        self.auth = mock.Mock()
        self.redis = mock.Mock()
        self.pubsub = mock.Mock()
        self.reactor = mock.Mock()
        self.controller = ConnectionController({}, DEFAULT_SERVER_CONFIG,
                                               self.auth,
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
        e = InvalidMessageException("foo")
        self.reactor.react = self._raise_on_call(e)
        self.controller.run_listener()
        self.websocket.send.assert_called_once_with(json.dumps({
            'type': 'error',
            'data': {
                'kind': 'InvalidMessageException',
                'message': 'foo'
            }
        }))

    def test_speaker(self):
        msgs = [
            {
                'channel': 'foo',
                'data': 'hi',
                'pattern': None,
                'type': 'message'
            },
            {
                'channel': 'foo',
                'data': 'bye',
                'pattern': None,
                'type': 'message'
            }
        ]
        self.pubsub.listen.side_effect = self._listen_side_effect(msgs)
        self.controller.run_speaker()
        self.assertEqual(self.websocket.send.call_count, 2)
        call_1, call_2 = self.websocket.send.call_args_list
        arg_1 = json.loads(call_1[0][0])
        arg_2 = json.loads(call_2[0][0])
        self.assertDictEqual(arg_1, {
            'type': 'message',
            'channel': 'foo',
            'data': 'hi'
        })
        self.assertDictEqual(arg_2, {
            'type': 'message',
            'channel': 'foo',
            'data': 'bye'
        })
