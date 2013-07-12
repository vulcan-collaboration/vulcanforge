# -*- coding: utf-8 -*-

"""
authorizer

@author: U{tannern<tannern@gmail.com>}
"""
import bson
from pylons import tmpl_context as c
from vulcanforge.common.util.pattern_method_map import PatternMethodMap
from vulcanforge.messaging.model import Conversation
from vulcanforge.websocket.exceptions import NotAuthorized


class WebSocketAuthorizer(object):
    _listen_map = PatternMethodMap()
    _publish_map = PatternMethodMap()
    _target_map = PatternMethodMap()

    def fail(self, msg=None):
        if msg:
            raise NotAuthorized(msg)
        else:
            raise NotAuthorized()

    def can_listen(self, name):
        self._listen_map.apply(name, context_self=self)

    def can_publish(self, name):
        self._publish_map.apply(name, context_self=self)

    def can_target(self, name):
        self._target_map.apply(name, context_self=self)

    @_listen_map.decorate(r'^user\.username\.(.+)$')
    @_publish_map.decorate(r'^user\.username\.(.+)$')
    def user_username(self, name, match):
        username = match.group(1)
        if c.user.username != username:
            self.fail()

    @_listen_map.decorate(r'^chat\.id\.(.+)$')
    @_publish_map.decorate(r'^chat\.id\.(.+)$')
    def chat_id(self, name, match):
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
    @_target_map.decorate(r'^test\.(.+)$')
    def test(self, name, match):
        pass


