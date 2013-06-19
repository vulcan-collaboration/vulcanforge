# -*- coding: utf-8 -*-

"""
test_reactor

@author: U{tannern<tannern@gmail.com>}
"""

import json
import unittest
import mock
from vulcanforge.websocket.exceptions import InvalidMessageException
from vulcanforge.websocket.reactor import MessageReactor


class ReactorTestCase(unittest.TestCase):

    def setUp(self):
        self.mock_redis = mock.Mock()
        self.mock_pubsub = mock.Mock()
        self.reactor = MessageReactor(self.mock_redis, self.mock_pubsub)


class TestMessageValidation(ReactorTestCase):

    def _valid(self, message):
        self.reactor.validate(message)

    def _invalid(self, message):
        with self.assertRaises(InvalidMessageException):
            self.reactor.validate(message)

    def test_invalid_json(self):
        self._invalid('')
        self._invalid('a')
        self._invalid(100)

    def test_schema(self):
        self._valid('{}')
        self._invalid('[]')
        self._invalid(json.dumps({
            'extraField': 'foo'
        }))

    def test_subscribe_schema(self):
        self._valid(json.dumps({
            'subscribe': 'foo'
        }))
        self._valid(json.dumps({
            'subscribe': ['foo', 'bar']
        }))
        self._invalid(json.dumps({
            'subscribe': True
        }))
        self._invalid(json.dumps({
            'subscribe': {'foo': 'bar'}
        }))

    def test_unsubscribe_schema(self):
        self._valid(json.dumps({
            'unsubscribe': 'foo'
        }))
        self._valid(json.dumps({
            'unsubscribe': ['foo', 'bar']
        }))
        self._invalid(json.dumps({
            'unsubscribe': True
        }))
        self._invalid(json.dumps({
            'unsubscribe': {'foo': 'bar'}
        }))

    def test_publish_schema(self):
        self._invalid(json.dumps({
            'publish': 'foo'
        }))
        self._valid(json.dumps({
            'publish': {
                'channel': 'foo',
                'message': 'howdy'
            }
        }))
        self._valid(json.dumps({
            'publish': {
                'channel': ['foo', 'bar'],
                'message': 'howdy'
            }
        }))

    def test_trigger_schema(self):
        self._invalid(json.dumps({
            'trigger': 'foo'
        }))
        self._valid(json.dumps({
            'trigger': {
                'type': 'foo',
                'target': 'howdy'
            }
        }))
        self._valid(json.dumps({
            'trigger': {
                'type': 'foo',
                'target': 'howdy',
                'params': 'bar'
            }
        }))
        self._valid(json.dumps({
            'trigger': {
                'type': 'foo',
                'target': 'howdy',
                'params': {
                    'foo': 'bar',
                    'howdy': 'yall'
                }
            }
        }))


class TestReactor(ReactorTestCase):

    def test_queue_event(self):
        event_dict = {
            'type': 'foo',
            'target': 'bar'
        }
        message_dict = {
            'trigger': event_dict
        }
        message = json.dumps(message_dict)
        self.reactor.react(message)
        self.mock_redis.rpush.assert_called_with(self.reactor.event_queue_key,
                                                 event_dict)
        self.assertFalse(self.mock_redis.publish.called)

    def test_publish_message(self):
        channel = 'foo'
        message = 'bar'
        socket_message_dict = {
            'publish': {
                'channel': channel,
                'message': message
            }
        }
        socket_message = json.dumps(socket_message_dict)
        self.reactor.react(socket_message)
        self.mock_redis.publish.assert_called_with(channel, message)
        self.assertFalse(self.mock_redis.rlpush.called)

    def test_publish_multiple_channels(self):
        channel = ['foo1', 'foo2']
        message = 'bar'
        socket_message_dict = {
            'publish': {
                'channel': channel,
                'message': message
            }
        }
        socket_message = json.dumps(socket_message_dict)
        self.reactor.react(socket_message)
        self.mock_redis.publish.assert_has_calls([
            mock.call('foo1', message),
            mock.call('foo2', message)
        ])
        self.assertFalse(self.mock_redis.rlpush.called)

    def test_subscribe(self):
        message_dict = {
            'subscribe': 'foo'
        }
        message = json.dumps(message_dict)
        self.reactor.react(message)
        self.mock_pubsub.subscribe.assert_called_once_with(['foo'])

    def test_subscribe_multiple(self):
        message_dict = {
            'subscribe': ['foo', 'bar']
        }
        message = json.dumps(message_dict)
        self.reactor.react(message)
        self.mock_pubsub.subscribe.assert_called_once_with(['foo', 'bar'])

    def test_unsubscribe(self):
        message_dict = {
            'unsubscribe': 'foo'
        }
        message = json.dumps(message_dict)
        self.reactor.react(message)
        self.mock_pubsub.unsubscribe.assert_called_once_with(['foo'])

    def test_unsubscribe_multiple(self):
        message_dict = {
            'unsubscribe': ['foo', 'bar']
        }
        message = json.dumps(message_dict)
        self.reactor.react(message)
        self.mock_pubsub.unsubscribe.assert_called_once_with(['foo', 'bar'])


class TestAuthorizer(unittest.TestCase):

    def test_authorize_channels(self):
        pass
