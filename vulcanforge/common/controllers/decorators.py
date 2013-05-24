import re
from datetime import datetime, timedelta
from decorator import decorator

from webob import exc
from formencode.variabledecode import variable_decode
from pylons import app_globals as g
from tg import request, response, redirect
from tg.decorators import before_validate, validate

from vulcanforge.common.util.http import RFC_FORMAT

RE_VARDEC_KEY = re.compile(r'''\A
( # first part
\w+# name...
(-\d+)?# with optional -digits suffix
)
(\. # next part(s)
\w+# name...
(-\d+)?# with optional -digits suffix
)+
\Z''', re.VERBOSE)


class require_post(object):

    def __init__(self, redir=None):
        self.redir = redir

    def __call__(self, func):
        def check_method(remainder, params):
            if request.method != 'POST':
                if self.redir is not None:
                    redirect(self.redir)
                raise exc.HTTPMethodNotAllowed(headers={'Allow': 'POST'})
        before_validate(check_method)(func)
        return func


def vardec(fun):
    def vardec_hook(remainder, params):
        new_params = variable_decode(dict(
            (k, v) for k, v in params.items() if RE_VARDEC_KEY.match(k)
        ))
        params.update(new_params)
    before_validate(vardec_hook)(fun)
    return fun


def controller_decorator(wrapper, controller):
    """Wraps a controller method"""
    result = lambda *args, **kwargs: wrapper(*args[1:], **kwargs)
    if hasattr(controller, 'decoration'):
        result.decoration = controller.decoration
    return decorator(result, controller)


class ControllerPropertyValidator(object):

    def __init__(self, attribute):
        self.attribute = attribute

    def validate(self, controller, params, state):
        form = getattr(controller.__self__.Forms, self.attribute)
        return form.validate(params, state)


class validate_form(validate):
    """
    Similar to validate, but if form is a string it attempts to access
    that attribute in the parent controller in order to facilitate form
    pluggability

    """
    def __init__(self, form, error_handler=None):
        if isinstance(form, basestring):
            form = ControllerPropertyValidator(form)
            self.needs_controller = True
        super(validate_form, self).__init__(
            form=form, error_handler=error_handler)


def require_anonymous(fn):
    def decorated(*args, **kwargs):
        g.security.require_anonymous()
        return fn(*args, **kwargs)
    return decorated


def require_authenticated(fn):
    def decorated(*args, **kwargs):
        g.security.require_authenticated()
        return fn(*args, **kwargs)
    return decorated


class require_site_admin_access(object):

    def __init__(self, redir=None):
        self.redir = redir

    def __call__(self, func):
        p_admin = g.get_site_admin_project()

        def check_method(remainder, params):
            if not g.security.has_access(p_admin, 'admin'):
                if self.redir is not None:
                    redirect(self.redir)
                raise exc.HTTPForbidden()

        before_validate(check_method)(func)
        return func


def add_cache_headers(seconds):
    """
    Add cache headers to a response

    @param seconds: int

    """
    def get_expire_dt():
        expire_dt = datetime.utcnow() + timedelta(seconds=seconds)
        return expire_dt.strftime(RFC_FORMAT)

    return add_headers({
        'Cache-Control': 'public, max-age=%d' % seconds,
        'Expires': get_expire_dt,
        'Pragma': ''
    })


def add_headers(headers):
    """
    Add headers to response
    @param headers: dict

    """
    def wrapper(func, *args, **kwargs):
        for k, v in headers.iteritems():
            if callable(v):
                v = v()
            response.headers[k] = v
        return func(*args, **kwargs)
    return decorator(wrapper)
