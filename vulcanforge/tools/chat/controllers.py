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

    def __init__(self):
        self._discuss = AppDiscussionController()

    @expose(TEMPLATE_DIR + 'chat.html')
    def index(self, **kwargs):
        session = c.app.get_active_session()
        return {
            'session_id': session._id
        }


class RootRestController(BaseController):
    pass
