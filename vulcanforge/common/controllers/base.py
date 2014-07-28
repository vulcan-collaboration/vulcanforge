import os

from webob import exc
from tg import expose
from tg.controllers import TGController, RestController


class _Base(object):

    class Forms(object):
        pass

    class Widgets(object):
        pass


class BaseController(_Base):
    """Simple, lightweight controller. TG routing will use root controller
    routing methods.

    """
    @expose()
    def _lookup(self, name, *remainder):
        """Provide explicit default lookup to avoid dispatching backtracking
        and possible loops."""
        raise exc.HTTPNotFound, name


class BaseTGController(_Base, TGController):
    """Extends TGController, which includes routing."""
    pass


class BaseRestController(_Base, RestController):
    pass


class WsgiDispatchController(BaseTGController):
    """
    Base class for the root controllers in the application.

    """
    class Forms(object):
        pass

    class Widgets(object):
        pass

    def _setup_request(self):
        """Responsible for setting all the values we need to be set on
        pylons.c

        """
        raise NotImplementedError('_setup_request')

    def _cleanup_request(self):
        raise NotImplementedError('_cleanup_request')

    def __call__(self, environ, start_response):
        try:
            self._setup_request()
            response = super(WsgiDispatchController, self).__call__(
                environ, start_response)
            return self.cleanup_iterator(response)
        except exc.HTTPException, err:
            return err(environ, start_response)

    def cleanup_iterator(self, response):
        for chunk in response:
            yield chunk
        self._cleanup_request()
