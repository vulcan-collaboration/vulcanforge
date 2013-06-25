# -*- coding: utf-8 -*-

"""
reactor

@author: U{tannern<tannern@gmail.com>}
"""
import json
import jsonschema
from vulcanforge.websocket import EVENT_QUEUE_KEY, INCOMING_MESSAGE_SCHEMA
from vulcanforge.websocket.exceptions import InvalidMessageException


class MessageReactor(object):
    """
    One reactor created for each connection. Incoming messages from the client
    are passed to the `react` method.
    """
    event_queue_key = EVENT_QUEUE_KEY
    incoming_message_schema = INCOMING_MESSAGE_SCHEMA

    def __init__(self, config, redis_client, pubsub_client):
        self.config = config
        self.redis = redis_client
        self.pubsub = pubsub_client
        self.authorizer_class = self._load_authorizer()
        self.authorizer = self.authorizer_class()

    def _load_authorizer(self):
        path = self.config['websocket.message_authorizer']
        modulename, classname = path.rsplit(':', 1)
        module = __import__(modulename, fromlist=[classname])
        return getattr(module, classname)

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
        self.authorizer.authorize(listen_channels=listen_channels,
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
        self.redis.rpush(self.event_queue_key, event)
