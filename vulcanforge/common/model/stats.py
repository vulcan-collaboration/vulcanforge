# -*- coding: utf-8 -*-
import ming

from .session import main_doc_session


class Stats(ming.Document):
    class __mongometa__:
        session = main_doc_session
        name = 'stats'
