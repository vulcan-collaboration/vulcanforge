# -*- coding: utf-8 -*-
import os
import re
import logging
import urlparse
import mimetypes
from random import random

import tg
from tg.configuration import config

from weberror import formatter, collector
from weberror.errormiddleware import ErrorMiddleware
import markdown
import ew
from ew.core import widget_context, WidgetContext
from paste import fileapp
from paste.deploy.converters import asbool
from pylons.util import call_wsgi_application
from webob import exc, Request

from scss import Scss

from vulcanforge.common.model.stats import Stats

from vulcanforge.common.util import cryptographic_nonce
from vulcanforge.common.util.log import prefix_lines
from vulcanforge.common.util.timing import timing, StatsRecord


LOG = logging.getLogger(__name__)


class VFMiddleware(object):
    """
    Sets site-wide response headers.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def vf_start_response(status, headers, exc_info=None):
            """
            Assumes X-Frame-Options header is not already set
            """
            headers.append(('X-Frame-Options', 'SAMEORIGIN',))
            return start_response(status, headers, exc_info)
        return self.app(environ, vf_start_response)


class LogContentType(object):
    def __init__(self, app, resource_prefix=None):
        self.app = app
        self.resource_prefix = resource_prefix

    def __call__(self, environ, start_response):
        if environ['PATH_INFO'].startswith(self.resource_prefix):
            def custom_start_response(status, headers, exc_info=None):
                LOG.info('%s: %s' % (environ['PATH_INFO'], headers))
                return start_response(status, headers, exc_info)
            return self.app(environ, custom_start_response)
        return self.app(environ, start_response)


class LogErrorMiddleware(ErrorMiddleware):
    """Use logging configuration for errors"""
    def __init__(self, *args, **kwargs):
        self.prefix = kwargs.pop(
            'prefix', tg.config.get('log_prefix', '>->->') + ' ')
        super(LogErrorMiddleware, self).__init__(*args, **kwargs)

    def exception_handler(self, exc_info, environ):
        exc_data = collector.collect_exception(*exc_info)
        text, head_text = formatter.format_text(
            exc_data, show_hidden_frames=True)
        text = prefix_lines(text, self.prefix)
        environ['wsgi.errors'].write(text + '\n')


class FixCSSContentType(object):
    def __init__(self, app, resource_prefix=None):
        self.app = app
        self.resource_prefix = resource_prefix

    def __call__(self, environ, start_response):
        p = environ['PATH_INFO']
        if p.startswith(self.resource_prefix) and p.endswith('.css'):
            def custom_start_response(status, headers, *args, **kwargs):
                try:
                    i = headers.index(
                        ('Content-Type', 'application/javascript'))
                except ValueError:
                    pass
                else:
                    headers[i] = ('Content-Type', 'text/css')
                return start_response(status, headers, *args, **kwargs)
            environ['CONTENT_TYPE'] = 'text/css'
            return self.app(environ, custom_start_response)
        return self.app(environ, start_response)


class LoginRedirectMiddleware(object):
    """Actually converts a 401 into a 302 so we can do a redirect to a
    different app for login.  (StatusCodeRedirect does a WSGI-only redirect
    which cannot go to a URL not managed by the WSGI stack).

    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        status, headers, app_iter, exc_info = call_wsgi_application(
            self.app, environ, catch_exc_info=True)
        if status[:3] == '401' and not tg.request.is_xhr:
            login_url = tg.config.get('auth.login_url', '/auth/')
            if environ['REQUEST_METHOD'] == 'GET':
                return_to = environ['PATH_INFO']
                if environ.get('QUERY_STRING'):
                    return_to += '?' + environ['QUERY_STRING']
                location = tg.url(login_url, dict(return_to=return_to))
            else:
                # Don't try to re-post; the body has been lost.
                location = tg.url(login_url)
            r = exc.HTTPFound(location=location)
            return r(environ, start_response)
        start_response(status, headers, exc_info)
        return app_iter


class CSRFMiddleware(object):
    """
    On POSTs, looks for a special field name that matches the value of a given
    cookie.  If this field is missing, the cookies are cleared to anonymize the
    request.

    """
    def __init__(self, app, cookie_name, param_name=None,
                 blacklist_regex=None):
        if param_name is None:
            param_name = cookie_name
        self._app = app
        self._param_name = param_name
        self._cookie_name = cookie_name
        if blacklist_regex is not None:
            self._blacklist_regex = re.compile(blacklist_regex)
        else:
            self._blacklist_regex = None

    def __call__(self, environ, start_response):
        # skip for blacklisted urls
        if (
            self._blacklist_regex is not None and
            self._blacklist_regex.match(environ['PATH_INFO']) is not None
        ):
            return self._app(environ, start_response)
        # otherwise continue
        req = Request(environ)
        headers = req.headers
        cookie = req.cookies.get(self._cookie_name, None)
        if cookie is None:
            cookie = cryptographic_nonce()
        if req.method == 'POST':
            try:
                param = req.str_GET.pop(self._param_name, None)
            except KeyError:
                param = None
            if not param:
                try:
                    param = req.str_POST.pop(self._param_name, None)
                except KeyError:
                    param = None
            if not param:
                param = headers.get('VF_SESSION_ID', None)
            if cookie != param:
                LOG.warning('CSRF attempt detected to %s, %r != %r',
                            environ['PATH_INFO'], cookie, param)
                environ.pop('HTTP_COOKIE', None)

        def session_start_response(status, headers, exc_info=None):
            headers.append(
                ('Set-cookie',
                 str('%s=%s; Path=/' % (self._cookie_name, cookie))))
            return start_response(status, headers, exc_info)

        return self._app(environ, session_start_response)


class SSLMiddleware(object):
    """Verify the https/http schema is correct"""

    def __init__(self, app, no_redirect_pattern=None):
        self.app = app
        if no_redirect_pattern:
            self._no_redirect_re = re.compile(no_redirect_pattern)
        else:
            self._no_redirect_re = re.compile('$$$')

    def __call__(self, environ, start_response):
        req = Request(environ)
        if self._no_redirect_re.match(environ['PATH_INFO']):
            return req.get_response(self.app)(environ, start_response)
        resp = None
        try:
            request_uri = req.url
            request_uri.decode('ascii')
        except UnicodeError:
            resp = exc.HTTPNotFound()
        secure = req.environ.get('HTTP_X_SFINC_SSL', 'false') == 'true'
        srv_path = req.url.split('://', 1)[-1]
        # TODO: sourceforge reference follows
        if req.cookies.get('SFUSER'):
            if not secure:
                resp = exc.HTTPFound(location='https://' + srv_path)
        elif secure:
            resp = exc.HTTPFound(location='http://' + srv_path)

        if resp is None:
            resp = req.get_response(self.app)
        return resp(environ, start_response)


class StatsMiddleware(object):

    def __init__(self, app, config):
        self.app = app
        self.config = config
        self.log = logging.getLogger('stats')
        self.active = False
        try:
            self.sample_rate = config.get('stats.sample_rate', 0.25)
            self.debug = asbool(config.get('debug', 'false'))
            self.instrument_pymongo()
            self.instrument_template()
            self.active = True
        except KeyError:
            self.sample_rate = 0

    def instrument_pymongo(self):
        import pymongo.collection
        import ming.odm
        timing('mongo').decorate(pymongo.collection.Collection,
                                 'count find find_one')
        timing('mongo').decorate(
            pymongo.cursor.Cursor,
            'count distinct explain hint limit next rewind skip sort where')
        timing('ming').decorate(ming.odm.odmsession.ODMSession,
                                'flush find get')
        timing('ming').decorate(ming.odm.odmsession.ORMCursor,
                                'next')

    def instrument_template(self):
        import jinja2
        import genshi.template
        timing('template').decorate(genshi.template.Template,
                                    '_prepare _parse generate')
        timing('render').decorate(genshi.Stream,
                                  'render')
        timing('render').decorate(jinja2.Template,
                                  'render')
        timing('markdown').decorate(markdown.Markdown,
                                    'convert')

    def __call__(self, environ, start_response):
        req = Request(environ)
        # TODO: sourceforge reference follows
        s = StatsRecord(req, random() < self.sample_rate)
        req.environ['sf.stats'] = s
        with s.timing('total'):
            resp = req.get_response(self.app, catch_exc_info=self.debug)
            result = resp(environ, start_response)
        if s.active:
            self.log.info('Stats: %r', s)
            Stats.make(s.asdict()).m.insert()
        return result


class WidgetMiddleware(ew.WidgetMiddleware):

    def __init__(self, app, **kwargs):
        mgr = config['pylons.app_globals'].resource_manager
        kwargs['script_name'] = mgr.script_name
        super(WidgetMiddleware, self).__init__(app, **kwargs)
        self.script_name_slim_res = mgr.script_name + '_slim/'

    def __call__(self, environ, start_response):
        registry = environ['paste.registry']
        mgr = config['pylons.app_globals'].resource_manager
        registry.register(
            widget_context,
            WidgetContext(
                scheme=environ['wsgi.url_scheme'],
                resource_manager=mgr))

        if not environ['PATH_INFO'].startswith(self.script_name):
            return self.app(environ, start_response)

        if environ['PATH_INFO'] == self.script_name_slim_js:
            result = self.serve_slim_js(
                mgr, urlparse.parse_qs(
                    environ['QUERY_STRING']).get('href', [''])[0],
                environ, start_response)
        elif environ['PATH_INFO'] == self.script_name_slim_css:
            result = self.serve_slim_css(
                mgr, urlparse.parse_qs(
                    environ['QUERY_STRING']).get('href', [''])[0],
                environ, start_response)
        elif environ['PATH_INFO'].startswith(self.script_name_slim_res):
            environ['CONTENT_ENCODING'] = 'identity'
            result = self.serve_slim_resource(
                mgr, environ['PATH_INFO'].split(self.script_name_slim_res)[1],
                environ, self.remove_encoding_start_response(start_response))
        else:
            environ['CONTENT_ENCODING'] = ''
            result = self.serve_resource(
                mgr,
                environ['PATH_INFO'][len(self.script_name):],
                environ,
                self.remove_encoding_start_response(start_response))

        return result

    def remove_encoding_start_response(self, start_response):
        def custom_start_response(status, headers, *args, **kwargs):
            try:
                i = headers.index(('Content-Encoding', 'gzip'))
            except ValueError:
                pass
            else:
                headers[i] = ('Content-Encoding', 'identity')
            return start_response(status, headers, *args, **kwargs)
        return custom_start_response

    def serve_resource(self, mgr, res_path, environ, start_response):
        fs_path = mgr.get_filename(res_path)
        if fs_path is None:
            LOG.warning('Could not map %s', res_path)
            return exc.HTTPNotFound(res_path)(environ, start_response)
        if res_path.endswith('.scss'):
            scss_compiler = Scss(scss_opts={
                'compress': False,
                'debug_info': False,
                'load_paths': mgr.get_directories()
            })
            scss_data = open(fs_path).read()
            compiled_data = scss_compiler.compile(scss_data)

            app = fileapp.DataApp(
                compiled_data, [('Content-Type', 'text/css')])
        else:
            app = fileapp.FileApp(fs_path, headers=self.extra_headers)
            app.cache_control(public=True, max_age=mgr.cache_max_age)
        try:
            return app(environ, start_response)
        except OSError:
            return exc.HTTPNotFound(res_path)(environ, start_response)

    def serve_slim_js(self, mgr, res_path, environ, start_response):
        try:
            data, mtime = mgr.serve_slim('js', res_path)
        except (IOError, OSError):
            return exc.HTTPNotFound()(environ, start_response)
        app = fileapp.DataApp(data, [
            ('Content-Type', 'text/javascript'),
            ('Content-Encoding', 'gzip'),
            ('Content-Length', len(data))
        ])
        app.cache_control(public=True, max_age=mgr.cache_max_age)
        app.set_content(data, mtime)
        return app(environ, start_response)

    def serve_slim_css(self, mgr, res_path, environ, start_response):
        try:
            data, mtime = mgr.serve_slim('css', res_path)
        except (IOError, OSError):
            return exc.HTTPNotFound()(environ, start_response)
        app = fileapp.DataApp(data, [
            ('Content-Type', 'text/css'),
            ('Content-Encoding', 'gzip'),
            ('Content-Length', len(data))
        ])
        app.cache_control(public=True, max_age=mgr.cache_max_age)
        app.set_content(data, mtime)
        return app(environ, start_response)

    def serve_slim_resource(self, mgr, res_path, environ, start_response):
        try:
            data, mtime = mgr.serve_slim('image', res_path)
        except (IOError, OSError):
            return exc.HTTPNotFound()(environ, start_response)

        content_type, encoding = mimetypes.guess_type(res_path)
        if content_type is None:
            content_type = 'binary/octet-stream'
        app = fileapp.DataApp(data, [('Content-Type', content_type)])
        app.cache_control(public=True, max_age=mgr.cache_max_age)
        app.set_content(data, mtime)
        return app(environ, start_response)
