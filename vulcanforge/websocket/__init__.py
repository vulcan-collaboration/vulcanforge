# -*- coding: utf-8 -*-

"""
__init__.py

@author: U{tannern<tannern@gmail.com>}
"""


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
