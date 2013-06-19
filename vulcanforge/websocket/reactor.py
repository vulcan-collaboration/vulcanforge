# -*- coding: utf-8 -*-

"""
reactor

@author: U{tannern<tannern@gmail.com>}
"""
import json
import jsonschema
from vulcanforge.websocket import EVENT_QUEUE_KEY, INCOMING_MESSAGE_SCHEMA
from vulcanforge.websocket.authorization import MessageAuthorizer
from vulcanforge.websocket.exceptions import InvalidMessageException


class MessageReactor(object):
    """
    One reactor created for each connection. Incoming messages from the client
    are passed to the `react` method.
    """
    authorizer_class = MessageAuthorizer
    event_queue_key = EVENT_QUEUE_KEY
    incoming_message_schema = INCOMING_MESSAGE_SCHEMA

    def __init__(self, redis_client, pubsub_client):
        self.redis_client = redis_client
        self.pubsub_client = pubsub_client
        self.authorizer = self.authorizer_class(redis_client, pubsub_client)

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
        publication = message.get('publish')
        if publication:
            self.publish(publication)
        event = message.get('trigger')
        if event:
            self.queue(event)

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
        self.authorizer.authorize(message)

    def subscribe(self, channels):
        if isinstance(channels, basestring):
            channels = [channels]
        self.pubsub_client.subscribe(channels)

    def unsubscribe(self, channels):
        if isinstance(channels, basestring):
            channels = [channels]
        self.pubsub_client.unsubscribe(channels)

    def publish(self, publication):
        channels = publication['channel']
        message = publication['message']
        if isinstance(channels, basestring):
            channels = [channels]
        for channel in channels:
            self.redis_client.publish(channel, message)

    def queue(self, event):
        self.redis_client.rpush(self.event_queue_key, event)
