# -*- coding: utf-8 -*-

"""
debugutil

@author: U{tannern<tannern@gmail.com>}
"""
from datetime import datetime
import json
from pylons import app_globals as g
from tg import expose
from tg.decorators import with_trailing_slash
from vulcanforge.common.controllers import BaseController


class DebugUtilRootController(BaseController):

    def _check_security(self):
        g.security.require_access(g.get_site_admin_project(), 'admin')


    @expose('_debug_util_/index.html')
    def index(self):
        return {}

    @expose('_debug_util_/solr.html')
    def solr(self, q=None, json_params=None):
        if q is None:
            q = ""
        if json_params is None:
            json_params = "{}"
        params = json.loads(json_params)
        start_dt = datetime.utcnow()
        result = g.solr.search(q, **params)
        duration = datetime.utcnow() - start_dt
        return {
            'q': q,
            'json_params': json_params,
            'duration': duration,
            'result': json.dumps(result.__dict__, indent=2)
        }

    @expose('json')
    @expose('_debug_util_/redis.html')
    @with_trailing_slash
    def redis(self, key=None):
        redis = g.cache.redis
        getters = {
            'string': redis.get,
            'hash': redis.hgetall,
            'list': lambda k: redis.lrange(k, 0, redis.llen(k)),
            'set': lambda k: list(redis.smembers(k))
        }
        result = {
            'keys': redis.keys('*')
        }
        if key is not None:
            if redis.exists(key):
                key_type = redis.type(key)
                result.update(**{
                    'selected': {
                        'key': key,
                        'exists': True,
                        'type': key_type,
                        'ttl': redis.ttl(key),
                        'value': getters[key_type](key)
                    }
                })
            else:
                result.update(selected={
                    'key': key,
                    'exists': False
                })
        return result
