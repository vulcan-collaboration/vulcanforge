# -*- coding: utf-8 -*-
"""
app

@author: U{tannern<tannern@gmail.com>}
"""
from datetime import datetime, timedelta
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
        'admin', 'read', 'post', 'unmoderated_post', 'configure'
    ]
    permission_descriptions = {
        "admin": "edit access control to this tool",
        "read": "view messages",
        "post": "post messages",
        "configure": "create and edit channels"
    }
    reference_opts = dict(
        Application.reference_opts,
        can_reference=True,
        can_create=False
    )
    artifacts = {
        'session': chat_model.ChatSession
    }
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

    def install(self, project, acl=None):
        super(ForgeChatApp, self).install(project, acl=acl)

    def get_active_session(self):
        query = {
            'app_config_id': self.config._id,
            'mod_date': {
                '$gte': datetime.utcnow() - timedelta(hours=12)
            }
        }
        session = chat_model.ChatSession.query.get(**query)
        if session is None:
            session = chat_model.ChatSession()
            session.flush_self()
        return session
