# -*- coding: utf-8 -*-

"""
controllers

@author: U{tannern<tannern@gmail.com>}
"""
import bson
from pylons import tmpl_context as c
import pymongo
from tg import expose
from webob.exc import HTTPNotFound
from vulcanforge.common.controllers import BaseController
from vulcanforge.discussion.controllers import AppDiscussionController
from vulcanforge.tools.chat import TEMPLATE_DIR


import logging
from vulcanforge.tools.chat.model import ChatSession

LOG = logging.getLogger(__name__)


class RootController(BaseController):

    def __init__(self):
        self._discuss = AppDiscussionController()

    @expose(TEMPLATE_DIR + 'index.html')
    def index(self, page=0, limit=50, **kwargs):
        cursor = ChatSession.query.find({
            'app_config_id': c.app.config._id
        })
        cursor.sort('mod_date', pymongo.DESCENDING)
        cursor.skip(page*limit)
        cursor.limit(limit)
        return {
            'chat_sessions': cursor.all(),
            'count': cursor.count(),
            'page': page,
            'limit': limit
        }

    @expose(TEMPLATE_DIR + 'chat.html')
    def session(self, chat_id=None, **kwargs):
        if chat_id is None:
            session = c.app.get_active_session()
        else:
            try:
                chat_id = bson.ObjectId(chat_id)
            except TypeError:
                raise HTTPNotFound()
            session = ChatSession.query.get(_id=chat_id)
        return {
            'chat_session': session,
            'thread': session.discussion_thread
        }


class RootRestController(BaseController):
    pass
