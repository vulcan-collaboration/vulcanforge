# -*- coding: utf-8 -*-
"""WSGI middleware initialization for a forge application."""

from paste.deploy.converters import asbool, asint
from paste.registry import RegistryManager
from beaker.middleware import SessionMiddleware
from routes.middleware import RoutesMiddleware
from paste.gzipper import middleware as GzipMiddleware
import pylons
from pylons.middleware import StatusCodeRedirect
from tg import config, error as tg_error, TGApp
import ew

from .custom_middleware import (
    StatsMiddleware,
    VFMiddleware,
    CSRFMiddleware,
    LoginRedirectMiddleware,
    LogErrorMiddleware,
    WidgetMiddleware,
    VFMingMiddleware
)
from .ming_config import ming_replicant_configure
from vulcanforge.auth.middleware import AuthMiddleware
from vulcanforge.config.render.template import patches

pylons.c = pylons.tmpl_context
pylons.g = pylons.app_globals


def make_wsgi_app(base_config, global_conf, app_conf, get_template_vars):

    patches.apply()
    # Configure MongoDB
    ming_replicant_configure(**app_conf)

    # Configure EW variable provider
    ew.render.TemplateEngine.register_variable_provider(get_template_vars)

    # Create base app
    load_environment = base_config.make_load_environment()

    # Configure the Pylons environment
    load_environment(global_conf, app_conf)

    if app_conf.get('temp_dir', None):
        import tempfile
        tempfile.tempdir = app_conf.get('temp_dir')

    app = TGApp()

    return app


def add_forge_middleware(app, base_config, global_conf, app_conf):

    # Setup resource manager, widget context SOP
    app = WidgetMiddleware(app)
    # Required for pylons
    app = RoutesMiddleware(app, config['routes.map'])
    # Required for sessions
    app = SessionMiddleware(app, config)

    # Redirect 401 to the login page
    app = LoginRedirectMiddleware(app)
    # Add instrumentation
    if app_conf.get('stats.sample_rate', '0.25') != '0':
        stats_config = dict(global_conf, **app_conf)
        app = StatsMiddleware(app, stats_config)
        # Clear cookies when the CSRF field isn't posted
    if not asbool(app_conf.get('disable_csrf_protection')):
        csrf_blacklist_regex = app_conf.get('csrf_blacklist_regex') or None
        app = CSRFMiddleware(
            app, '_session_id',
            secure=asbool(app_conf.get('beaker.session.secure', False)),
            blacklist_regex=csrf_blacklist_regex)

    # credentials request-global credentials cache
    app = AuthMiddleware(app)

    # Make sure that the wsgi.scheme is set appropriately when we
    # have the funky HTTP_X_SFINC_SSL  environ var
    # if asbool(app_conf.get('auth.method', 'local') == 'sfx'):
    #    app = set_scheme_middleware(app)
        # Handle static files (by tool)
    # Handle setup and flushing of Ming ORM sessions
    app = VFMingMiddleware(app)

    app = VFMiddleware(app)

    if asbool(config.get('web.compress', False)):
        level = asint(config.get('web.compress.level', 6))
        app = GzipMiddleware(app, compress_level=level)

    # Converts exceptions to HTTP errors, shows traceback in debug mode
    # Redirect some status codes to /error/document
    if asbool(config['debug']):
        app = tg_error.ErrorHandler(
            app,
            global_conf,
            **config['pylons.errorware']
        )
        app = StatusCodeRedirect(app, base_config.handle_status_codes)
    else:
        app = LogErrorMiddleware(
            app, global_conf, **config['pylons.errorware'])
        app = StatusCodeRedirect(app, base_config.handle_status_codes + [500])

    # Set up the registry for stacked object proxies (SOPs).
    #    streaming=true ensures they won't be cleaned up till
    #    the WSGI application's iterator is exhausted
    app = RegistryManager(app, streaming=True)
    return app


def set_scheme_middleware(app):
    def SchemeMiddleware(environ, start_response):
        if asbool(environ.get('HTTP_X_SFINC_SSL', 'false')):
            environ['wsgi.url_scheme'] = 'https'
        return app(environ, start_response)
    return SchemeMiddleware


def get_base_template_vars(context):
    import pylons
    import tg
    from urllib import quote, quote_plus
    context.setdefault('g', pylons.app_globals)
    context.setdefault('c', pylons.tmpl_context)
    context.setdefault('request', pylons.request)
    context.setdefault('response', pylons.response)
    context.setdefault('url', pylons.url)
    context.setdefault('tg', dict(
        config=tg.config,
        flash_obj=tg.flash,
        quote=quote,
        quote_plus=quote_plus,
        url=tg.url))
