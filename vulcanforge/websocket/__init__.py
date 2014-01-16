# -*- coding: utf-8 -*-

"""
__init__.py

@author: U{tannern<tannern@gmail.com>}
"""


import multiprocessing


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
    'websocket.port': 8002,
    'websocket.process_count': multiprocessing.cpu_count(),
    'websocket.auth_broker': 'vulcanforge.websocket.auth_broker:'
                              'WebSocketAuthBroker',
    'event_queue.name': 'event_queue',
    'event_queue.namespace': 'eventd'
}


def get_config(filename, section_name="websocketserver"):
    import ConfigParser
    parser = ConfigParser.ConfigParser()
    with open(filename, 'r') as fp:
        parser.readfp(fp)
    config = DEFAULT_SERVER_CONFIG
    for option in parser.options(section_name):
        config[option] = parser.get(section_name, option)
    return config


def load_auth_broker(config):
    path = config['websocket.auth_broker']
    modulename, classname = path.rsplit(':', 1)
    module = __import__(modulename, fromlist=[classname])
    return getattr(module, classname)
