# -*- coding: utf-8 -*-
import os
import difflib
import urllib
import re
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta

import chardet
from webhelpers import date, html
from webhelpers.text import truncate
from pylons import tmpl_context as c, response, request
import tg
import genshi.template


def monkeypatch(*objs):
    def patchem(func):
        for obj in objs:
            setattr(obj, func.__name__, func)
    return patchem


def urlquote(url):
    try:
        return urllib.quote(str(url))
    except UnicodeEncodeError:
        return urllib.quote(url.encode('utf-8'))


def urlquoteplus(url):
    try:
        return urllib.quote_plus(str(url))
    except UnicodeEncodeError:
        return urllib.quote_plus(url.encode('utf-8'))


def urlunquote(url):
    return really_unicode(urllib.unquote(url))


def split_subdomain(ip):
    return '.'.join(ip.split('.')[-2:]).split(':')[0]


def really_unicode(s):
    if s is None:
        return u''
    # try naive conversion to unicode
    try:
        return unicode(s)
    except UnicodeDecodeError:
        pass
    # Try to guess the encoding
    encodings = [
        lambda: 'utf-8',
        lambda: chardet.detect(s[:1024])['encoding'],
        lambda: chardet.detect(s)['encoding'],
        lambda: 'latin-1',
        ]
    for enc in encodings:
        encoding_type = enc()
        if encoding_type:
            try:
                return unicode(s, encoding_type)
            except UnicodeDecodeError:
                pass
    # Return the repr of the str -- should always be safe
    return unicode(repr(str(s)))[1:-1]


def pretty_print_file_size(size_in_bytes):
    size_str = ''
    if size_in_bytes / 1024 / 1024 > 0:
        size_str = str(size_in_bytes / 1024 / 1024) + ' MB'
    elif size_in_bytes / 1024 > 0:
        size_str = str(size_in_bytes / 1024) + ' KB'
    elif size_in_bytes >= 0:
        size_str = str(size_in_bytes) + ' B'

    return size_str


def get_neighborhoods_by_ids(ids):
    from vulcanforge.neighborhood.model import Neighborhood
    return Neighborhood.query.find({
        '_id': {'$in': list(ids)}
    })


def get_projects_by_ids(ids):
    from vulcanforge.project.model import Project
    return Project.query.find({
        '_id': {'$in': list(ids)}
    })


def get_users_by_ids(ids):
    from vulcanforge.auth.model import User
    return User.query.find({
        '_id': {'$in': list(ids)}
    })


def get_roles_by_ids(ids):
    from vulcanforge.project.model import ProjectRole
    return ProjectRole.query.find({
        '_id': {'$in': list(ids)}
    })


def sharded_path(name, num_parts=2):
    parts = [name[:i + 1] for i in range(num_parts)]
    return '/'.join(parts)


def encode_keys(d):
    """
    Encodes the unicode keys of d, making the result
    a valid kwargs argument

    """
    return dict((k.encode('utf-8'), v) for k, v in d.iteritems())


def ago(start_time, round=True, cutoff=True):
    """
    Return time since starting time as a rounded, human readable string.
    E.g., "3 hours ago"
    """

    if start_time is None:
        return 'unknown'
    granularities = ['century', 'decade', 'year', 'month', 'day', 'hour',
                     'minute']
    end_time = datetime.utcnow()
    if cutoff and (end_time - start_time > timedelta(days=7)):
        return start_time.strftime('%Y-%m-%d')

    while True:
        granularity = granularities.pop()
        ago = date.distance_of_time_in_words(
            start_time, end_time, granularity, round=round)
        rounded_to_one_granularity = 'and' not in ago
        if rounded_to_one_granularity:
            break
    return ago + ' ago'


def ago_ts(timestamp):
    return ago(datetime.utcfromtimestamp(timestamp))


def absurl(url):
    if url is None:
        return None
    if '://' in url:
        return url
    return request.scheme + '://' + request.host + url


def diff_text(t1, t2, differ=None):
    t1_lines = t1.replace('\r', '').split('\n')
    t2_lines = t2.replace('\r', '').split('\n')
    t1_words = []
    for line in t1_lines:
        for word in line.split(' '):
            t1_words.append(word)
            t1_words.append(' ')
        t1_words.append('\n')
    t2_words = []
    for line in t2_lines:
        for word in line.split(' '):
            t2_words.append(word)
            t2_words.append(' ')
        t2_words.append('\n')
    if differ is None:
        differ = difflib.SequenceMatcher(None, t1_words, t2_words)
    result = []
    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag in ('delete', 'replace'):
            result += ['<del>'] + t1_words[i1:i2] + ['</del>']
        if tag in ('insert', 'replace'):
            result += ['<ins>'] + t2_words[j1:j2] + ['</ins>']
        if tag == 'equal':
            result += t1_words[i1:i2]
    return ' '.join(result).replace('\n', '<br/>\n')


class ProxiedAttrMeta(type):
    def __init__(cls, name, bases, dct):
        for v in dct.itervalues():
            if isinstance(v, attrproxy):
                v.cls = cls


class attrproxy(object):
    cls = None

    def __init__(self, *attrs):
        self.attrs = attrs

    def __repr__(self):
        return '<attrproxy on %s for %s>' % (
            self.cls, self.attrs)

    def __get__(self, obj, klass=None):
        if obj is None:
            obj = klass
        for a in self.attrs:
            obj = getattr(obj, a)
        return proxy(obj)

    def __getattr__(self, name):
        if self.cls is None:
            return promised_attrproxy(lambda: self.cls, name)
        return getattr(attrproxy(self.cls, *self.attrs), name)


class promised_attrproxy(attrproxy):
    def __init__(self, promise, *attrs):
        super(promised_attrproxy, self).__init__(*attrs)
        self._promise = promise

    def __repr__(self):
        return '<promised_attrproxy for %s>' % (self.attrs,)

    def __getattr__(self, name):
        cls = self._promise()
        return getattr(cls, name)


class proxy(object):
    def __init__(self, obj):
        self._obj = obj

    def __getattr__(self, name):
        return getattr(self._obj, name)

    def __call__(self, *args, **kwargs):
        return self._obj(*args, **kwargs)


def render_genshi_plaintext(template_name, **template_vars):
    assert os.path.exists(template_name)
    fd = open(template_name)
    try:
        tpl_text = fd.read()
    finally:
        fd.close()
    filepath = os.path.dirname(template_name)
    tt = genshi.template.NewTextTemplate(
        tpl_text, filepath=filepath, filename=template_name)
    stream = tt.generate(**template_vars)
    return stream.render(encoding='utf-8').decode('utf-8')


site_url = None  # cannot set it just yet since tg.config is empty


def full_url(url):
    """Make absolute URL from the relative one.
    """
    global site_url
    if site_url is None:
        # XXX: add a separate tg option instead of re-using openid.realm
        # TODO: sourceforge reference follows
        # TODO: openid
        site_url = tg.config.get('openid.realm',
                                 'https://newforge.sf.geek.net/')
        site_url = site_url.replace('https:', 'http:')
        if not site_url.endswith('/'):
            site_url += '/'
    if url.startswith('/'):
        url = url[1:]
    return site_url + url


@tg.expose(content_type='text/plain')
def json_validation_error(controller, **kwargs):
    result = dict(status='Validation Error',
                errors=c.validation_exception.unpack_errors(),
                value=c.validation_exception.value,
                params=kwargs)
    response.status = 400
    return json.dumps(result, indent=2)


def pop_user_notifications(user=None):
    from vulcanforge.notification.model import Notification, Mailbox
    if user is None:
        user = c.user
    mbox = Mailbox.query.get(user_id=user._id, is_flash=True)
    if mbox:
        notifications = Notification.query.find(dict(
            _id={'$in': mbox.queue}))
        mbox.queue = []
        for n in notifications:
            yield n


def config_with_prefix(d, prefix):
    """
    Return a subdictionary keys with a given prefix,
    with the prefix stripped

    """
    plen = len(prefix)
    return dict(
        (k[plen:], v) for k, v in d.iteritems() if k.startswith(prefix)
    )


@contextmanager
def twophase_transaction(*engines):
    connections = [e.contextual_connect() for e in engines]
    txns = []
    to_rollback = []
    try:
        for c in connections:
            txn = c.begin_twophase()
            txns.append(txn)
            to_rollback.append(txn)
        yield
        to_rollback = []
        for txn in txns:
            txn.prepare()
            to_rollback.append(txn)
        for txn in txns:
            txn.commit()
    except:
        for txn in to_rollback:
            txn.rollback()
        raise


class log_action(object):
    extra_proto = dict(
        action=None,
        action_type=None,
        tool_type=None,
        tool_mount=None,
        project=None,
        neighborhood=None,
        username=None,
        url=None,
        ip_address=None)

    def __init__(self, logger, action):
        self._logger = logger
        self._action = action

    def log(self, level, message, *args, **kwargs):
        kwargs = dict(kwargs)
        extra = kwargs.setdefault('extra', {})
        meta = kwargs.pop('meta', {})
        kwpairs = extra.setdefault('kwpairs', {})
        for k, v in meta.iteritems():
            kwpairs['meta_%s' % k] = v
        extra.update(self._make_extra())
        self._logger.log(level, self._action + ': ' + message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self.log(logging.INFO, message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        self.log(logging.DEBUG, message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self.log(logging.ERROR, message, *args, **kwargs)

    def critical(self, message, *args, **kwargs):
        self.log(logging.CRITICAL, message, *args, **kwargs)

    def exception(self, message, *args, **kwargs):
        self.log(logging.EXCEPTION, message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self.log(logging.EXCEPTION, message, *args, **kwargs)
    warn = warning

    def _make_extra(self):
        result = dict(self.extra_proto, action=self._action)
        try:
            if getattr(c, 'app', None):
                result['tool_type'] = c.app.config.tool_name
                result['tool_mount'] = c.app.config.options['mount_point']
            if getattr(c, 'project', None):
                result['project'] = c.project.shortname
                result['neighborhood'] = c.project.neighborhood.name
            if getattr(c, 'user', None):
                result['username'] = c.user.username
            else:
                result['username'] = '*system'
            try:
                result['url'] = request.url
                ip_address = request.headers.get(
                    'X_FORWARDED_FOR', request.remote_addr
                )
                if ip_address is not None:
                    ip_address = ip_address.split(',')[0].strip()
                    result['ip_address'] = ip_address
                else:
                    result['ip_address'] = '0.0.0.0'
            except TypeError:
                pass
            return result
        except:
            self._logger.warning(
                'Error logging to rtstats, some info may be missing',
                exc_info=True
            )
            return result


def paging_sanitizer(limit, page, total_count, zero_based_pages=True):
    """Return limit, page - both converted to int and constrained to
    valid ranges based on total_count.

    Useful for sanitizing limit and page query params.
    """
    limit = max(int(limit), 1)
    max_page = (total_count / limit) + (1 if total_count % limit else 0)
    max_page = max(0, max_page - (1 if zero_based_pages else 0))
    page = min(max(int(page), (0 if zero_based_pages else 1)), max_page)
    return limit, page


def get_site_protocol():
    """
    Gets the site protocol from the `base_url` configuration entry.

    @return: 'http' or 'https'
    @rtype: str
    """
    return tg.config.get('base_url', 'http').split(':', 1)[0].lower()


def slugify(s, substitute='-'):
    """
    Make an all lowercase version of the given string where all characters
    other than letters and digits are removed and replaced with dashes ("-")
    and any leading or trailing dashes are removed.

    >>> slugify("Hello World!")
    "hello-world"

    @param s: the string to slugify
    @type s: str
    @return: str
    """
    r = re.sub(ur'[^a-zA-Z0-9]+', substitute, s.lower(), flags=re.UNICODE)
    if substitute:
        r = r.strip(substitute)
    return r


def subscribed(user_id=None, project_id=None, app_config_id=None,
        artifact=None, topic=None):
    """
    Get whether the user is subscribed to the given artifact/tool/project

    """
    from vulcanforge.notification.model import Mailbox
    return Mailbox.subscribed(user_id=user_id, project_id=project_id,
                              app_config_id=app_config_id,
                              artifact=artifact, topic=topic)


def subscribed_to_tool(user_id=None, project_id=None, app_config_id=None):
    """
    Get whether the user is subscribed to all artifacts of a tool

    """
    from vulcanforge.notification.model import Mailbox
    return Mailbox.subscribed(user_id=user_id, project_id=project_id,
                              app_config_id=app_config_id,
                              artifact=None, topic=None)


def get_app_subscriptions(user_id=None, project_id=None, app_config_id=None):
    """
    Get mailboxes for input parameters

    """
    from vulcanforge.notification.model import Mailbox
    query_params = {
        'user_id': user_id or c.user._id,
        'project_id': project_id,
        'app_config_id': app_config_id,
    }
    return Mailbox.query.find(query_params).all()


def stringify_datetime(dt):
    return dt.strftime('%Y%m%d%H%M%S%f')


def strip_str(s):
    """
    Strip a name for fuzzy-matching uniqueness queries

    :param s: unicode
    :return: unicode
    """
    r = s.lower().replace(u'the ', u'')
    return slugify(r, substitute=u'')
