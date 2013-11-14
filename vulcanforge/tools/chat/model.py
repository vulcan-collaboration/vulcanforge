# -*- coding: utf-8 -*-

"""
model

@author: U{tannern<tannern@gmail.com>}
"""
import os
import logging
from bson import ObjectId
from ming.odm import FieldProperty, RelationProperty
from vulcanforge.common.model.session import artifact_orm_session
from vulcanforge.discussion.model import Discussion, \
    PostHistory, DiscussionAttachment, AbstractPost, Thread


LOG = logging.getLogger(__name__)


class ChatSession(Discussion):

    class __mongometa__(object):
        session = artifact_orm_session
        name = 'chat_session'
        indexes = [
            'app_config_id',
            'project_id'
        ]

    type_s = 'ChatChannel'

    threads = RelationProperty('ChatThread')
    posts = RelationProperty('ChatPost')

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


class ChatThread(Thread):

    class __mongometa__:
        polymorphic_identity = 'chat_thread'

    kind = FieldProperty(str, if_missing='chat_thread')
    discussion = RelationProperty(ChatSession)
    posts = RelationProperty('ChatPost', via='thread_id')
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

    def url(self):
        return self.app.url


class ChatPost(AbstractPost):

    class __mongometa__(object):
        polymorphic_identity = "chat_post"
        history_class = PostHistory

    kind = FieldProperty(str, if_missing='chat_post')

    thread = RelationProperty(ChatThread)
    discussion = RelationProperty(ChatSession)

    @classmethod
    def attachment_class(cls):
        return ChatAttachment

    def get_publish_channels(self):
        channels = super(ChatPost, self).get_publish_channels()
        active_session = self.app.get_active_session()
        thread = active_session.get_discussion_thread()
        if self.thread_id == thread._id:
            channels.append('project.{}.chat'.format(self.project.shortname))
        return channels

    def url(self):
        return self.app.url


class ChatAttachment(DiscussionAttachment):

    class __mongometa__(object):
        polymorphic_identity = "chat_attachment"

    kind = FieldProperty(str, if_missing='chat_attachment')
