# -*- coding: utf-8 -*-
from logging.handlers import WatchedFileHandler
from logging import Formatter

import tg


class StatsHandler(WatchedFileHandler):
    fields = (
        'action',
        'action_type',
        'tool_type',
        'tool_mount',
        'project',
        'neighborhood',
        'username',
        'url',
        'ip_address'
    )

    def __init__(self, strftime_pattern, module='vulcanforge', page=1, **kwargs):
        self.page = page
        self.module = module
        WatchedFileHandler.__init__(self, strftime_pattern, **kwargs)

    def emit(self, record):
        if not hasattr(record, 'action'):
            return
        kwpairs = dict(
            module=self.module,
            page=self.page)
        for name in self.fields:
            kwpairs[name] = getattr(record, name, None)
        kwpairs.update(getattr(record, 'kwpairs', {}))
        record.kwpairs = ','.join(
            '%s=%s' % (k, v) for k, v in sorted(kwpairs.iteritems())
            if v is not None)
        record.exc_info = None  # Never put tracebacks in the rtstats log
        WatchedFileHandler.emit(self, record)


def prefix_lines(text, prefix):
    if text.endswith('\n'):
        text = text[:-1]
    text = text.replace('\n', '\n'+prefix)
    return text


class BlockFormatter(Formatter):
    """
    Formats a log msg so that all lines except the first are prefixed with
    a given string.

    Useful for grouping messages.

    """

    def __init__(self, fmt=None, datefmt=None, prefix=None):
        super(BlockFormatter, self).__init__(fmt=fmt, datefmt=datefmt)
        if prefix is None:
            prefix = tg.config.get('log_prefix', '>->->')+' '
        self.prefix = prefix

    def format(self, record):
        s = super(BlockFormatter, self).format(record)
        return prefix_lines(s, self.prefix)
