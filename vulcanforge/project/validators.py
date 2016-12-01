import cgi

from formencode import Invalid
from formencode import validators as fev
from pylons import tmpl_context as c

from vulcanforge.common.validators import MountPointValidator
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.common.helpers import really_unicode, strip_str
from vulcanforge.project.model import Project


class ProjectNameValidator(fev.UnicodeString):
    not_empty = True
    max = 40
    messages = dict(
        fev.UnicodeString._messages,
        name_taken='That name is already taken!',
        invalid_character='%(character)s is not a valid character'
    )
    invalid_characters = '"\'<>{}'

    def get_neighborhood_id(self):
        if hasattr(c, 'neighborhood'):
            return c.neighborhood._id
        return c.project.neighborhood_id

    def to_python(self, value, state=None):
        value = super(ProjectNameValidator, self).to_python(value, state=state)

        for character in self.invalid_characters:
            if character in value:
                msg = self.message(
                    'invalid_character', state, character=cgi.escape(character)
                )
                raise Invalid(msg, value, state)

        stripped = strip_str(value)

        nbhd_id = self.get_neighborhood_id()
        query = {
            'stripped_name': stripped,
            'neighborhood_id': nbhd_id
        }
        if hasattr(c, 'project') and c.project:
            query['_id'] = {'$ne': c.project._id}  # can be same as current
        cur = Project.query.find(query)
        if cur.count():
            raise Invalid(self.message('name_taken', state), value, state)

        return value


class ShortnameValidator(fev.Regex):
    not_empty = True
    regex = r'^[A-z][-A-z0-9]{2,}$'
    strip = True
    messages = dict(
        fev.Regex._messages,
        invalid='Must be three or more letters, numbers, or dashes, starting with a letter.',
        bad='Invalid value. Please choose another.'
    )

    BLACKLISTED = [
        'home',
        'admin',
        'add_project',
        'register',
        'Project',
        'User'
    ]

    def validate_name(self, value, state=None):
        """Validates the value"""
        value = super(ShortnameValidator, self).to_python(value, state)
        # make sure the name isn't blacklisted
        if value in self.BLACKLISTED:
            msg = self.message('bad', state)
            raise fev.Invalid(msg, value, state)

        return value

    def to_python(self, value, state=None):
        value = self.validate_name(value, state)
        value = really_unicode(value or '').encode('utf-8').lower()

        # no neighborhoods with this shortname
        if Neighborhood.by_prefix(value):
            msg = self.message('bad', state)
            raise fev.Invalid(msg, value, state)

        return value


class AvailableShortnameValidator(ShortnameValidator):
    """Ensures the value is not the shortname of another project."""
    messages = dict(
        ShortnameValidator._messages,
        taken='That url is already taken, please choose another.'
    )

    def to_python(self, value, state=None):
        value = super(
            AvailableShortnameValidator, self).to_python(value, state)
        # make sure the name isn't taken
        if Project.query.get(shortname=value):
            raise fev.Invalid(self.message('taken', state), value, state)
        return value


class ExistingShortnameValidator(ShortnameValidator):
    """Ensures the value is the shortname of the given project, and returns
    the project.

    """
    messages = dict(
        ShortnameValidator._messages,
        notfound='A project with this name was not found'
    )

    def to_python(self, value, state=None):
        value = super(ExistingShortnameValidator, self).to_python(value, state)
        if value:
            project = Project.query.get(shortname=value)
            if not project:
                raise fev.Invalid(self.message('notfound', state), value, state)
            return project


MOUNTPOINT_VALIDATOR = MountPointValidator()
