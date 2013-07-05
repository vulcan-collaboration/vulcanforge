# -*- coding: utf-8 -*-
"""Error controller"""
import random

from tg import request, expose, config

__all__ = ['ErrorController']

MESSAGES = {
    "default": [
        "We're sorry but we weren't able to process this request.",
    ],
    400: [
        "Your request is invalid.",
        "Are you sure you did that right?",
        "Your request is illogical.",
    ],
    403: [
        "You don't have permission to do that.",
    ],
    404: [
        "We can't find this thing you're looking for.",

        "Nothing to see here. Move along.",

        "These aren't the droids you're looking for. Move along.",

        "Maybe if you try again and again you may see something else.",

        "OK, that's the last time we let you drive.",

        "If you're reading this, it means this page is no more. "
            "It's probably not your fault.",

        "Missing: One Page",

        "Your lucky numbers for today: 4, 0, 4",

        "This page is only viewable by Jimmy Hoffa, Amelia Earhart, "
            "Jim Morrison, and Howard Hughes.",

        "Great, now you've gone and done it. You've broken the internet. "
            "Way to go!",

        "You had better pull over and ask for directions.",
    ],
}


class ErrorController(object):

    @expose('jinja:vulcanforge.common:templates/error.html')
    def document(self, *args, **kwargs):
        """Render the error document"""
        resp = request.environ.get('pylons.original_response')
        code = -1
        status_text = ""
        if resp:
            code = resp.status_int
            status_text = resp.status[4:]
        message = self._get_message_for_resp(resp)

        return {
            'code': code,
            'code_class': code / 100,
            'status_text': status_text,
            'message': message,
            'resp': resp,
            'hide_sidebar': True,
            'hide_header': True,
            "site_issues_url": config.get("site_issues_url")
        }

    def _get_message_for_resp(self, resp):
        code = resp.status_int
        message = request.environ.get('error_message', None)
        if message is not None:
            return message
        messages = MESSAGES.get(code, MESSAGES['default'])
        return random.choice(messages)
