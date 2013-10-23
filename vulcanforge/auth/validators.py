import re

from formencode import Invalid
from formencode import validators as fev
import tg

from vulcanforge.common.helpers import really_unicode
from vulcanforge.common.util import re_path_portion
from vulcanforge.common.validators import EmailValidator
from vulcanforge.auth.model import User


class UsernameFormatValidator(fev.UnicodeString):
    min = 3
    max = 32

    def to_python(self, value, state=None):
        def invalid(msg):
            return Invalid(msg, value, state)

        value = super(UsernameFormatValidator, self).to_python(value, state)
        if value:
            if not value == value.lower():
                raise invalid("Usernames must be all lowercase!")
            if not re.match(r'^[a-z]', value):
                raise invalid("Usernames must begin with a letter!")
            if value == 'user':
                raise invalid("Invalid username")
            if not re.match(re_path_portion, value):
                raise invalid("Usernames may only contain letters, numbers, "
                              "and dashes (-)!")
        return value


class UsernameValidator(UsernameFormatValidator):
    def to_python(self, value, state=None):
        value = super(UsernameValidator, self).to_python(value, state)
        user = User.by_username(value)
        if user:
            raise Invalid("Username already taken!", value, state)
        return value


class UserIdentifierValidator(fev.UnicodeString):
    """
    Takes a field to uniquely identify a user. Currently Email or Username.
    Returns formatted field, user, id_type

    """
    email_validator = EmailValidator()
    username_validator = UsernameFormatValidator()
    strip = True

    def to_python(self, value, state=None):
        try:
            value = self.email_validator.to_python(value, state)
        except Invalid:
            value = self.username_validator.to_python(value, state)
            user = User.by_username(value)
            if not user:
                raise Invalid("User not found", value, state)
            id_type = 'username'
        else:
            id_type = 'email'
            user = User.by_email_address(value)
        return value, user, id_type


class UsernameListValidator(fev.UnicodeString):

    def to_python(self, value, state=None):
        value = super(UsernameListValidator, self).to_python(value, state)

        def invalid(msg):
            return Invalid(msg, value, state)

        users = []
        usernames = value.split(',')
        for username in usernames:
            username = username.strip()
            if username == '':
                continue
            user = User.by_username(username)
            if user is None:
                raise invalid("'{}' could not be found".format(username))
            users.append(user)
        return users


class PasswordValidator(fev.UnicodeString):
    min = int(tg.config.get('auth.pw.min_length', 10))
    max = int(tg.config.get('auth.pw.max_length', 512))
    messages = {
        'tooShort': "Password should be at least {} characters "
                    "long!".format(min),
        'tooLong': "Password should be no longer than {} characters".format(
            max),
        'missingLower': "Password must contain at least one lowercase "
                        "letter",
        'missingUpper': "Password must contain at least one uppercase "
                        "letter",
        'missingNumber': "Password must contain at least one number",
        'missingSpecial': "Password must contain at least one special "
                          "character",
        }

    def to_python(self, value, state=None):
        def invalid(msg):
            return Invalid(self.message(msg, state), value, state)
        value = really_unicode(value or '').encode('utf-8')
        value = super(PasswordValidator, self).to_python(value, state)
        if not re.match(r'(?=.*[a-z])', value):
            raise invalid('missingLower')
        if not re.match(r'(?=.*[A-Z])', value):
            raise invalid('missingUpper')
        if not re.match(r'(?=.*[\d])', value):
            raise invalid('missingNumber')
        if not re.match(r'(?=.*[\W])', value):
            raise invalid('missingSpecial')
        return value

