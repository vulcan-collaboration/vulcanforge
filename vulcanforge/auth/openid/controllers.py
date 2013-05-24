import string
from urllib import urlencode
from pylons import app_globals as g, tmpl_context as c
from tg import expose, redirect, flash, session
from vulcanforge.auth.controllers import OID_PROVIDERS
from vulcanforge.auth.model import User
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import require_post
from vulcanforge.common.util.oid import verify_oid, process_oid
from vulcanforge.neighborhood.model import Neighborhood

TEMPLATE_DIR = 'jinja:vulcanforge:auth/openid/templates/'


class OpenIdController(BaseController):

    @expose(TEMPLATE_DIR + 'openid_login.html')
    def login_verify_oid(self, provider, username, return_to=None):
        if g.openid_enabled:
            if provider:
                oid_url = string.Template(provider).safe_substitute(
                    username=username)
            else:
                oid_url = username
            return verify_oid(
                oid_url,
                failure_redirect='.',
                return_to='login_process_oid?%s' % urlencode(dict(
                    return_to=return_to
                )),
                title='OpenID Login',
                prompt='Click below to continue')
        else:
            redirect('/')

    @expose()
    def login_process_oid(self, **kw):
        oid_obj = process_oid(failure_redirect='.')
        c.user = oid_obj.claimed_by_user()
        session['userid'] = c.user._id
        session.save()
        if not c.user.username:
            flash('Please choose a user name for SourceForge, %s.'
                  % c.user.get_pref('display_name'))
            redirect('setup_openid_user')
        redirect(kw.pop('return_to', '/'))

    @expose(TEMPLATE_DIR + 'bare_openid.html')
    def bare_openid(self, url=None):
        """
        Called to notify the user that they must set up a 'real' (with
        username) account when they have a pure openid account

        """
        if g.openid_enabled:
            return dict(location=url)
        else:
            redirect('/auth/prefs/')

    @expose(TEMPLATE_DIR + 'setup_openid_user.html')
    def setup_openid_user(self):
        if g.openid_enabled:
            return dict()
        else:
            redirect('/auth/prefs/')

    @expose()
    @require_post()
    def do_setup_openid_user(self, username=None, display_name=None):
        if g.openid_enabled:
            u = User.by_username(username)
            if u and username != c.user.username:
                flash(
                    'That username is already taken.  Please choose another.',
                    'error')
                redirect('setup_openid_user')
            c.user.username = username
            c.user.set_pref('display_name', display_name)
            if u is None:
                n = Neighborhood.query.get(name='Users')
                n.register_project('u/' + username)
            flash('Your username has been set to %s.' % username)
            redirect('/')
        else:
            redirect('/auth/prefs/')

    @expose(TEMPLATE_DIR + 'claim_openid.html')
    def claim_oid(self):
        if g.openid_enabled:
            return dict(oid_providers=OID_PROVIDERS)
        else:
            redirect('/auth/prefs/')

    @expose(TEMPLATE_DIR + 'openid_login.html')
    def claim_verify_oid(self, provider, username):
        if g.openid_enabled:
            if provider:
                oid_url = string.Template(provider).safe_substitute(
                    username=username)
            else:
                oid_url = username
            return verify_oid(oid_url, failure_redirect='claim_oid',
                              return_to='claim_process_oid',
                              title='Claim OpenID',
                              prompt='Click below to continue')
        else:
            redirect('/auth/prefs/')

    @expose()
    @require_post()
    def claim_process_oid(self, **kw):
        if g.openid_enabled:
            oid_obj = process_oid(failure_redirect='claim_oid')
            if c.user:
                c.user.claim_openid(oid_obj._id)
                flash('Claimed %s' % oid_obj._id)
            redirect('/auth/prefs/')
        else:
            redirect('/auth/prefs/')