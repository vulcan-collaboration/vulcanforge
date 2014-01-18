import logging
import re
from itertools import ifilter
from urllib import urlencode

import tg
from tg import redirect
from vulcanforge.auth.model import User

LOG = logging.getLogger(__name__)


class VisibilityModeHandler(object):
    """
    Redirects unauthorized users if visibility_mode closed is engaged

    """
    MODES = dict(
        default=False,
        open=False,
        closed=True
    )
    url_whitelist = [
        re.compile(r'^/favicon\.(ico|gif|png|jpg)'),
        re.compile(r'^/error'),
        re.compile(r'\.(js|css)$'),
        re.compile(r'^/_test_vars'),
        re.compile(r'^/webs/'),
        re.compile(r'^/rest/'),
        re.compile(r'^/static_auth/')
    ]

    def __init__(self, app):
        self.app = app
        self.mode = tg.config.get('visibility_mode', 'default')
        # bail early if disabled
        if self.is_enabled:
            self.login_url = tg.config.get('auth.login_url', '/auth/')
            self.login_url = "/{}/".format(self.login_url.strip('/'))
            self.url_whitelist.append(re.compile('^{}'.format(self.login_url)))
            holes = tg.config.get('visibility_holes', '')
            for hole in ifilter(None, holes.split(',')):
                regex = re.compile(hole)
                self.url_whitelist.append(regex)

    def check_visibility(self, user, request):
        pass


    @property
    def is_enabled(self):
        return self.MODES[self.mode]

    def is_whitelisted(self, request):
        path = request.path_info
        for p in self.url_whitelist:
            if p.match(path):
                return True
        return False

    def get_redirect_location(self, request):
        if request.method == 'GET' and request.path_info is not '/':
            return_to = request.path_info
            if request.query_string:
                return_to += '?' + request.query_string
            location = self.get_login_url(dict(return_to=return_to))
        else:
            # Don't try to re-post; the body has been lost.
            location = self.get_login_url()
        return location

    def redirect(self, request):
        LOG.debug("Redirecting from %s", request.path_info)
        location = self.get_redirect_location(request)
        redirect(location)

    def get_login_url(self, params=None):
        if not params:
            return self.login_url
        return '?'.join((self.login_url, urlencode(params)))
