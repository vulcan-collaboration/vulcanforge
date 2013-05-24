
from formencode import Invalid
from formencode import validators as fev

from .model import OAuthConsumerToken


class UniqueOAuthApplicationName(fev.UnicodeString):

    def _to_python(self, value, state):
        app = OAuthConsumerToken.query.get(name=value)
        if app is not None:
            raise Invalid('That name is already taken, please choose '
                          'another!', value, state)
        return value