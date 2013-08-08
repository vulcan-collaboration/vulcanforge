import cgi
from pylons import tmpl_context as c
import re
import logging
import json
from datetime import datetime

from dateutil.parser import parse
from bson import ObjectId
from bson.errors import InvalidId
from formencode import Invalid, ForEach, validators as fev, Schema
from formencode.api import NoDefault
from tg import request

from vulcanforge.common import helpers as h

LOG = logging.getLogger(__name__)
EMAIL_RE = re.compile(r'(?i)^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$')


class DatetimeValidator(fev.FancyValidator):
    fmt = None
    strip = True

    __unpackargs__ = ('fmt', )

    messages = {
        'invalid': 'This does not appear to be a valid date'
    }

    def _to_python(self, value, state):
        try:
            value = datetime.strptime(value, self.fmt)
        except ValueError:
            LOG.debug('Invalid datetime %s', value)
            raise fev.Invalid(self.message('invalid', state), value, state)
        return value


class DateTimeConverter(fev.FancyValidator):
    """Duplicate functionality to above, let's decide which is cooler"""

    def _to_python(self, value, state):
        try:
            return parse(value)
        except ValueError:
            if self.if_invalid != NoDefault:
                return self.if_invalid
            else:
                raise

    def _from_python(self, value, state):
        return value.isoformat()


class CommaSeparatedEach(ForEach):

    def _convert_to_list(self, value):
        if isinstance(value, basestring):
            return value.split(',')
        return super(CommaSeparatedEach, self)._convert_to_list(value)


class JSONValidator(fev.String):

    messages = {
        'invalid': 'Invalid JSON'
    }

    def _to_python(self, value, state):
        value = super(JSONValidator, self)._to_python(value, state)
        if value:
            try:
                value = json.loads(value)
            except ValueError:
                raise fev.Invalid(self.message('invalid', state), value, state)
        return value


class JSONSchema(Schema):
    """
    Take the request body, parse it as json, and place that in the params
    for further validation

    """
    # these two fields make it work like a normal tg validator
    ignore_key_missing = True
    allow_extra_fields = True

    messages = {
        'invalid': 'Invalid JSON'
    }

    def is_empty(self, value):
        return False

    def validate_other(self, params, state):
        if not request.content_type == 'application/json':
            LOG.debug('Invalid content type')
            raise fev.Invalid(self.message('invalid', state), params, state)

    def _to_python(self, value_dict, state):
        try:
            payload = json.loads(request.body)
        except ValueError:
            LOG.debug('Error parsing JSON: %s with params', request.body)
            raise fev.Invalid(
                self.message('invalid', state), value_dict, state)
        value_dict.update(Schema._to_python(self, payload, state))
        return value_dict


class NullValidator(fev.Validator):

    def to_python(self, value, state=None):
        return value

    def from_python(self, value, state=None):
        return value

    def validate(self, value, state):
        return value


class MaxBytesValidator(fev.FancyValidator):
    max = 255

    def _to_python(self, value, state):
        value = h.really_unicode(value or '').encode('utf-8')
        if len(value) > self.max:
            raise Invalid("Please enter a value less than %s bytes "
                             "long!" % self.max, value, state)
        return value

    def from_python(self, value, state=None):
        return h.really_unicode(value or '')


class EmailValidator(fev.UnicodeString):

    def to_python(self, value, state=None):
        value = h.really_unicode(value or '').encode('utf-8')
        if not value or not re.match(EMAIL_RE, value):
            raise Invalid("Please enter a valid email address!",
                value, state)
        return value


class ObjectIdValidator(fev.UnicodeString):
    not_empty = True
    mapped_class = None

    def __init__(self, **kwargs):
        self.mapped_class = kwargs.pop('mapped_class', None)
        super(ObjectIdValidator, self).__init__(**kwargs)

    def to_python(self, value, state=None):
        value = super(ObjectIdValidator, self).to_python(value, state=state)

        def invalid(msg):
            return Invalid(msg, value, state)

        if value:
            try:
                value = ObjectId(value)
            except InvalidId:
                raise invalid("'{}' is not a valid id".format(value))
            if self.mapped_class is not None:
                instance = self.mapped_class.query.get(_id=value)
                if instance is None:
                    raise invalid(
                        "no instance found with the id '{}'".format(value))
                return instance
        return value


class MingValidator(fev.FancyValidator):

    def __init__(self, cls, **kw):
        self.cls = cls
        super(MingValidator, self).__init__(**kw)

    def _to_python(self, value, state):
        result = self.cls.query.get(_id=value)
        if result is None:
            try:
                result = self.cls.query.get(_id=ObjectId(value))
            except Exception:
                pass
        return result

    def _from_python(self, value, state):
        return value._id


class MountPointValidator(fev.Regex):
    not_empty = True
    regex = r'^[a-z][-a-z0-9]{2,}$'
    messages = dict(
        fev.Regex._messages,
        invalid='Please use at least 3 lowercase letters and numbers '
                'beginning with a letter',
        bad='Invalid value. Please choose another.',
        taken='That url is already taken, please choose another.'
    )

    def validate_name(self, value, state=None):
        return super(MountPointValidator, self).to_python(value, state)

    def to_python(self, value, state=None):
        value = self.validate_name(value, state)

        if c.project.app_instance(value) is not None:
            raise fev.Invalid(self.message('taken', state), value, state)
        return value


class HTMLEscapeValidator(fev.String):
    def _to_python(self, value, state):
        value = super(HTMLEscapeValidator, self)._to_python(value, state)
        return cgi.escape(value)


class HexValidator(fev.Regex):
    regex = r'^[0-9A-F]+$'
    regexOps = ('I',)

