import string
import time
import random
import binascii
import hashlib

from webhelpers.html import literal
from formencode import Invalid
import pylons
from tg.decorators import before_validate
from ew import jinja2_ew as ew
from vulcanforge.common.util.http import get_client_ip


class AntiSpam(object):
    """Helper class for bot-protecting forms"""
    honey_field_template = string.Template('''<p class="$honey_class">
    <label for="$fld_id">You seem to have CSS turned off.
        Please don't fill out this field.</label><br>
    <input id="$fld_id" name="$fld_name" type="text"><br></p>''')

    def __init__(self, request=None, num_honey=2):
        self.num_honey = num_honey
        if request is None:
            self.request = pylons.request
            self.timestamp = int(time.time())
            self.spinner = self.make_spinner()
            self.timestamp_text = str(self.timestamp)
            self.spinner_text = self._wrap(self.spinner)
        else:
            self.request = request
            self.timestamp_text = request.params['timestamp']
            self.spinner_text = request.params['spinner']
            self.timestamp = int(self.timestamp_text)
            self.spinner = self._unwrap(self.spinner_text)
        self.spinner_ord = map(ord, self.spinner)
        self.random_padding = [random.randint(0, 255) for x in self.spinner]
        self.honey_class = self.enc(self.spinner_text, css_safe=True)

        # The counter is to ensure that multiple forms in the same page
        # don't end up with the same id.  Instead of doing:
        #
        # honey0, honey1
        # which just relies on 0..num_honey we include a counter
        # which is incremented every time extra_fields is called:
        #
        # honey00, honey 01, honey10, honey11
        self.counter = 0

    @staticmethod
    def _wrap(s):
        """
        Encode a string to make it HTML id-safe (starts with alpha, includes
        only digits, hyphens, underscores, colons, and periods).  Luckily,
        base64 encoding doesn't use hyphens, underscores, colons, nor periods,
        so we'll use these characters to replace its plus, slash, equals, and
        newline.

        """
        tx_tbl = string.maketrans('+/', '-_')
        s = binascii.b2a_base64(s)
        s = s.rstrip('=\n')
        s = s.translate(tx_tbl)
        s = 'X' + s
        return s

    @staticmethod
    def _unwrap(s):
        tx_tbl = string.maketrans('-_', '+/')
        s = s[1:]
        s = str(s).translate(tx_tbl)
        i = len(s) % 4
        if i > 0:
            s += '=' * (4 - i)
        s = binascii.a2b_base64(s + '\n')
        return s

    def enc(self, plain, css_safe=False):
        """
        Stupid fieldname encryption.  Not production-grade, but
        hopefully "good enough" to stop spammers.  Basically just an
        XOR of the spinner with the unobfuscated field name

        """
        # Plain starts with its length, includes the ordinals for its
        #   characters, and is padded with random data
        plain = (
            [len(plain)]
            + map(ord, plain)
            + self.random_padding[:len(self.spinner_ord) - len(plain) - 1]
            )
        enc = ''.join(chr(p ^ s) for p, s in zip(plain, self.spinner_ord))
        enc = self._wrap(enc)
        if css_safe:
            enc = ''.join(ch for ch in enc if ch.isalpha())
        return enc

    def dec(self, enc):
        enc = self._unwrap(enc)
        enc = list(map(ord, enc))
        plain = [e ^ s for e, s in zip(enc, self.spinner_ord)]
        plain = plain[1:1 + plain[0]]
        plain = ''.join(map(chr, plain))
        return plain

    def extra_fields(self):
        yield ew.HiddenField(
            name='timestamp',
            value=self.timestamp_text
        ).display()
        yield ew.HiddenField(name='spinner', value=self.spinner_text).display()
        for fldno in range(self.num_honey):
            fld_name = self.enc('honey%d' % fldno)
            fld_id = self.enc('honey%d%d' % (self.counter, fldno))
            yield literal(self.honey_field_template.substitute(
                honey_class=self.honey_class,
                fld_id=fld_id,
                fld_name=fld_name))
        self.counter += 1

    def make_spinner(self, timestamp=None):
        if timestamp is None:
            timestamp = self.timestamp
        client_ip = get_client_ip(self.request) or '127.0.0.1'
        plain = '%d:%s:%s' % (
            timestamp,
            client_ip,
            pylons.config.get('spinner_secret', 'abcdef'))
        return hashlib.sha1(plain).digest()

    @classmethod
    def validate_request(cls, request=None, now=None):
        if request is None:
            request = pylons.request
        params = dict(request.params)
        params.pop('timestamp', None)
        params.pop('spinner', None)
        obj = cls(request)
        if now is None:
            now = time.time()
        if obj.timestamp > now + 5:
            raise ValueError('Post from the future')
        if now - obj.timestamp > 60 * 60:
            raise ValueError('Post from the 1hr+ past')
        if obj.spinner != obj.make_spinner(obj.timestamp):
            raise ValueError('Bad spinner value')
        for k in params.keys():
            params[obj.dec(k)] = params.pop(k)
        for fldno in range(obj.num_honey):
            value = params.pop('honey%s' % fldno)
            if value:
                raise ValueError('Value in honeypot field: %s' % value)
        return params

    @classmethod
    def validate(cls, error_msg):
        """
        Controller decorator to raise Invalid errors if bot protection is
        engaged

        """

        def antispam_hook(remainder, params):
            """
            Converts various errors in validate_request to a single Invalid
            message

            """
            try:
                params.update(cls.validate_request())
            except (ValueError, TypeError, binascii.Error) as e:
                raise Invalid(error_msg, params, None)
        return before_validate(antispam_hook)
