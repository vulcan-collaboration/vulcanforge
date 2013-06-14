import logging
from functools import wraps

import redis
from redis.exceptions import ConnectionError

from .exceptions import QueueConnectionError

LOG = logging.getLogger(__name__)


def convert_conn_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionError:
            raise QueueConnectionError("Connection failed to redis")
    return wrapper


class RedisQueue(object):
    """Simple Queue with Redis Backend

    Borrowed from
    http://peter-hoffmann.com/2012/python-simple-queue-redis-queue.html
      (if found, please return)

    """
    def __init__(self, name, namespace='taskd', conn=None, **redis_kwargs):
        """The default connection parameters are:
        host='localhost', port=6379, db=0"""
        if conn:
            self.__db = conn
        else:
            self.__db = redis.Redis(**redis_kwargs)
        self.key = '%s:%s' % (namespace, name)

    @convert_conn_error
    def qsize(self):
        """Return the approximate size of the queue."""
        return self.__db.llen(self.key)

    @convert_conn_error
    def empty(self):
        """Return True if the queue is empty, False otherwise."""
        return self.qsize() == 0

    @convert_conn_error
    def put(self, item):
        """Put item into the queue."""
        self.__db.rpush(self.key, item)

    @convert_conn_error
    def get(self, block=True, timeout=None):
        """Remove and return an item from the queue.

        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available.

        """
        if block:
            item = self.__db.blpop(self.key, timeout=timeout)
        else:
            item = self.__db.lpop(self.key)

        if item:
            item = item[1]

        return item

    @convert_conn_error
    def get_nowait(self):
        """Equivalent to get(False)."""
        return self.get(False)
