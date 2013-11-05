# -*- coding: utf-8 -*-

"""
test_reactor

@author: U{tannern<tannern@gmail.com>}
"""

import json
import unittest
import mock
from vulcanforge.websocket import DEFAULT_SERVER_CONFIG
from vulcanforge.websocket.auth_broker import BaseWebSocketAuthBroker
from vulcanforge.websocket.exceptions import InvalidMessageException, \
    NotAuthorized
from vulcanforge.websocket.reactor import MessageReactor


class ReactorTestCase(unittest.TestCase):

    def setUp(self):
        self.environ = {
            'HTTP_COOKIE': "dummy-cookie"
        }
        self.mock_auth = mock.Mock()
        self.mock_redis = mock.Mock()
        self.mock_pubsub = mock.Mock()
        self.reactor = MessageReactor(self.environ, DEFAULT_SERVER_CONFIG,
                                      self.mock_auth,
                                      self.mock_redis, self.mock_pubsub)


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
            'subscribe': ['foo']
        }))
        self._valid(json.dumps({
            'subscribe': ['foo', 'bar']
        }))
        self._invalid(json.dumps({
            'subscribe': []
        }))
        self._invalid(json.dumps({
            'subscribe': True
        }))
        self._invalid(json.dumps({
            'subscribe': {'foo': 'bar'}
        }))

    def test_unsubscribe_schema(self):
        self._valid(json.dumps({
            'unsubscribe': ['foo', 'bar']
        }))
        self._invalid(json.dumps({
            'unsubscribe': 'foo'
        }))
        self._invalid(json.dumps({
            'unsubscribe': []
        }))
        self._invalid(json.dumps({
            'unsubscribe': True
        }))
        self._invalid(json.dumps({
            'unsubscribe': {'foo': 'bar'}
        }))

    def test_publish_schema(self):
        self._valid(json.dumps({
            'publish': {
                'channels': ['foo'],
                'message': 'howdy'
            }
        }))
        self._valid(json.dumps({
            'publish': {
                'channels': ['foo', 'bar'],
                'message': 'howdy'
            }
        }))
        self._invalid(json.dumps({
            'publish': 'foo'
        }))
        self._invalid(json.dumps({
            'publish': {
                'channels': [],
                'message': 'howdy'
            }
        }))
        self._invalid(json.dumps({
            'publish': {
                'channels': 'foo',
                'message': 'howdy'
            }
        }))

    def test_trigger_schema(self):
        self._valid(json.dumps({
            'trigger': {
                'type': 'foo',
                'targets': ['howdy']
            }
        }))
        self._valid(json.dumps({
            'trigger': {
                'type': 'foo',
                'targets': ['howdy'],
                'params': 'bar'
            }
        }))
        self._valid(json.dumps({
            'trigger': {
                'type': 'foo',
                'targets': ['howdy'],
                'params': {
                    'foo': 'bar',
                    'howdy': 'yall'
                }
            }
        }))
        self._invalid(json.dumps({
            'trigger': 'foo'
        }))


class TestReactor(ReactorTestCase):

    def test_queue_event(self):
        event_dict = {
            'type': 'foo',
            'targets': ['bar']
        }
        message_dict = {
            'trigger': event_dict
        }
        message = json.dumps(message_dict)
        self.reactor.react(message)
        self.mock_redis.rpush.assert_called_with(
            self.reactor.event_queue.key,
            json.dumps({
                'cookie': 'dummy-cookie',
                'event': event_dict
            }))
        self.assertFalse(self.mock_redis.publish.called)

    def test_publish_message(self):
        socket_message_dict = {
            'publish': {
                'channels': ['foo'],
                'message': 'bar'
            }
        }
        socket_message = json.dumps(socket_message_dict)
        self.reactor.react(socket_message)
        self.mock_redis.publish.assert_called_with('foo', 'bar')
        self.assertFalse(self.mock_redis.rlpush.called)

    def test_publish_multiple_channels(self):
        channels = ['foo1', 'foo2']
        message = 'bar'
        socket_message_dict = {
            'publish': {
                'channels': channels,
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
            'subscribe': ['foo']
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
            'unsubscribe': ['foo']
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


class TestAuthBroker(ReactorTestCase):

    class MockAuthBroker(BaseWebSocketAuthBroker):
        can_listen = set()
        can_publish = set()
        can_target = set()

        def authorize(self, listen_channels=None, publish_channels=None,
                      event_targets=None):
            if listen_channels is not None:
                if not self.can_listen.issuperset(listen_channels):
                    self.fail()
            if publish_channels is not None:
                if not self.can_publish.issuperset(publish_channels):
                    self.fail()
            if event_targets is not None:
                if not self.can_target.issuperset(event_targets):
                    self.fail()

    def setUp(self):
        ReactorTestCase.setUp(self)
        self.auth = self.MockAuthBroker(self.environ, DEFAULT_SERVER_CONFIG)
        self.reactor.auth = self.auth

    def test_authorize_subscribe(self):
        self.auth.can_listen.add('foo')
        self.reactor.react(json.dumps({
            'subscribe': ['foo']
        }))
        self.mock_pubsub.subscribe.assert_called_once_with(['foo'])
        self.mock_pubsub.subscribe.reset_mock()
        with self.assertRaises(NotAuthorized):
            self.reactor.react(json.dumps({
                'subscribe': ['bar']
            }))
        self.assertFalse(self.mock_pubsub.subscribe.called)

    def test_authorize_publish(self):
        self.auth.can_publish.add('foo')
        self.reactor.react(json.dumps({
            'publish': {
                'channels': ['foo'],
                'message': 'howdy'
            }
        }))
        self.mock_redis.publish.assert_called_once_with('foo', 'howdy')
        self.mock_redis.publish.reset_mock()
        with self.assertRaises(NotAuthorized):
            self.reactor.react(json.dumps({
                'publish': {
                    'channels': ['bar'],
                    'message': 'howdy'
                }
            }))
        self.assertFalse(self.mock_redis.publish.called)

    def test_authorize_trigger(self):
        self.auth.can_target.add('foo')
        self.reactor.react(json.dumps({
            'trigger': {
                'targets': ['foo'],
                'type': 'howdy'
            }
        }))
        self.mock_redis.rpush.assert_called_once_with(
            self.reactor.event_queue.key,
            json.dumps({
                'cookie': 'dummy-cookie',
                'event': {
                    'targets': ['foo'],
                    'type': 'howdy'
                }
            }))
        self.mock_redis.rpush.reset_mock()
        with self.assertRaises(NotAuthorized):
            self.reactor.react(json.dumps({
                'trigger': {
                    'targets': ['bar'],
                    'type': 'howdy'
                }
            }))
        self.assertFalse(self.mock_redis.rpush.called)
