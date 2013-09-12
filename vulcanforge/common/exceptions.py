import json
import logging

from webob.exc import WSGIHTTPException
from webob.response import Response
from webob import exc
from tg import request


LOG = logging.getLogger(__name__)


class ForgeError(Exception):
    pass


class ToolError(ForgeError):
    pass


class NoSuchAppError(ForgeError):
    pass


class CompoundError(ForgeError):
    def __repr__(self):
        return '<%s>\n%s\n</%s>' % (
            self.__class__.__name__,
            '\n'.join(map(repr, self.args)),
            self.__class__.__name__)

    def format_error(self):
        import traceback
        parts = ['<%s>\n' % self.__class__.__name__]
        for tp, val, tb in self.args:
            for line in traceback.format_exception(tp, val, tb):
                parts.append('    ' + line)
        parts.append('</%s>\n' % self.__class__.__name__)
        return ''.join(parts)


class ImproperlyConfigured(ForgeError):
    pass


class ConfigurationError(ForgeError):
    pass


# AJAX Errors


class WSGIAJAXException(WSGIHTTPException):

    def generate_response(self, environ, start_response):
        if request.is_xhr:
            body_dict = dict(code=self.code,
                status=self.status,
                explanation=self.explanation,
                detail=self.detail)
            extra_kw = {}
            resp = Response(json.dumps(body_dict),
                status=self.status,
                headerlist=[],
                content_type='application/json',
                **extra_kw
            )
            environ['pylons.status_code_redirect'] = True
            return resp(environ, start_response)
        else:
            return WSGIHTTPException.generate_response(self,
                environ,
                start_response)


class AJAXBadRequest(WSGIAJAXException, exc.HTTPBadRequest):
    pass


class AJAXUnauthorized(WSGIAJAXException, exc.HTTPUnauthorized):
    pass


class AJAXForbidden(WSGIAJAXException, exc.HTTPForbidden):
    pass


class AJAXNotFound(WSGIAJAXException, exc.HTTPNotFound):
    pass


class AJAXMethodNotAllowed(WSGIAJAXException, exc.HTTPMethodNotAllowed):
    pass


class AJAXNotAcceptable(WSGIAJAXException, exc.HTTPNotAcceptable):
    pass


class AJAXConflict(WSGIAJAXException, exc.HTTPConflict):
    pass


class AJAXGone(WSGIAJAXException, exc.HTTPGone):
    pass


class AJAXUnsupportedMediaType(WSGIAJAXException, exc.HTTPUnsupportedMediaType):
    pass


class AJAXLocked(WSGIAJAXException, exc.HTTPLocked):
    pass


