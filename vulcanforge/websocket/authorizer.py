# -*- coding: utf-8 -*-

"""
authorizer

@author: U{tannern<tannern@gmail.com>}
"""
import re
import bson
from pylons import tmpl_context as c
from vulcanforge.messaging.model import Conversation
from vulcanforge.websocket.exceptions import NotAuthorized


class PatternMethodMap(object):

    def __init__(self):
        self._map = []

    def register(self, regex, method):
        assert isinstance(regex, basestring), "regex must be a basestring"
        assert hasattr(method, '__call__'), "method must be callable"
        self._map.append((re.compile(regex), method,))

    def decorate(self, regex):
        def wrapper(method):
            self.register(regex, method)
            return method
        return wrapper

    def lookup(self, name):
        assert isinstance(name, basestring), "name must be a basestring"
        for pattern, method in self._map:
            match = pattern.match(name)
            if match is not None:
                return method, match
        raise KeyError("Pattern match not found")

    def apply(self, name, context_self=None):
        method, match = self.lookup(name)
        if method is not None:
            if context_self is not None:
                return method(context_self, name, match)
            else:
                return method(name, match)
        return None


class WebSocketAuthorizer(object):
    _listen_map = PatternMethodMap()
    _publish_map = PatternMethodMap()
    _trigger_map = PatternMethodMap()

    def fail(self, msg=None):
        if msg:
            raise NotAuthorized(msg)
        else:
            raise NotAuthorized()

    def can_listen(self, name):
        self._listen_map.apply(name, context_self=self)

    def can_publish(self, name):
        self._publish_map.apply(name, context_self=self)

    def can_trigger(self, name):
        self._trigger_map.apply(name, context_self=self)

    @_listen_map.decorate(r'^user\.id\.(.+)$')
    @_publish_map.decorate(r'^user\.id\.(.+)$')
    def user_id(self, name, match):
        try:
            user_id = bson.ObjectId(match.group(1))
        except ValueError:
            self.fail()
        if c.user._id != user_id:
            self.fail()

    @_listen_map.decorate(r'^user\.username\.(.+)$')
    @_publish_map.decorate(r'^user\.username\.(.+)$')
    def user_username(self, name, match):
        username = match.group(1)
        if c.user.username != username:
            self.fail()

    @_listen_map.decorate(r'^chat\.id\.(.+)$')
    @_publish_map.decorate(r'^chat\.id\.(.+)$')
    def chat(self, name, match):
        try:
            _id = bson.ObjectId(match.group(1))
        except ValueError:
            self.fail()
        convo = Conversation.query.get(_id=_id)
        if convo is None:
            self.fail()
        status = convo.get_status_for_user_id(c.user._id, create=False)
        if status is None:
            self.fail()

    @_listen_map.decorate(r'^system$')
    def system_listen(self, name, match):
        pass  # allow listening to system channel

    @_publish_map.decorate(r'^system$')
    def system_publish(self, name, match):
        self.fail()  # do not allow publishing to system channel

    @_listen_map.decorate(r'^test\.(.+)$')
    @_publish_map.decorate(r'^test\.(.+)$')
    def test_channel(self, name, match):
        pass  # allow both for test channels


