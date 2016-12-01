import logging

from webob import exc
from pylons import app_globals as g, tmpl_context as c
from tg import expose

from vulcanforge.common.controllers import BaseController

LOG = logging.getLogger(__name__)


class GlobalExchangeRestController(BaseController):
    @expose()
    def _lookup(self, name, *remainder):
        xcng = g.exchange_manager.get_exchange_by_uri(name)
        if xcng and xcng.config.get('rest_controller'):
            c.exchange = xcng
            return xcng.config['rest_controller'], remainder
        raise exc.HTTPNotFound


class ExchangeRestController(BaseController):
    pass