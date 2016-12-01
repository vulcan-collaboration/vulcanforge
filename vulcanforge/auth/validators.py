import re

from formencode import Invalid
from formencode import validators as fev
import tg

from vulcanforge.common.helpers import really_unicode
from vulcanforge.common.util import re_path_portion
from vulcanforge.common.util.diff import levenshtein
from vulcanforge.common.validators import EmailValidator
from vulcanforge.auth.model import User

DEFAULT_COMPLEXITY_SPEC = "U1_L1_N1_S1"
COMPLEXITY_ELEMENTS = ('uppercase', 'lowercase', 'number', 'special')
DEFAULT_COMPLEXITY = {x: 1 for x in COMPLEXITY_ELEMENTS}

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
        value = super(UserIdentifierValidator, self).to_python(value, state)
        try:
            value = self.email_validator.to_python(value, state)
        except Invalid:
            value = self.username_validator.to_python(value, state)
            user = User.by_username(value)
            if not user:
                raise Invalid("User {} not found".format(value), value, state)
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


def complexity_helper(spec):
    """Parses a password complexity specification"""
    retval = {}
    retval.update(DEFAULT_COMPLEXITY)
    for elem in COMPLEXITY_ELEMENTS:
        regex = re.compile(elem.capitalize()[0] + "([0-9]*)")
        mo = regex.search(spec)
        if mo:
            count = int(mo.group(1))
            if count:
                retval[elem] = count
    return retval


def get_complexity():
    """returns the configured or default password complexity"""
    spec = tg.config.get('auth.pw.complexity', DEFAULT_COMPLEXITY_SPEC)
    return complexity_helper(spec)


def complexity_messages(counts):
    """Returns a dictionary of diagnostic messages for password complexity"""
    msg_names = dict(uppercase="missingUpper", lowercase="missingLower",
                     number="missingNumber", special="missingSpecial")
    retval = {}
    for elem in counts:
        kind = "letter" if elem in ("uppercase", "lowercase") else "character"
        kind += "s" if counts[elem] > 1 else ""
        template = "Password must contain at least {} {} {}"
        retval[msg_names[elem]] = template.format(counts[elem], elem, kind)
    return retval


class PasswordValidator(fev.UnicodeString):

    def to_python(self, value, state=None):
        def invalid(msg):
            return Invalid(self.message(msg, state), value, state)

        self.min = int(tg.config.get('auth.pw.min_length', 10))
        self.max = int(tg.config.get('auth.pw.max_length', 512))
        self.counts = get_complexity()

        self._messages = {
            'tooShort': "Password must be at least {} characters long!".format(
                self.min),
            'tooLong': "Password must be no longer than {} characters".format(
                self.max)
        }
        self._messages.update(complexity_messages(self.counts))

        value = really_unicode(value or '').encode('utf-8')
        value = super(PasswordValidator, self).to_python(value, state)
        if len(re.findall('[a-z]', value)) < self.counts['lowercase']:
            raise invalid('missingLower')
        if len(re.findall('[A-Z]', value)) < self.counts['uppercase']:
            raise invalid('missingUpper')
        if len(re.findall('[\d]', value)) < self.counts['number']:
            raise invalid('missingNumber')
        if len(re.findall('[\W_]', value)) < self.counts['special']:
            raise invalid('missingSpecial')
        return value


def validate_password(value, current=None):
    min = int(tg.config.get('auth.pw.min_length', 10))
    max = int(tg.config.get('auth.pw.max_length', 512))
    counts = get_complexity()
    messages = {
        'tooSimilar': "Password must not be too similar to current password",
        'tooShort': "Password must be at least {} characters long".format(
            min),
        'tooLong': "Password must be no longer than {} characters".format(
            max)
    }
    messages.update(complexity_messages(counts))

    if len(value) < min:
        return messages['tooShort']
    if len(value) > max:
        return messages['tooLong']
    if len(re.findall('[a-z]', value)) < counts['lowercase']:
        return messages['missingLower']
    if len(re.findall('[A-Z]', value)) < counts['uppercase']:
        return messages['missingUpper']
    if len(re.findall('[\d]', value)) < counts['number']:
        return messages['missingNumber']
    if len(re.findall('[\W_]', value)) < counts['special']:
        return messages['missingSpecial']

    if current:
        min_levenshtein = int(tg.config.get('auth.pw.min_levenshtein', 0))
        if min_levenshtein > 0:
            lev = levenshtein(value, current)
            if lev < min_levenshtein:
                return messages['tooSimilar']
    return 'success'

