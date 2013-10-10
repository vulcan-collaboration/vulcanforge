from decimal import Decimal

from ming.odm.odmsession import ODMCursor
try:
    from simplejson.encoder import (
        encode_basestring_ascii,
        encode_basestring,
        FLOAT_REPR,
        PosInf,
        c_make_encoder,
        _make_iterencode,
    )
except ImportError:
    from json.encoder import (
        encode_basestring_ascii,
        encode_basestring,
        FLOAT_REPR,
        INFINITY as PosInf,
        c_make_encoder,
        _make_iterencode,
    )

from markupsafe import Markup
from tg.jsonify import GenericJSON

from vulcanforge.common.util.json_util import JSONSafe


class SanitizeEncode(GenericJSON):
    """Taken from simplejson.encode.JSONEncoderForHTML"""

    def encode(self, o, sanitize=None):
        # Override JSONEncoder.encode because it has hacks for
        # performance that make things more complicated.
        if sanitize is None:
            sanitize = not isinstance(o, JSONSafe)
        chunks = self.iterencode(o, True, sanitize)
        if self.ensure_ascii:
            return ''.join(chunks)
        else:
            return u''.join(chunks)

    def _sanitize_encode(self, encoder, sanitize=True):
        def sanitize_encoder(o):
            if isinstance(o, Markup):
                try:
                    o = str(o)
                except UnicodeEncodeError:
                    o = unicode(o)
            elif sanitize:
                o = o.replace('&', '\\u0026')\
                     .replace('<', '\\u003c')\
                     .replace('>', '\\u003e')
            return encoder(o)
        return sanitize_encoder

    def iterencode(self, o, _one_shot=False, sanitize=True):
        if self.check_circular:
            markers = {}
        else:
            markers = None
        if self.ensure_ascii:
            _encoder = encode_basestring_ascii
        else:
            _encoder = encode_basestring
        if self.encoding != 'utf-8':
            def _encoder(o, _orig_encoder=_encoder, _encoding=self.encoding):
                if isinstance(o, str):
                    o = o.decode(_encoding)
                return _orig_encoder(o)

        def floatstr(o, allow_nan=self.allow_nan, ignore_nan=self.ignore_nan,
                     _repr=FLOAT_REPR, _inf=PosInf, _neginf=-PosInf):
            # Check for specials. Note that this type of test is processor
            # and/or platform-specific, so do tests which don't depend on
            # the internals.

            if o != o:
                text = 'NaN'
            elif o == _inf:
                text = 'Infinity'
            elif o == _neginf:
                text = '-Infinity'
            else:
                return _repr(o)

            if ignore_nan:
                text = 'null'
            elif not allow_nan:
                raise ValueError(
                    "Out of range float values are not JSON compliant: " +
                    repr(o))

            return text

        key_memo = {}
        _encoder = self._sanitize_encode(_encoder, sanitize)

        if (_one_shot and c_make_encoder is not None
                and self.indent is None):
            _iterencode = c_make_encoder(
                markers, self.default, _encoder,
                self.indent, self.key_separator, self.item_separator,
                self.sort_keys, self.skipkeys, self.allow_nan, key_memo,
                self.use_decimal, self.namedtuple_as_object,
                self.tuple_as_array, self.bigint_as_string, self.item_sort_key,
                self.encoding, self.for_json, self.ignore_nan,
                Decimal)
        else:
            _iterencode = _make_iterencode(
                markers, self.default, _encoder,
                self.indent, floatstr, self.key_separator, self.item_separator,
                self.sort_keys, self.skipkeys, _one_shot, self.use_decimal,
                self.namedtuple_as_object, self.tuple_as_array,
                self.bigint_as_string, self.item_sort_key,
                self.encoding, self.for_json,
                Decimal=Decimal)
        try:
            return _iterencode(o, 0)
        finally:
            key_memo.clear()

    def default(self, obj):
        if isinstance(obj, ODMCursor):
            return obj.all()
        return super(SanitizeEncode, self).default(obj)


class JSONRenderer(object):

    def __init__(self, **kw):
        self.encoder = SanitizeEncode(**kw)

    def encode(self, obj, sanitize=None):
        if isinstance(obj, basestring):
            return self.encoder.encode(obj, sanitize=sanitize)
        try:
            value = obj['test']
        except TypeError:
            if not hasattr(obj, '__json__') and not isinstance(obj, ODMCursor):
                raise TypeError('Your Encoded object must be dict-like.')
        except:
            pass
        return self.encoder.encode(obj, sanitize=sanitize)

    def render_json(self, template, template_vars, sanitize=None, **kw):
        """Return a JSON string representation of a Python object."""
        return self.encode(template_vars, sanitize=sanitize)
