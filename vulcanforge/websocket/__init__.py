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
            "type": ["string", "array"],
            "items": {"type": "string"},
            "additionalProperties": False
        },
        "unsubscribe": {
            "type": ["string", "array"],
            "items": {"type": "string"},
            "additionalProperties": False
        },
        "publish": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": ["string", "array"],
                    "items": {"type": "string"},
                },
                "message": {}
            },
            "required": ["channel", "message"],
            "additionalProperties": False
        },
        "trigger": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string"
                },
                "target": {
                    "type": "string"
                },
                "params": {}
            },
            "required": ["type", "target"],
            "additionalProperties": False
        }
    },
    "additionalProperties": False
}
