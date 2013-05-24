import logging
import hashlib

from webhelpers.html import literal
from pylons import app_globals as g, tmpl_context as c
from tg import request, response
from tg.decorators import Decoration, override_template
from vulcanforge.common.controllers.decorators import controller_decorator

LOG = logging.getLogger(__name__)


class BaseCacheDecorator(object):
    """
    Base class decorator for caching the result of a function. Uses the Redis
    hash object with input params key and name.

    :param timeout int seconds
    :param key str key to use with redis. Can incorporate context by using
        format string with "c", e.g.: "preferences-{c.user.username}"
    :param name str name to use with redis. Can incorporate context by using
        format string with "c", e.g.: "preferences-{c.user.username}"
    :param allow_overrides bool allow force run the function without checking
        the cache
    :param override_kwarg str keyword argument passed to the function that
        causes force run of the function

    """
    def __init__(self, name=None, key=None, timeout=None, allow_overrides=False,
                 override_kwarg='force'):
        self.name = name
        self.key = key
        self.timeout = timeout
        self.allow_overrides = allow_overrides
        self.override_kwarg = override_kwarg

    def extra_param_kwargs(self):
        return {}

    def default_key(self, func, args, kwargs):
        if self.allow_overrides and self.override_kwarg in kwargs:
            kwargs = kwargs.copy()
            del kwargs[self.override_kwarg]
        return hashlib.sha1(str(args) + str(kwargs)).hexdigest()

    def default_name(self, func, args, kwargs):
        return hashlib.sha1(str(func)).hexdigest()

    def _convert_redis_param(self, param, args, kwargs):
        if callable(param):
            return param(args=args, kwargs=kwargs)
        return param.format(
            args=args,
            kwargs=kwargs,
            c=c
        )

    def get_keyname(self, func, args=None, kwargs=None):
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        params_kwargs = self.extra_param_kwargs()
        params_kwargs.update(kwargs)
        if self.name:
            name = self._convert_redis_param(self.name, args, params_kwargs)
        else:
            name = self.default_name(func, args, kwargs)
        if self.key:
            key = self._convert_redis_param(self.key, args, params_kwargs)
        else:
            key = self.default_key(func, args, kwargs)
        return name, key

    def get_cached(self, name, key):  # pragma no cover
        raise NotImplementedError('get_cached')

    def set_cached(self, name, key, value):  # pragma no cover
        raise NotImplementedError('set_cached')

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            if not g.cache:
                return func(*args, **kwargs)
            name, key = self.get_keyname(func, args=args, kwargs=kwargs)
            if self.allow_overrides and kwargs.pop(self.override_kwarg, None):
                value = None
            else:
                value = self.get_cached(name, key)
            if not value:
                value = func(*args, **kwargs)
                self.set_cached(name, key, value)
            return value

        return wrapper


class cache_str(BaseCacheDecorator):

    def get_cached(self, name, key):
        return g.cache.hget(name, key)

    def set_cached(self, name, key, value):
        return g.cache.hset(name, key, value, self.timeout)


class cache_literal(cache_str):
    def get_cached(self, name, key):
        result = super(cache_literal, self).get_cached(name, key)
        if result:
            result = literal(result)
        return result


class cache_json(BaseCacheDecorator):

    def get_cached(self, name, key):
        return g.cache.hget_json(name, key)

    def set_cached(self, name, key, value):
        return g.cache.hset_json(name, key, value, self.timeout)


class BaseCacheController(BaseCacheDecorator):
    """
    Base class for caching the result of a controller method

    :param use_query bool whether or not to use the query string

    """
    def __init__(self, append_query=True, **kw):
        self.use_query = append_query
        super(BaseCacheController, self).__init__(**kw)

    def extra_key_kwargs(self):
        return {'path': request.path_info}

    def default_name(self, func, args, kwargs):
        return request.path_info

    def get_keyname(self, func, args=[], kwargs={}):
        kwargs = kwargs.copy()
        kwargs.update(self.extra_key_kwargs())
        name, key = super(BaseCacheController, self).get_keyname(
            func, args, kwargs)
        if self.use_query:
            name += '-' + request.query_string
        return name, key


class cache_method(BaseCacheController, cache_json):
    """
    Cache the result of a controller method, pre-render.

    The result must be jsonifiable

    """
    def default_key(self, func, args, kwargs):
        return 'prerendered'

    def __call__(self, func):
        wrapper = cache_json.__call__(self, func)
        return controller_decorator(wrapper, func)


class cache_rendered(BaseCacheController):
    """Cache the result of a controller method post-render"""

    def default_key(self, func, args, kwargs):
        """Key is not used here"""
        pass

    def __call__(self, func):
        self._func = func
        deco = Decoration.get_decoration(func)
        deco.register_hook('after_render', self.after_render)
        return controller_decorator(self._wrapper, func)

    def _wrapper(self, *args, **kwargs):
        if not g.cache:
            c._cache_response = False
            return self._func(*args, **kwargs)

        name, key = self.get_keyname(self._func, args=args, kwargs=kwargs)
        cached = g.cache.hgetall(name)
        if cached:
            LOG.info('found cache val for %s: %s', name, cached)
            c._cache_response = False
            override_template(self._wrapper, '')
            val = literal(cached['response'])
            if cached.get('content_type'):
                response.content_type = cached['content_type']
        else:
            LOG.info('no cache val for %s', name)
            c._cache_response = name
            val = self._func(*args, **kwargs)
        return val

    def after_render(self, response):
        if c._cache_response:
            name = c._cache_response
            val = {
                'response': response['response'],
                'content_type': response.get('content_type', '')
            }
            g.cache.hmset(name, val, self.timeout)
            LOG.info('setting cache val for %s to %s', name, response)
