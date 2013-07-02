# -*- coding: utf-8 -*-

"""
__init__.py

@author: U{tannern<tannern@gmail.com>}
"""
import sys


EVENT_QUEUE_KEY = 'queue.event'
INCOMING_MESSAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "subscribe": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "unsubscribe": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "publish": {
            "type": "object",
            "properties": {
                "channels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "message": {}
            },
            "required": ["channels", "message"],
            "additionalProperties": False
        },
        "trigger": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string"
                },
                "targets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "params": {}
            },
            "required": ["type", "targets"],
            "additionalProperties": False
        }
    },
    "additionalProperties": False
}
DEFAULT_SERVER_CONFIG = {
    'websocket.host': 'localhost',
    'websocket.port': 8001,
    'websocket.process_count': 1,
    'websocket.auth_class': 'vulcanforge.websocket.auth:BaseWebSocketAuth'
}


def get_config(filename):
    import ConfigParser
    parser = ConfigParser.ConfigParser()
    with open(filename, 'r') as fp:
        parser.readfp(fp)
    section_name = "websocketserver"
    config = DEFAULT_SERVER_CONFIG
    for option in parser.options(section_name):
        config[option] = parser.get(section_name, option)
    return config


def load_auth(config):
    path = config['websocket.auth_class']
    modulename, classname = path.rsplit(':', 1)
    module = __import__(modulename, fromlist=[classname])
    return getattr(module, classname)
