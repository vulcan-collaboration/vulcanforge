# -*- coding: utf-8 -*-

"""
exceptions

@author: U{tannern<tannern@gmail.com>}
"""


class WebSocketException(Exception):
    pass


class InvalidMessageException(WebSocketException):
    pass


class NotAuthorized(WebSocketException):
    pass


class LostConnection(WebSocketException):
    pass
