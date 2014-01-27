import logging
import json

from redis import StrictRedis

LOG = logging.getLogger(__name__)


class RedisCache(object):
    """
    A wrapper for redis with some forge-specific functionality.

    default_timeout is an integer (seconds), a datetime.timedelta, or None

    """
    def __init__(self, default_timeout=None, conn=None, prefix='', **kw):
        if conn:
            self.redis = conn
        else:
            self.redis = StrictRedis(**kw)
        self.default_timeout = default_timeout
        self.prefix = prefix

    def make_keyname(self, name):
        return self.prefix + name

    def get(self, name):
        return self.redis.get(self.make_keyname(name))

    def set(self, name, value, expiration=None):
        name = self.make_keyname(name)
        if expiration is None:
            expiration = self.default_timeout
        if expiration:
            return self.redis.setex(name, expiration, value)
        else:
            return self.redis.set(name, value)

    def delete(self, *names):
        return self.redis.delete(*[self.make_keyname(name) for name in names])

    def hget(self, name, key):
        return self.redis.hget(self.make_keyname(name), key)

    def hset(self, name, key, value, expiration=None):
        name = self.make_keyname(name)
        if expiration is None:
            expiration = self.default_timeout
        if expiration:
            pipe = self.redis.pipeline()
            pipe.hset(name, key, value).expire(name, expiration)
            return pipe.execute()
        else:
            return self.redis.hset(name, key, value)

    def hmset(self, name, mapping, expiration=None):
        name = self.make_keyname(name)
        if expiration is None:
            expiration = self.default_timeout
        if expiration:
            pipe = self.redis.pipeline()
            return pipe.hmset(name, mapping).expire(name, expiration).execute()
        else:
            return self.redis.hmset(name, mapping)

    def hgetall(self, name):
        return self.redis.hgetall(self.make_keyname(name))

    def hdel(self, name, *keys):
        return self.redis.hdel(self.make_keyname(name), *keys)

    def _from_json(self, name, value):
        try:
            value = json.loads(value)
        except ValueError:
            LOG.warn('Invalid json cached in %s', name)
            value = None
        return value

    def get_json(self, name):
        result = self.get(name)
        if result:
            result = self._from_json(name, result)
        return result

    def set_json(self, name, value, expiration=None):
        try:
            value_json = json.dumps(value)
        except TypeError:
            LOG.warn('Cannot cache to %s -- invalid json %s', name, value)
        else:
            return self.set(name, value_json, expiration=expiration)

    def hget_json(self, name, key):
        result = self.hget(name, key)
        if result:
            result = self._from_json(','.join((name, key)), result)
        return result

    def hset_json(self, name, key, value, expiration=None):
        try:
            value_json = json.dumps(value)
        except TypeError:
            LOG.warn('Cannot cache to %s -- invalid json %s', name, value)
        else:
            return self.hset(name, key, value_json, expiration=expiration)

    def clear(self):
        self.redis.flushdb()
