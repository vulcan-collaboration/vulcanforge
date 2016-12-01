# -*- coding: utf-8 -*-

"""
model

@author: U{tannern<tannern@gmail.com>}
"""
from datetime import datetime
import os
import logging
from bson import ObjectId
from ming.odm import FieldProperty, RelationProperty, ForeignIdProperty
import pymongo
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
            'project_id',
            'mod_date'
        ]

    type_s = 'ChatChannel'

    last_post_datetime = FieldProperty(datetime, if_missing=datetime.utcnow)
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
        return os.path.join(self.app.url, 'session', str(self._id))

    def get_discussion_thread(self, data=None, generate_if_missing=True):
        """
        Return the discussion thread for this artifact (possibly made more
        specific by the message_data)
        """
        thread_class = self.thread_class()
        thread = thread_class.query.get(ref_id=self.index_id())
        if thread is None and generate_if_missing:
            idx = self.index() or {}
            thread = thread_class(
                app_config_id=self.app_config_id,
                discussion_id=self._id,
                ref_id=idx.get('id', self.index_id()),
                subject='%s discussion' % idx.get('title_s', self.link_text()))
            thread.flush_self()
        return thread


class ChatThread(Thread):

    class __mongometa__:
        polymorphic_identity = 'chat_thread'
        indexes = [
            ('ref_id',),
            ('ref_id', 'app_config_id'),
            (
                ('app_config_id', pymongo.ASCENDING),
                ('last_post_date', pymongo.DESCENDING),
                ('mod_date', pymongo.DESCENDING)
            )
        ]

    kind = FieldProperty(str, if_missing='chat_thread')
    discussion_id = ForeignIdProperty(ChatSession)
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
        return self.discussion.url()


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

    def notify(self):
        pass

    def get_publish_channels(self):
        channels = super(ChatPost, self).get_publish_channels()
        active_session = self.app.get_active_session()
        thread = active_session.get_discussion_thread()
        if self.thread_id == thread._id:
            channels.append('project.{}.chat'.format(self.project.shortname))
        return channels

    def url(self):
        return self.discussion.url()

    def approve(self):
        super(ChatPost, self).approve()
        self.discussion.last_post_datetime = self.timestamp


class ChatAttachment(DiscussionAttachment):

    class __mongometa__(object):
        polymorphic_identity = "chat_attachment"

    kind = FieldProperty(str, if_missing='chat_attachment')
