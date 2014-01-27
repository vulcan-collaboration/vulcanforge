import logging

import requests
from beaker.session import SessionObject
from paste.deploy.converters import asbool
from pylons import app_globals as g
from tg import config

from vulcanforge.auth.model import User

LOG = logging.getLogger(__name__)


class ForgeRequester(object):
    """Makes requests to current active deployment with optional auth

    Used for testing.

    """
    def __init__(self):
        self._cookies = {}
        self._session_id = 'forge_internal_requester'

    def expand_uri(self, uri):
        return '/'.join((g.base_url, uri.lstrip('/')))

    def make_auth_cookies(self, user):
        sesh = SessionObject(
            {},
            key=config.get('beaker.session.key'),
            timeout=int(config.get('beaker.session.timeout', 0)),
            encrypt_key=config['beaker.session.encrypt_key'],
            validate_key=config['beaker.session.validate_key'],
            secure=asbool(config.get('beaker.session.secure', 'f')),
            secret=config.get('beaker.session.secret'),
            type=config.get('beaker.session.type', 'cookie')
        )
        sesh['userid'] = user._id
        sesh.save()
        sesh.persist()
        cookie_str = sesh.__dict__['_headers']['cookie_out']
        cookie_val = cookie_str.split(';')[0].split('=', 1)[1]
        cookies = {
            sesh.key: cookie_val,
            '_session_id': self._session_id
        }
        return cookies

    def set_user(self, user):
        self.user = user
        self._cookies.update(self.make_auth_cookies(user))

    def _http_request(self, verb, url, as_user=None, **params):
        params.setdefault('timeout', 4)
        cookies = self._cookies.copy()
        cookies.update(params.pop('cookies', {}))
        if as_user is True:
            as_user = config.get('sanity.user', 'sanity_user')
        if as_user:
            user = User.by_username(as_user)
            if user:
                cookies.update(self.make_auth_cookies(user))
            else:
                LOG.warn("User %s does not exist", as_user)

        func = getattr(requests, verb)
        if url.startswith('/'):
            url = self.expand_uri(url)
        return func(url, cookies=cookies or None, **params)

    def get(self, uri, **kw):
        return self._http_request('get', uri, **kw)

    def head(self, uri, **kw):
        return self._http_request('head', uri, **kw)

    def post(self, uri, data=None, **kw):
        if data is None:
            data = {}
        if not '_session_id' in data:
            data['_session_id'] = self._session_id
        return self._http_request('get', uri, **kw)
