import os
import re
from contextlib import contextmanager
from hashlib import sha1

from bson import ObjectId
import tg

from .filesystem import temporary_file, temporary_dir
from .http import get_client_ip, set_cache_headers, set_download_headers

re_path_portion = re.compile(r'^[a-z][-_a-z0-9]{2,}$')


class ConfigProxy(object):
    """
    Wrapper for loading config values at module-scope so we don't
    have problems when a module is imported before tg.config is initialized

    """

    def __init__(self, **kw):
        self._kw = kw

    def __getattr__(self, k):
        return tg.config[self._kw[k]]


@contextmanager
def push_config(obj, **kw):
    saved_attrs = {}
    new_attrs = []
    for k, v in kw.iteritems():
        try:
            saved_attrs[k] = getattr(obj, k)
        except AttributeError:
            new_attrs.append(k)
        setattr(obj, k, v)
    try:
        yield obj
    finally:
        for k, v in saved_attrs.iteritems():
            setattr(obj, k, v)
        for k in new_attrs:
            delattr(obj, k)


def nonce(length=4):
    return sha1(ObjectId().binary + os.urandom(10)).hexdigest()[:length]


def cryptographic_nonce(length=40):
    hex_format = '%.2x' * length
    return hex_format % tuple(map(ord, os.urandom(length)))


def title_sort(input, case_sensitive=False):
    """
    Generate a sort friendly version of the given string.

    @param input: string to calculate sortable string from
    @type  input: str, unicode
    @param case_sensitive: should this be sorted case sensitively
    @type  case_sensitive: bool
    @return: sort friendly version of input
    @rtype : str, unicode
    """
    # make a copy
    output = type(input)(input)
    # make case insensitive
    if not case_sensitive:
        output = output.lower()
        # convert prefixes. i.e. - "The Title" to "Title, The"
    for prefix in ['the ']:
        if output.lower().startswith(prefix):
            output = output[len(prefix):].lstrip()\
                     + ', ' + output[:len(prefix)].rstrip()
    return output


def alpha_cmp_factory(*attrs):
    """
    Generate a case insensitive compare function for the given attribute.

    @param attrs: the attributes to sort by if not None with descending
        preference. If none of the attributes are found an empty string will be
        used.
    @type  attrs: list of str, None

    @return: cmp result
    @rtype : int
    """
    def _cmp(*args):
        def get_sort_attr(x):
            value = None
            for attr in attrs:
                value = getattr(x, attr, None)
                if value is not None:
                    break
            value = value or ''
            return value.lower()
        return cmp(*[get_sort_attr(arg) for arg in args])
    return _cmp
