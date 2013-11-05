# -*- coding: utf-8 -*-

"""
controllers

@author: U{tannern<tannern@gmail.com>}
"""
from pylons import tmpl_context as c
from tg import expose
from vulcanforge.common.controllers import BaseController
from vulcanforge.discussion.controllers import AppDiscussionController
from vulcanforge.discussion.widgets import ThreadWidget
from vulcanforge.tools.chat import TEMPLATE_DIR


import logging

LOG = logging.getLogger(__name__)


class RootController(BaseController):

    class Widgets(BaseController.Widgets):
        thread = ThreadWidget(
            page=None, limit=None, page_size=None, count=None,
            style='linear')

    def __init__(self):
        self._discuss = AppDiscussionController()

    @expose(TEMPLATE_DIR + 'chat.html')
    def index(self, page=0, limit=10, **kwargs):
        session = c.app.get_active_session()
        c.thread = self.Widgets.thread
        return {
            'session': session,
            'thread': session.discussion_thread,
            'page': page,
            'limit': limit
        }


class RootRestController(BaseController):
    pass
