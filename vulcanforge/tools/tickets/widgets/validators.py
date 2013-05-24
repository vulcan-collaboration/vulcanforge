import logging

from formencode.api import Invalid
from pylons import tmpl_context as c
from ew.validators import UnicodeString

LOG = logging.getLogger(__name__)


class ProjectUser(UnicodeString):

    messages = dict(
        invalid='Please enter a valid user for this project'
    )

    def validate_python(self, value, state):
        # if blank it's valid
        if value == '':
            return value
        # if we can find the user then it's valid
        try:
            assert c.app.project.user_in_project(value)
        except (AssertionError, AttributeError, NotImplementedError):
            raise Invalid(self.message('invalid', state), value, state)
        # we made it this far must be valid
        return value
