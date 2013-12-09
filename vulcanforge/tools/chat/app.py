# -*- coding: utf-8 -*-
"""
app

@author: U{tannern<tannern@gmail.com>}
"""
from datetime import datetime, timedelta
from pylons import app_globals as g
import pymongo
from vulcanforge.common.app import Application
from vulcanforge.common.types import SitemapEntry
from vulcanforge.tools import chat
from vulcanforge.tools.chat import model as chat_model,\
    controllers as chat_controllers


class ForgeChatApp(Application):
    __version__ = chat.__version__
    status = 'alpha'
    tool_label = 'Chat'
    default_mount_label = 'Chat'
    default_mount_point = 'chat'
    sitemap = []
    permissions = [
        'admin', 'read', 'post', 'moderate', 'unmoderated_post'
    ]
    permission_descriptions = {
        "admin": "edit access control to this tool",
        "read": "view messages",
        "moderate": "moderate new messages",
        "post": "post messages",
        "unmoderated_post": "add content without moderation"
    }
    default_acl = {
        'Admin': permissions,
        'Developer': ['moderate'],
        '*authenticated': ['post', 'unmoderated_post'],
        '*anonymous': ['read']
    }
    reference_opts = dict(
        Application.reference_opts,
        can_reference=True,
        can_create=False
    )
    artifacts = {
        'session': chat_model.ChatSession
    }
    DiscussionClass = chat_model.ChatSession
    PostClass = chat_model.ChatPost
    AttachmentClass = chat_model.ChatAttachment

    def __init__(self, project, config):
        super(ForgeChatApp, self).__init__(project, config)
        self.root = chat_controllers.RootController()
        self.api_root = chat_controllers.RootRestController()

    @property
    def sitemap(self):
        return [
            SitemapEntry(self.config.options.mount_label, self.url)
        ]

    def sidebar_menu(self):
        return [
            SitemapEntry('Transcripts', self.url)
        ]

    def install(self, project, acl=None):
        super(ForgeChatApp, self).install(project, acl=acl)

    def get_active_session(self):
        with g.context_manager.push(app_config_id=self.config._id):
            query = {
                'app_config_id': self.config._id,
                'mod_date': {
                    '$gte': datetime.utcnow() - timedelta(hours=12)
                }
            }
            cursor = chat_model.ChatSession.query.find(query)
            cursor.sort('mod_date', pymongo.DESCENDING)
            session = cursor.first()
            if session is None:
                session = chat_model.ChatSession()
                session.flush_self()
            return session

    def get_active_thread(self):
        with g.context_manager.push(app_config_id=self.config._id):
            session = self.get_active_session()
            return session.get_discussion_thread()
