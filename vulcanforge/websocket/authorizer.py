# -*- coding: utf-8 -*-

"""
authorizer

@author: U{tannern<tannern@gmail.com>}
"""
import bson
from pylons import tmpl_context as c, app_globals as g
from vulcanforge.common.util.pattern_method_map import PatternMethodMap
from vulcanforge.messaging.model import Conversation
from vulcanforge.project.model import Project
from vulcanforge.websocket.exceptions import NotAuthorized


import logging
LOG = logging.getLogger(__name__)


class WebSocketAuthorizer(object):
    _listen_map = PatternMethodMap()
    _publish_map = PatternMethodMap()
    _target_map = PatternMethodMap()

    @staticmethod
    def fail(msg=None):
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

    @_publish_map.decorate(r'^user\.([^\.]+)$')
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

    @_listen_map.decorate(r'^project\.([^\.]+)$')
    @_target_map.decorate(r'^project\.([^\.]+)$')
    def project(self, name, match):
        shortname = match.group(1)
        project = self._get_project_by_shortname(shortname)
        if not g.security.has_access(project, 'read'):
            LOG.debug("user does not have read access to %r", shortname)
            self.fail()

    @_listen_map.decorate(r'^project\.([^\.]+).chat$')
    @_target_map.decorate(r'^project\.([^\.]+).chat$')
    def project_chat(self, name, match):
        shortname = match.group(1)
        project = self._get_project_by_shortname(shortname)
        chat_config = project.get_app_configs_by_kind('chat').first()
        if chat_config is None:
            LOG.debug("no chat tool installed for %r", shortname)
            self.fail()
        if not g.security.has_access(chat_config, 'read'):
            LOG.debug("user does not have read access to %r chat", shortname)
            self.fail()

    @_listen_map.decorate(r'^system$')
    @_listen_map.decorate(r'^user\.([^\.]+)$')
    @_listen_map.decorate(r'^test\.(.+)$')
    @_publish_map.decorate(r'^test\.(.+)$')
    @_target_map.decorate(r'^test\.(.+)$')
    def allow(self, name, match):
        """
        Generic allow
        """
        pass

    @_publish_map.decorate(r'^system$')
    @_publish_map.decorate(r'^project\.([^\.]+)$')
    def deny(self, name, match):
        """
        Generic deny
        """
        self.fail()

    def _get_project_by_shortname(self, shortname):
        cursor = Project.query.find({'shortname': shortname})
        if cursor.count() == 0:
            LOG.debug("project not found %r", shortname)
            self.fail()
        if cursor.count() > 1:
            LOG.debug("multiple projects found for %r", shortname)
            self.fail()
        return cursor.first()
