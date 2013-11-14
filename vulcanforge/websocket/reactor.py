# -*- coding: utf-8 -*-

"""
reactor

@author: U{tannern<tannern@gmail.com>}
"""
import json
import jsonschema
from paste.deploy.converters import asint
from vulcanforge.common.util.filesystem import import_object
from vulcanforge.taskd.queue import RedisQueue
from vulcanforge.websocket import INCOMING_MESSAGE_SCHEMA
from vulcanforge.websocket.exceptions import InvalidMessageException


def _make_event_queue(config):
    api_path = config.get('event_queue.cls')
    if api_path:
        cls = import_object(api_path)
    else:
        cls = RedisQueue
    kwargs = {
        'host': config.get('event_queue.host', config['redis.host']),
        'port': asint(config.get('event_queue.port',
                                 config.get('redis.port', 6379))),
        'db': asint(config.get('event_queue.db',
                               config.get('redis.db', 0)))
    }
    if config.get('event_queue.namespace'):
        kwargs['namespace'] = config['event_queue.namespace']
    return cls(config.get('event_queue.name', 'event_queue'), **kwargs)


class MessageReactor(object):
    """
    One reactor created for each connection. Incoming messages from the client
    are passed to the `react` method.
    """
    incoming_message_schema = INCOMING_MESSAGE_SCHEMA

    def __init__(self, environ, config, auth, redis_client, pubsub_client):
        self.environ = environ
        self.config = config
        self.redis = redis_client
        self.pubsub = pubsub_client
        self.auth = auth
        self.event_queue = _make_event_queue(config)

    def react(self, message):
        """

        :param message: The message string to which the MessageReactor should
                        react.
        :type message: str, unicode
        """
        message = self.validate(message)
        self.authorize(message)
        subscribe_to = message.get('subscribe')
        if subscribe_to:
            self.subscribe(subscribe_to)
        unsubscribe_from = message.get('unsubscribe')
        if unsubscribe_from:
            self.unsubscribe(unsubscribe_from)
        publish = message.get('publish')
        if publish:
            self.publish(publish)
        trigger = message.get('trigger')
        if trigger:
            self.queue(trigger)

    def validate(self, message):
        """
        Converts message from JSON to dictionary and validates it's format.

        :param message: The message string to validate
        :type message: str, unicode
        :raises: InvalidMessageException
        :return: Converted message dictionary
        :rtype: dict
        """
        try:
            message = json.loads(message)
        except:
            raise InvalidMessageException("Invalid JSON")
        try:
            jsonschema.validate(message, self.incoming_message_schema)
        except jsonschema.ValidationError, e:
            raise InvalidMessageException(unicode(e))
        return message

    def authorize(self, message):
        listen_channels = set()
        publish_channels = set()
        event_targets = set()
        subscribe_to = message.get('subscribe')
        if subscribe_to:
            listen_channels.update(subscribe_to)
        publish = message.get('publish')
        if publish:
            publish_channels.update(publish['channels'])
        trigger = message.get('trigger')
        if trigger:
            event_targets.update(trigger['targets'])
        self.auth.authorize(listen_channels=listen_channels,
                            publish_channels=publish_channels,
                            event_targets=event_targets)

    def subscribe(self, channels):
        self.pubsub.subscribe(channels)

    def unsubscribe(self, channels):
        self.pubsub.unsubscribe(channels)

    def publish(self, publication):
        message = publication['message']
        for channel in publication['channels']:
            self.redis.publish(channel, message)

    def queue(self, event):
        event_info = {
            'event': event,
            'cookie': self.environ['HTTP_COOKIE']
        }
        self.event_queue.put(json.dumps(event_info))
