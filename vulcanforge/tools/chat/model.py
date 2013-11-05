# -*- coding: utf-8 -*-

"""
model

@author: U{tannern<tannern@gmail.com>}
"""
import os
from bson import ObjectId
from ming.odm import ForeignIdProperty, FieldProperty
from vulcanforge.common.model.session import artifact_orm_session
from vulcanforge.discussion.model import AbstractPost, PostHistory, \
    DiscussionAttachment, AbstractThread, Discussion


class ChatSession(Discussion):

    class __mongometa__(object):
        session = artifact_orm_session
        name = 'chat_session'
        indexes = [
            'app_config_id',
            'project_id'
        ]

    type_s = 'ChatChannel'

    @classmethod
    def attachment_class(cls):
        return ChatAttachment

    @classmethod
    def thread_class(cls):
        return ChatThread

    @classmethod
    def by_id(cls, id_, suppress=True):
        try:
            id_ = ObjectId(id_)
        except ValueError:
            if not suppress:
                raise
            return None
        else:
            return cls.query.get(_id=id_)

    def __json__(self):
        return {
            'id': str(self._id),
            'url': self.url()
        }

    def url(self):
        return os.path.join(self.app.url, str(self._id))


class ChatPostHistory(PostHistory):

    class __mongometa__(object):
        name = 'post_history'

    artifact_id = ForeignIdProperty('ChatPost')


class ChatThread(AbstractThread):

    class __mongometa__:
        name = 'forum_thread'
        indexes = ['flags']

    type_s = 'ChatThread'

    @staticmethod
    def discussion_class():
        return ChatSession

    @classmethod
    def attachment_class(cls):
        return ChatAttachment

    @staticmethod
    def post_class():
        return ChatPost


class ChatPost(AbstractPost):

    class __mongometa__(object):
        session = artifact_orm_session
        name = 'chat_post'
        history_class = ChatPostHistory


class ChatAttachment(DiscussionAttachment):

    class __mongometa__(object):
        polymorphic_identity = "ChatAttachment"
