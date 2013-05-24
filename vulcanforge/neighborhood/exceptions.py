
from webob import exc

from vulcanforge.common.exceptions import ForgeError


class RegistrationError(exc.HTTPForbidden):
    """User may not register"""


class NoSuchNeighborhoodError(ForgeError):
    pass
