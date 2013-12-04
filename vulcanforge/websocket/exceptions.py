# -*- coding: utf-8 -*-

"""
exceptions

@author: U{tannern<tannern@gmail.com>}
"""


class WebSocketException(Exception):
    pass


class ConfigurationError(WebSocketException):
    pass


class InvalidMessageException(WebSocketException):
    pass


class NotAuthenticated(WebSocketException):
    pass


class NotAuthorized(WebSocketException):
    pass


class LostConnection(WebSocketException):
    pass
