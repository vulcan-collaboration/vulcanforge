# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import hashlib
import logging
import os
from StringIO import StringIO
from urlparse import urlparse, urlsplit

import bson
from bson.objectid import ObjectId
from ming.odm.odmsession import ThreadLocalODMSession, session
from formencode import validators
from formencode.api import Invalid
from paste.deploy.converters import asbool
from webob import exc as wexc, exc
from pylons import tmpl_context as c, app_globals as g
from tg import (
    expose,
    flash,
    redirect,
    validate,
    config,
    request,
    override_template
)
import tg
from tg.decorators import with_trailing_slash, without_trailing_slash
import pyotp
import qrcode

from vulcanforge.artifact.model import ArtifactReference
from vulcanforge.auth.exceptions import (
    PasswordAlreadyUsedError,
    PasswordInvalidError,
    PasswordCannotBeChangedError
)
from vulcanforge.auth.oauth.forms import OAuthRevocationForm
from vulcanforge.auth.oauth.model import OAuthAccessToken
from vulcanforge.auth.validators import (
    UsernameFormatValidator,
    get_complexity
)
from vulcanforge.auth.model import (
    EmailAddress,
    PasswordResetToken,
    EmailChangeToken,
    User,
    UserRegistrationToken,
    ApiToken,
    ServiceToken,
    LoginVerificationToken,
    TwoFactorAuthenticationToken
)
from vulcanforge.auth.widgets import (
    LoginForm,
    Login2Form,
    LoginVerifyForm,
    Avatar
)
from vulcanforge.auth.forms import (
    UserRegistrationEmailForm,
    UserRegistrationForm,
    PasswordResetEmailForm,
    PasswordResetForm,
    UnnamedUserRegistrationForm,
    TwoFactorAuthenticationForm,
    TwoFactorCredentialForm
)
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import (
    require_post,
    require_anonymous,
    validate_form,
    vardec
)
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.common.util import get_client_ip, cryptographic_nonce
from vulcanforge.common.widgets.forms import PasswordChangeForm, UploadKeyForm
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.notification.model import Mailbox
from vulcanforge.notification.tasks import sendmail
from vulcanforge.notification.util import gen_message_id
from vulcanforge.project.model import Project, AppConfig, RegistrationRequest, \
    MembershipInvitation
from vulcanforge.project.exceptions import NoSuchProjectError


LOG = logging.getLogger(__name__)

OID_PROVIDERS = [
    ('OpenID', '${username}'),
    ('Yahoo!', 'http://yahoo.com'),
    ('Google', 'https://www.google.com/accounts/o8/id'),
    ('MyOpenID', 'http://${username}.myopenid.com/'),
    ('LiveJournal', 'http://${username}.livejournal.com/'),
    ('Flickr', 'http://www.filckr.com/photos/${username}/'),
    ('Wordpress', 'http://${username}.wordpress.com/'),
    ('Blogger', 'http://${username}.blogspot.com/'),
    ('Vidoop', 'http://${username}.myvidoop.com/'),
    ('Verisign', 'http://${username}.pip.verisignlabs.com/'),
    ('ClaimID', 'http://openid.claimid.com/${username}/'),
    ('AOL', 'http://openid.aol.com/${username}/')
]
TEMPLATE_DIR = 'jinja:vulcanforge:auth/templates/'
REGISTRATION_ACTION = '/auth/send_user_registration_email'


class _AuthController(BaseController):

    class Forms(BaseController.Forms):
        login_form = LoginForm()
        login2_form = Login2Form()
        loginverify_form = LoginVerifyForm()
        user_registration_email_form = UserRegistrationEmailForm(
            affiliate=False,
            action=REGISTRATION_ACTION)
        user_registration_form = UserRegistrationForm(
            action='/auth/do_user_registration')
        unnamed_registration_form = UnnamedUserRegistrationForm(
            action='/auth/do_user_registration')
        password_reset_email_form = PasswordResetEmailForm(
            action='/auth/send_password_reset_email')
        password_reset_form = PasswordResetForm(
            action='/auth/do_password_reset')

    def __init__(self):
        self.prefs = PreferencesController()

    def _login_params(self, request_kwargs):
        is_returning_to = False
        msgClass = ''
        orig_request = request.environ.get('pylons.original_request', None)
        if 'return_to' in request_kwargs:
            return_to = request_kwargs.pop('return_to')
            is_returning_to = True
        elif orig_request:
            return_to = orig_request.url
            is_returning_to = True
        elif request.referer:
            return_to = urlsplit(request.referer).path
            is_returning_to = True
        else:
            return_to = '/'
        if config.get('templates.login'):
            override_template(self.index, config.get('templates.login'))

        c.form = self.Forms.login_form
        return {
            'msg': '',
            'msgClass': msgClass,
            'oid_providers': OID_PROVIDERS,
            'return_to': return_to,
            'form_values': {'return_to': return_to},
            'can_register': g.show_register_on_login,
            'autocomplete': not g.production_mode,
            'is_returning_to': is_returning_to
        }

    def _login2_params(self, request_kwargs):
        msgClass = ''
        if config.get('templates.login2'):
            override_template(self.index, config.get('templates.login2'))

        c.form = self.Forms.login2_form
        return {
            'msg': '',
            'msgClass': msgClass,
            'autocomplete': not g.production_mode
        }

    def _loginverify_params(self, request_kwargs):
        msgClass = ''
        if config.get('templates.loginverify'):
            override_template(self.index, config.get('templates.loginverify'))

        c.form = self.Forms.loginverify_form
        return {
            'msg': '',
            'msgClass': msgClass,
            'autocomplete': not g.production_mode
        }

    @expose('auth/login.html')
    @require_anonymous
    @with_trailing_slash
    def index(self, **kwargs):
        return self._login_params(kwargs)

    @expose('auth/login.html')
    @without_trailing_slash
    def login(self, *args, **kwargs):
        return self._login_params(kwargs)

    @expose('auth/login2.html')
    @without_trailing_slash
    def login2(self, *args, **kwargs):
        return self._login2_params(kwargs)

    @expose('auth/loginverify.html')
    @without_trailing_slash
    def loginverify(self, *args, **kwargs):
        return self._loginverify_params(kwargs)

    @expose()
    def send_verification_link(self, a):
        addr = EmailAddress.by_address(a)
        if addr:
            addr.send_verification_link()
            flash('Verification link sent')
        else:
            flash('No such address', 'error')
        redirect(request.referer or '/')

    @expose()
    def verify_addr(self, a):
        addr = EmailAddress.query.get(nonce=a)
        if addr:
            addr.confirm()
            flash('Email address {} confirmed'.format(addr.email))
        else:
            flash('Unknown verification link', 'error')
        redirect('/')

    @expose()
    def logout(self):
        g.auth_provider.logout()
        redirect(g.post_logout_url)

    def stage_login_verification(self, user, destination):
        token = LoginVerificationToken.query.get(user_id=user._id)
        if not token:
            token = LoginVerificationToken()
            token.user_id = user._id
            token.email = user.get_email_address()
            token.client_ip = get_client_ip()
        token.nonce = token.generate_nonce(6)
        token.cookie =  hashlib.sha256(os.urandom(10)).hexdigest()
        token.destination = destination
        token.expiry_date = datetime.utcnow() + timedelta(seconds=120)
        verify = user.needs_account_verification
        token.reason = "account" if verify else "clientip"
        token.send_email()
        from tg import response
        is_production = asbool(config.get("is_production", False))
        secure = g.production_mode and is_production
        response.set_cookie("authverify", token.cookie, max_age=120,
                            overwrite=True, secure=secure)

    def stage_two_factor_login(self, user, destination):
        token = TwoFactorAuthenticationToken.query.get(user_id=user._id)
        if not token:
            token = TwoFactorAuthenticationToken()
            token.user_id = user._id
            token.client_ip = get_client_ip()
        token.cookie =  hashlib.sha256(os.urandom(10)).hexdigest()
        token.destination = destination
        token.expiry_date = datetime.utcnow() + timedelta(seconds=180)
        from tg import response
        is_production = asbool(config.get("is_production", False))
        secure = g.production_mode and is_production
        response.set_cookie("auth2", token.cookie, max_age=180,
                            overwrite=True, secure=secure)

    @expose()
    @require_post()
    @validate_form("login_form", error_handler=index)
    def do_login(self, return_to=None, **kw):
        if return_to and return_to != "/":
            landing_url = return_to
        else:
            user = c.form_values.get('username', User.anonymous())
            landing_url = user.landing_url()
        user = c.form_values.get('username')
        client_ip = get_client_ip()
        has_known_ips = user and len(user.login_clients) > 0
        can_check_ip = has_known_ips and client_ip is not None
        check_unknown = g.verify_login_clients and can_check_ip
        unknown_ip = (check_unknown and
                      client_ip.replace(".", "_") not in user.login_clients)
        if g.auth_two_factor and user and user.get_pref('two_factor_auth'):
            self.stage_two_factor_login(user, landing_url)
            redirect('/auth/login2')
        elif (user and user.needs_account_verification) or unknown_ip:
            self.stage_login_verification(user, user.landing_url())
            redirect('/auth/loginverify')
        redirect(landing_url)

    @expose()
    @require_post()
    @validate_form("login2_form", error_handler=login2)
    def do_login2(self, return_to=None, **kw):
        """Implements the second factor for two-factor authentication"""
        destination = c.form_values.get('destination')
        user = c.form_values.get('username')
        if user and user.needs_account_verification:
            self.stage_login_verification(user, user.landing_url())
            redirect('/auth/loginverify')
        redirect(destination)

    @expose()
    @require_post()
    @validate_form("loginverify_form", error_handler=loginverify)
    def do_loginverify(self, return_to=None, **kw):
        """Implements account and access verification"""
        destination = c.form_values.get('destination')
        redirect(destination)

    @expose()
    def refresh_repo(self, neighborhood, *rest):
        neighborhood = Neighborhood.by_prefix(neighborhood)
        if not neighborhood:
            return 'No Neighborhood at %s' % neighborhood

        if len(rest) > 1:
            project = rest[0]
            mount = rest[1]
        else:
            project = '--init--'
            mount = rest[0]

        try:
            g.context_manager.set(project, mount, neighborhood=neighborhood)
        except NoSuchProjectError:
            return 'No project at %s' % project
        if c.app is None or not getattr(c.app, 'repo'):
            return 'Cannot find repo at %s' % mount
        c.app.repo.refresh()
        return '%r refresh queued.\n' % c.app.repo

    @expose('auth/auth_password_reset.html')
    @with_trailing_slash
    def password_reset(self, token=None, **kw):
        form_values = dict()
        if not token:
            c.form = self.Forms.password_reset_email_form
        else:
            token_object = PasswordResetToken.query.get(nonce=token)
            if token_object and token_object.is_valid:
                c.form = self.Forms.password_reset_form
                form_values['token'] = token
            else:
                LOG.warn("Invalid token %s\n%s", token, token_object)
                if token_object:
                    token_object.delete()
                flash("The password reset token is invalid or has expired. "
                      "Please request another password reset.", 'error')
                redirect(g.login_url)
        return dict(token=token, form_values=form_values, **kw)

    @expose('json')
    @require_post()
    @validate_form("password_reset_email_form", error_handler=password_reset)
    def send_password_reset_email(self, email=None, **kw):
        LOG.debug("send_password_reset_email %s", email)
        user = User.by_email_address(email)
        if user:
            token = PasswordResetToken.query.get(user_id=user._id)
            if not token:
                token = PasswordResetToken()
                token.user_id = user._id
            token.email = email
            token.nonce = hashlib.sha256(os.urandom(10)).hexdigest()
            token.expiry_date = datetime.utcnow() + timedelta(hours=2)
            token.send_email()
        flash(
            "Please check your email for instructions to reset your password.",
            status='confirm')
        redirect('/auth/login')

    @expose()
    @require_post()
    @validate_form("password_reset_form", error_handler=password_reset)
    def do_password_reset(self, token=None, password=None, return_to=None,
                          **kw):
        LOG.debug("do_password_reset token: %s", token)
        token_object = PasswordResetToken.query.get(nonce=token)
        user = token_object.user
        try:
            user.set_password(password, as_admin=True)
        except PasswordAlreadyUsedError:
            flash('This password has been used before', 'error')
            return redirect('password_reset', {'token': token})
        except wexc.HTTPUnauthorized:
            flash('Improper password', 'error')
            return redirect('password_reset', {'token': token})
        token_object.delete()
        g.auth_provider.login(user)
        flash("Your password has been updated.", status="confirm")
        if return_to is None:
            return_to = user.landing_url()
        return redirect(return_to)

    @expose('auth/auth_cancel_email_mod.html')
    def cancel_email_modification(self, token=None, **kw):
        if not token:
            raise exc.HTTPNotFound()
        token_object = EmailChangeToken.query.get(nonce=token)
        if not token_object or not token_object.is_valid:
            LOG.warn('Invalid token %s from %s', token, get_client_ip())
            raise exc.HTTPNotFound()
        user = token_object.user
        email = token_object.old_email
        if not EmailAddress.by_address(email, confirmed=True):
            em = EmailAddress.upsert(email)
            em.confirm()
        user.set_pref('email_address', email)
        EmailChangeToken.query.remove({
            'user_id': user._id,
            'created_date': {
                '$gte': token_object.created_date
            }
        })
        return {}

    @expose('auth/registration.html')
    @require_anonymous
    @with_trailing_slash
    def register(self, token=None, **kw):
        form_values = dict()
        if not g.registration_allowed:
            tg.override_template(
                self.register,
                'auth/registration_closed.html'
            )
            return form_values
        if not token:
            c.form = self.Forms.user_registration_email_form
            kw.update(dict(step1='incomplete current',
                           step2='incomplete',
                           step3='incomplete'))
        else:
            token_object = UserRegistrationToken.query.get(nonce=token)
            if token_object and token_object.is_valid:
                if token_object.name:
                    c.form = self.Forms.user_registration_form
                else:
                    c.form = self.Forms.unnamed_registration_form
                form_values['token'] = token
                kw.update(dict(step1='complete',
                               step2='complete',
                               step3='incomplete current'))
            else:
                LOG.warn("Invalid token %s\n%s", token, token_object)
                if token_object:
                    token_object.delete()
                flash("The registration token is invalid or has expired. "
                      "Please register again.", 'error')
                redirect('.')
        return dict(kw, form_values=form_values)

    @expose()
    @require_post()
    @validate_form("user_registration_email_form", error_handler=register)
    def send_user_registration_email(self, email=None, name='', **kw):
        if not g.registration_allowed:
            redirect('/auth/register/')
        if EmailAddress.by_address(email, confirmed=True):
            flash("This email address has already been claimed by a user.",
                  status='error')
            redirect('/auth/')

        token = UserRegistrationToken.query.get(email=email)
        if not token:
            token = UserRegistrationToken()
            token.email = email
        token.name = name
        token.nonce = hashlib.sha256(os.urandom(10)).hexdigest()
        token.expiry_date = datetime.utcnow() + timedelta(hours=2)
        token.send()
        redirect_to = '/'
        flash("Please check your email for instructions "
              "to complete your registration.", status='confirm')

        redirect(redirect_to)

    @expose('json')
    @require_post()
    @validate_form("unnamed_registration_form", error_handler=register)
    def do_user_registration(self, token=None, username=None, password=None,
                             name=None, **kw):
        token = UserRegistrationToken.query.get(nonce=token)
        project, neighborhood = None, None
        if token.project:
            neighborhood = token.project.neighborhood
            project = token.project
        elif 'default_nbhd_membership' in config:
            neighborhood = Neighborhood.by_prefix(
                config['default_nbhd_membership'])
            project = neighborhood.neighborhood_project
        user_cls = neighborhood.user_cls if neighborhood else User
        user = user_cls.register(
            {
                'username': username,
                'display_name': name or token.name,
                'password': password,
                'user_fields': token.user_fields
            },
            neighborhood=neighborhood)
        ThreadLocalODMSession.flush_all()
        user.claim_address(token.email, confirmed=True, is_primary=True)
        if project:
            # add user to project
            project.user_join_project(
                user,
                role=token.project_role,
                notify=True,
                notify_ac_id=project.app_config('admin')._id
            )
        token.delete()
        ThreadLocalODMSession.flush_all()
        g.auth_provider.login(user)  # log them in auto-magically
        redirect_url = user.landing_url()

        # set user_id in outstanding email project invitations
        auto_join = asbool(config.get('auto_join_projects', True))
        # case insensitive email matching
        user_address = user.get_email_address().lower()
        mq = MembershipInvitation.query
        q = {"email": {"$ne": None}, "user_id": None}
        invites = [x for x in mq.find(q) if x.email.lower() == user_address]
        for invite in invites:
            if invite.project and not invite.project.deleted:
                invite.user_id = user._id
                ThreadLocalODMSession.flush_all()
                if auto_join:
                    invite.project.user_join_project(
                        user, notify=True, role=invite.project_role)
            else:
                invite.delete()
                ThreadLocalODMSession.flush_all()
        redirect_url = user.landing_url()

        # Send Welcome Email
        # TODO: replace with vf notification if possible.
        LOG.info("Sending welcome email to %s", token.email)
        template = g.jinja2_env.get_template(
            'vulcanforge.common:templates/mail/welcome.txt'
        )
        forge_name = g.forge_name
        text = template.render(dict(user=user, forge_name=forge_name))
        self._send_user_email(
            token.email,
            "Welcome to {}!".format(forge_name or 'Our Forge!'),
            text
        )

        flash('User "%s" registered' % user.get_pref('display_name'))
        redirect(redirect_url)

    def _send_user_email(self, email, subject, text):
        sendmail.post(
            fromaddr=g.forgemail_return_path,
            destinations=[email],
            reply_to=g.forgemail_return_path,
            subject=subject,
            message_id=gen_message_id(),
            text=text
        )

    @expose('json')
    def username_available(self, username):
        if not g.registration_allowed:
            return dict(
                available=False,
                status="Registration is currently closed"
            )
        if username == '':
            return dict(available=False, status="")

        if username == "user":
            return dict(available=False, status="Username unavailable")

        if len(username) < 3:
            return dict(
                available=False,
                status="Usernames must be at least 3 characters long!"
            )

        user = User.by_username(username)
        if user:
            return dict(
                available=False,
                status="The name `{}` is already in use.".format(username)
            )

        validator = UsernameFormatValidator()
        try:
            validator.to_python(username, None)
        except Invalid, e:
            return dict(available=False, status=str(e))

        return dict(available=True,
                    status="The name `{}` is available.".format(username))

    @expose()
    def renew_session(self):
        return "OK"

    @expose('json')
    def password_requirements(self):
        retval = get_complexity()
        min = int(config.get('auth.pw.min_length', 10))
        max = int(config.get('auth.pw.max_length', 512))
        retval.update(dict(min_length=min, max_length=max))
        return retval

    @expose()
    def qrcode(self):
        """returns QR code for current user's TOTP key"""
        g.security.require_authenticated()
        key = c.user.user_fields.get('totp', pyotp.random_base32())
        if 'totp' not in c.user.user_fields:
            c.user.user_fields.update(dict(totp=key))
        site = urlparse(g.base_url).hostname
        ident = "{}@{}".format(c.user.username, site)
        t = pyotp.TOTP(key)
        q = qrcode.make(t.provisioning_uri(ident))
        img = StringIO()
        q.save(img)
        img.seek(0)
        from tg import response
        response.headers['Content-Type'] = "image/png"
        return iter(img)        


class _ModeratedAuthController(_AuthController):
    """
    Auth controller override for moderated registration situations

    """
    class Forms(_AuthController.Forms):
        user_registration_email_form = UserRegistrationEmailForm(
            affiliate=True,
            action=REGISTRATION_ACTION)

    # do not store these fields in user.user_fields on registration
    SKIP_FIELDS = [
        'recaptcha_challenge_field',
        'recaptcha_response_field'
    ]

    @expose('auth/login.html')
    @require_anonymous
    @with_trailing_slash
    def index(self, **kwargs):
        result = super(_ModeratedAuthController, self).index(**kwargs)
        result["msg"] = "Use your VF Access ID to sign in."
        return result

    @expose('auth/registration.html')
    @require_anonymous
    @with_trailing_slash
    def register(self, **kw):
        """This is necessary because the error_handler argument of tg.validate
        will not allow accessing subclass attributes.

        TODO: fix this...somehow...
        """
        return super(_ModeratedAuthController, self).register(**kw)

    @expose()
    @require_post()
    @validate_form("user_registration_email_form", error_handler=register)
    def send_user_registration_email(self, email=None, name='', **kw):
        user_fields = {k: v for k, v in kw.items()
                       if k not in self.SKIP_FIELDS}
        with g.context_manager.push(g.site_admin_project, 'admin'):
            req = RegistrationRequest.upsert(
                email=email,
                name=name,
                user_fields=user_fields,
                project_id=c.project._id
            )
            req.flush_self()
            req.notify()
        redirect('moderate_thanks')

    @expose('auth/moderate_thanks.html')
    def moderate_thanks(self):
        return dict()


# determine whether to moderate general registrations
#   Use visibility mode settings unless explicitly defined
_moderate = asbool(
    config.get('moderate_registration',
               config.get('visibility_mode') == 'closed'))
AuthController = _ModeratedAuthController if _moderate else _AuthController


class UserStatePreferencesRESTController(object):
    def __init__(self, key):
        self.key = key

    def _check_security(self, *args, **kwargs):
        if c.user.is_anonymous:
            raise exc.HTTPNotFound

    @expose('json')
    def index(self, **kwargs):
        if request.method == "GET":
            return self.index_get()
        elif request.method == "POST":
            return self.index_post(**kwargs)
        else:
            raise exc.HTTPMethodNotAllowed

    def index_get(self):
        if self.key not in c.user.state_preferences:
            raise exc.HTTPNotFound
        return c.user.state_preferences[self.key]

    def index_post(self, **kwargs):
        c.user.state_preferences[self.key] = kwargs


class PreferencesController(BaseController):

    class Forms(BaseController.Forms):
        oauth_revocation_form = OAuthRevocationForm(action='revoke_oauth')
        password_change = PasswordChangeForm(
            action='/auth/prefs/change_password')
        two_factor_auth = TwoFactorAuthenticationForm(
            action='/auth/prefs/set_two_factor_auth')
        two_factor_credential = TwoFactorCredentialForm(
            action='/auth/prefs/change_two_factor_credential')
        upload_key = UploadKeyForm(
            action='/auth/prefs/upload_sshkey')

    def _before(self, *args, **kwargs):
        c.custom_sidebar_menu = [
            SitemapEntry('Profile', c.user.url()),
            SitemapEntry('Settings'),
            SitemapEntry('Edit Profile Info',
                         c.user.url() + 'profile/edit_profile'),
            SitemapEntry('Preferences', '/auth/prefs'),
            SitemapEntry('Subscriptions', '/auth/prefs/subscriptions'),
        ]

    @expose()
    def _lookup(self, name, *remainder):
        if name == 'state':
            return UserStatePreferencesRESTController(
                key='/'.join(remainder)), []

    @with_trailing_slash
    @expose('auth/user_preferences.html')
    def index(self, **kw):
        g.security.require_authenticated()
        c.revoke_access = self.Forms.oauth_revocation_form
        api_token = ApiToken.query.get(user_id=c.user._id)
        form_dict = dict(
            api_token=api_token,
            authorized_applications=OAuthAccessToken.for_user(c.user),
            password_change_form=self.Forms.password_change,
            upload_key_form=self.Forms.upload_key
        )
        if g.auth_two_factor:
            setting_form = self.Forms.two_factor_auth(
                value={'totp_auth': c.user.get_pref('two_factor_auth')})
            form_dict.update(dict(two_factor_auth=setting_form))
            if c.user.get_pref('two_factor_auth'):
                cred_form = self.Forms.two_factor_credential(
                    value={'code': c.user.user_fields['totp']})
                form_dict.update(dict(two_factor_credential=cred_form))
        return form_dict

    @without_trailing_slash
    @expose('auth/user_subscriptions.html')
    def subscriptions(self, **kw):
        g.security.require_authenticated()

        # make list of editable mailboxes
        mailboxes = Mailbox.query.find({
            'user_id': c.user._id,
            'project_id': {"$ne": None},
            'is_flash': False})
        project_ids = set()
        for mailbox in mailboxes:
            # delete broken subscriptions
            if mailbox.project is None:
                mailbox.delete()
                continue
            # exclude missing app_configs
            if mailbox.app_config is None:
                continue
            project_ids.add(mailbox.project_id)
        project_ids.update([p._id for p in c.user.my_projects()
                            if not p.is_user_project()])
        project_cls = c.user.registration_neighborhood().project_cls
        projects = project_cls.query_find({'_id': {'$in': list(project_ids)}})

        project_data_items = []
        for project in projects:
            if not g.security.has_access(project, 'read'):
                continue
            project_data = {
                'project': project,
                'app_config_data_items': [],
                'subscribed': False,
            }
            for mount in project.ordered_mounts():
                app_config = mount.get('ac', None)
                if app_config is None or not g.security.has_access(app_config,
                                                                   'read'):
                    continue
                artifact_mbs = Mailbox.query.find({
                    'user_id': c.user._id,
                    'app_config_id': app_config._id,
                    'artifact_index_id': {'$ne': None},
                })
                app_mb = Mailbox.query.get(user_id=c.user._id,
                                           app_config_id=app_config._id,
                                           artifact_index_id=None)
                subscribed = artifact_mbs.count() > 0 or app_mb is not None
                app_config_data = {
                    'app_config': app_config,
                    'subscribed': subscribed,
                    'app_mailbox': app_mb,
                    'artifact_mailboxes': artifact_mbs.all(),
                    'type': getattr(app_mb, 'type', 'direct'),
                    'frequency': getattr(app_mb, 'frequency', {
                        'n': 1,
                        'unit': 'day',
                    }),
                }
                project_data['subscribed'] = project_data['subscribed'] or \
                                             app_config_data['subscribed']
                project_data['app_config_data_items'].append(app_config_data)
            project_data_items.append(project_data)

        # get exchange items
        exchange_data_items = []
        for exchange in g.exchange_manager.exchanges:
            artifact_mbs = Mailbox.query.find({
                'user_id': c.user._id,
                'exchange_uri': exchange.config['uri'],
                'artifact_index_id': {'$ne': None}
            })
            xcng_mb = Mailbox.query.get(
                user_id=c.user._id,
                exchange_uri=exchange.config['uri'])
            xcng_data = {
                'uri': exchange.config['uri'],
                'name': exchange.config['name'],
                'icon_url': g.resource_manager.absurl(exchange.config['icon']),
                'mailbox': xcng_mb,
                'artifact_mailboxes': artifact_mbs.all()
            }
            if xcng_mb:
                xcng_data.update({
                    "subscribed": True,
                    "type": xcng_mb.type,
                    "frequency": xcng_mb.frequency
                })
            else:
                xcng_data.update({
                    "subscribed": False,
                    "type": "direct",
                    "frequency": {
                        "n": 1,
                        "unit": "day"
                    }
                })
            exchange_data_items.append(xcng_data)

        return {
            'autosubscribe': c.user.get_pref('autosubscribe'),
            'message_emails': c.user.get_pref('message_emails'),
            'project_data_items': project_data_items,
            'exchange_data_items': exchange_data_items
        }

    @without_trailing_slash
    @vardec
    @expose('json')
    @require_post()
    def update_subscriptions(self, general=None, app_config_ids=None,
                             mailbox_ids=None, app_configs=None,
                             exchanges=None, mailboxes=None, **kwargs):
        # autosubscribe
        autosubscribe = general is not None and 'autosubscribe' in general
        c.user.set_pref('autosubscribe', autosubscribe)
        # message_emails
        message_emails = general is not None and 'message_emails' in general
        c.user.set_pref('message_emails', message_emails)
        # unsubscribe all
        unsubscribe_all = general is not None and 'unsubscribe_all' in general
        if unsubscribe_all:
            Mailbox.query.remove({
                'user_id': c.user._id,
            })
            return redirect('subscriptions')

        if mailboxes is None:
            mailboxes = {}
        if not isinstance(mailbox_ids, list):
            mailbox_ids = [mailbox_ids]
            # remove mailboxes
        mb_keep_ids = [k for k in mailboxes if 'subscribe' in mailboxes[k]]
        mb_remove_ids = [i for i in mailbox_ids if i not in mb_keep_ids]
        Mailbox.query.remove({
            'user_id': c.user._id,
            '_id': {'$in': map(ObjectId, mb_remove_ids)}
        })

        # exchange subscriptions
        if exchanges is None:
            exchanges = {}
        for exchange_uri, info in exchanges.items():
            s_type = info.get("type", "direct")
            s_freq = info.get('frequency', {})
            s_freq_n = int(s_freq.get('n', 1))
            s_freq_unit = s_freq.get("unit", "day")
            if 'subscribe' in info:
                Mailbox.subscribe(
                    exchange_uri=exchange_uri,
                    type=s_type,
                    n=s_freq_n,
                    unit=s_freq_unit)
            Mailbox.query.update(
                {
                    "user_id": c.user._id,
                    "exchange_uri": exchange_uri
                }, {
                    "$set": {
                        "type": s_type,
                        "frequency": {
                            "n": s_freq_n,
                            "unit": s_freq_unit
                        }
                    }
                },
                multi=True
            )

        # app config subscriptions
        # Reduce queries by collecting all ac_ids at the beginning
        if app_configs is None:
            app_configs = {}
        app_config_add_ids = [ObjectId(k) for k, v in app_configs.items()
                              if 'subscribe' in v]
        app_config_objects = AppConfig.query.find({
            '_id': {'$in': app_config_add_ids}
        })
        for ac in app_config_objects:
            Mailbox.subscribe(user_id=c.user._id,
                              project_id=ac.project_id,
                              app_config_id=ac._id)

        # update mailbox settings per app config
        for _id, info in app_configs.items():
            s_type = info.get('type', 'direct')
            s_freq = info.get('frequency', {})
            s_freq_n = int(s_freq.get('n', 1))
            s_freq_unit = s_freq.get('unit', 'day')
            Mailbox.query.update(
                {
                    'user_id': c.user._id,
                    'app_config_id': ObjectId(_id),
                }, {
                    '$set': {
                        'type': s_type,
                        'frequency': {
                            'n': s_freq_n,
                            'unit': s_freq_unit,
                        },
                    },
                }, multi=True)

        # flush and fire
        Mailbox.fire_ready()

        return redirect('subscriptions')

    @without_trailing_slash
    @expose()
    def send_digest(self, return_to=None, **kwargs):
        g.security.require_authenticated()
        Mailbox.query.update(
            {'user_id': c.user._id},
            {
                '$set': {
                    'next_scheduled': datetime.utcnow(),
                }
            }, multi=True)
        ThreadLocalODMSession.flush_all()
        Mailbox.fire_ready()
        flash("Digest emails sent", "confirm")
        return redirect(return_to or 'subscriptions')

    @with_trailing_slash
    @expose()
    def subscribe_project(self, project_id=None, return_to=None,
                          **kwargs):
        g.security.require_authenticated()
        project = Project.query_get(_id=ObjectId(project_id))
        if project is None:
            raise wexc.HTTPBadRequest("Project does not exist")
        for app_config in project.app_configs:
            Mailbox.subscribe(user_id=c.user._id, project_id=project._id,
                              app_config_id=app_config._id)
        return redirect(return_to or project.url())

    @with_trailing_slash
    @expose()
    def unsubscribe_project(self, project_id=None, return_to=None,
                            **kwargs):
        g.security.require_authenticated()
        project = Project.query_get(_id=ObjectId(project_id))
        if project is None:
            raise wexc.HTTPBadRequest("Project does not exist")
        Mailbox.query.remove({
            'user_id': c.user._id,
            'project_id': project._id,
        })
        return redirect(return_to or project.url())

    @with_trailing_slash
    @expose()
    def subscribe_app(self, app_config_id=None, return_to=None,
                      **kwargs):
        g.security.require_authenticated()
        app_config = AppConfig.query.get(_id=ObjectId(app_config_id))
        if app_config is None:
            raise wexc.HTTPBadRequest("App does not exist")
        Mailbox.subscribe(user_id=c.user._id,
                          project_id=app_config.project_id,
                          app_config_id=app_config._id)
        return redirect(return_to or app_config.url())

    @with_trailing_slash
    @expose()
    def unsubscribe_app(self, app_config_id=None, return_to=None,
                        **kwargs):
        g.security.require_authenticated()
        app_config = AppConfig.query.get(_id=ObjectId(app_config_id))
        if app_config is None:
            raise wexc.HTTPBadRequest("App does not exist")
        Mailbox.query.remove({
            'user_id': c.user._id,
            'project_id': app_config.project_id,
            'app_config_id': app_config._id,
        })
        return redirect(return_to or app_config.url())

    @with_trailing_slash
    @expose()
    def subscribe_artifact(self, artifact_index_id=None, return_to=None,
                           **kwargs):
        g.security.require_authenticated()
        ref = ArtifactReference.query.get(_id=artifact_index_id)
        if ref is None or ref.artifact is None:
            raise wexc.HTTPBadRequest("Artifact does not exist")
        artifact = ref.artifact
        app_config_id = artifact.app_config_id
        project_id = artifact.project_id
        Mailbox.subscribe(user_id=c.user._id, project_id=project_id,
                          app_config_id=app_config_id, artifact=artifact)
        return redirect(return_to or artifact.url())

    @with_trailing_slash
    @expose()
    def unsubscribe_artifact(self, artifact_index_id=None, return_to=None,
                             **kwargs):
        g.security.require_authenticated()
        ref = ArtifactReference.query.get(_id=artifact_index_id)
        if ref is None or ref.artifact is None:
            raise wexc.HTTPBadRequest("Artifact does not exist")
        artifact = ref.artifact
        app_config_id = artifact.app_config_id
        project_id = artifact.project_id
        Mailbox.unsubscribe(user_id=c.user._id, project_id=project_id,
                            app_config_id=app_config_id,
                            artifact_index_id=artifact_index_id)
        return redirect(return_to or artifact.url())

    @vardec
    @expose()
    @require_post()
    def update(self, display_name=None, addr=None, new_addr=None,
               primary_addr=None, oid=None, new_oid=None, preferences=None,
               **kw):
        g.security.require_authenticated()
        if display_name is None:
            display_name = c.user.display_name
        if display_name is None:
            flash("Display Name cannot be empty.", 'error')
            redirect('.')
        c.user.set_pref('display_name', display_name)
        if g.user_change_primary_email:
            if c.user.get_pref('email_address') != primary_addr:
                token = EmailChangeToken(
                    old_email=c.user.get_pref('email_address'),
                    new_email=primary_addr)
                token.send_email()
                c.user.set_pref('email_address', primary_addr)
            for i, (old_a, data) in enumerate(zip(
                    c.user.email_addresses, addr or [])):
                obj = c.user.address_object(old_a)
                if data.get('delete') or not obj:
                    if primary_addr != c.user.email_addresses[i]:
                        del c.user.email_addresses[i]
                        if obj:
                            obj.delete()
                    else:
                        flash('Primary e-mail address cannot be deleted',
                              'error')
            if new_addr.get('claim'):
                if EmailAddress.by_address(new_addr['addr'], confirmed=True):
                    flash('Email address already claimed', 'error')
                else:
                    em = EmailAddress.upsert(new_addr['addr'])
                    em.send_verification_link()
        for i, (old_oid, data) in enumerate(zip(
                c.user.open_ids, oid or [])):
            obj = c.user.openid_object(old_oid)
            if data.get('delete') or not obj:
                del c.user.open_ids[i]
                if obj:
                    obj.delete()
        if preferences:
            for k, v in preferences.iteritems():
                if k == 'results_per_page':
                    v = int(v)
                c.user.set_pref(k, v)
        redirect('.')

    @expose()
    @require_post()
    def gen_api_token(self):
        g.security.require_authenticated()
        tok = ApiToken.query.get(user_id=c.user._id)
        if tok is None:
            tok = ApiToken(user_id=c.user._id)
        else:
            tok.secret_key = cryptographic_nonce()
        redirect(request.referer or 'index')  # TODO: check

    @expose()
    @require_post()
    def del_api_token(self):
        g.security.require_authenticated()
        tok = ApiToken.query.get(user_id=c.user._id)
        if tok is None:
            return
        tok.delete()
        redirect(request.referer or 'index')  # TODO: check

    @expose('json')
    @require_post()
    def gen_service_token(self, upsert=True, **kw):
        """
        Generate a new service token

        :param upsert: if True, use existing if available. Otherwise, always
         generate new
        :param kw:
        :return: json {'service_token': str}

        """
        g.security.require_authenticated()
        if upsert:
            token_obj = ServiceToken.upsert()
        else:
            ServiceToken.query.remove({'user_id': c.user._id})
            token_obj = ServiceToken(user_id=c.user._id)
            session(ServiceToken).flush(token_obj)

        return {
            'service_token': token_obj.api_key
        }

    @expose('json')
    @require_post()
    def del_service_token(self):
        g.security.require_authenticated()
        token_obj = ServiceToken.query.get(user_id=c.user._id)
        if not token_obj:
            raise exc.HTTPNotFound()
        token_obj.delete()

        return {
            'success': True
        }

    @expose()
    @require_post()
    def revoke_oauth(self, _id=None):
        tok = OAuthAccessToken.query.get(_id=bson.ObjectId(_id))
        if tok is None:
            flash('Invalid app ID', 'error')
            redirect('.')
        if tok.user_id != c.user._id:
            flash('Invalid app ID', 'error')
            redirect('.')
        tok.delete()
        flash('Application access revoked')
        redirect('.')

    @expose()
    @require_post()
    @validate_form('password_change', error_handler=index)
    def change_password(self, oldpw=None, password=None, **kw):
        g.security.require_authenticated()
        min_hours = int(tg.config.get('auth.pw.min_lifetime.hours', 24))
        if c.user.password_set_at is None:
            c.user.password_set_at = datetime.utcnow() - \
                                     timedelta(hours=min_hours)
        age = datetime.utcnow() - c.user.password_set_at
        if age < timedelta(hours=min_hours):
            flash("Passwords may only be changed once every {} "
                  "hours".format(min_hours), 'error')
            redirect('.')
        if oldpw:
            if not g.auth_provider.validate_password(c.user, oldpw):
                flash('Incorrect old password', 'error')
                redirect('.')
        try:
            c.user.set_password(password, current=oldpw)
        except PasswordInvalidError:
            flash('Password requirements not met', 'error')
            redirect('.')
        except PasswordCannotBeChangedError:
            flash('Password minimum lifetime not yet exceeded', 'error')
            redirect('.')
        except PasswordAlreadyUsedError:
            flash('Password has been used before', 'error')
            redirect('.')
        flash('Password changed')
        redirect('.')

    @expose()
    @require_post()
    def set_two_factor_auth(self, totp_auth=False, **kwargs):
        g.security.require_authenticated()
        c.user.set_pref('two_factor_auth', bool(totp_auth))
        if totp_auth and 'totp' not in c.user.user_fields:
            key = pyotp.random_base32()
            c.user.user_fields.update(dict(totp=key))
        msg = 'Two-Factor Authentication {}'
        flash(msg.format('enabled' if totp_auth else 'disabled'))
        redirect('.')

    @expose()
    @require_post()
    def change_two_factor_credential(self, *args, **kwargs):
        g.security.require_authenticated()
        key = pyotp.random_base32()
        c.user.user_fields.update(dict(totp=key))
        if 'skip' not in kwargs:
            flash('Two-Factor Authentication key changed')
            redirect('.')

    @expose('json')
    def config_test(self):
        g.security.require_authenticated()
        two_factor = g.auth_two_factor
        if 'totp' not in c.user.user_fields:
            change_two_factor(skip=True)
        if two_factor:
            t = pyotp.TOTP(c.user.user_fields['totp'])
            return dict(status='success', now=t.now(), interval=t.interval)
        reason = "Platform does not support two-factor authentication"
        return dict(status="failed", reason=reason)

    @expose()
    @require_post()
    def upload_sshkey(self, key=None, **kwargs):
        if g.user_ssh_public_key:
            g.security.require_authenticated()
            c.user.public_key = key
            try:
                g.auth_provider.upload_sshkey(c.user.username, key)
            except AssertionError, ae:
                flash('Error uploading key: %s' % ae, 'error')
            flash('Key uploaded')
        redirect('.')

    @expose()
    @require_post()
    def delete_account(self, password, **kw):
        g.security.require_authenticated()
        if not g.auth_provider.validate_password(c.user, password):
            flash('Incorrect Password', 'error')
            redirect('.')
        c.user.delete_account()
        g.auth_provider.logout()
        redirect(g.post_logout_url)


class UserDiscoverController(BaseController):
    """Controller to search and browse the users of the forge"""

    hide_sidebar = True
    user_title = "Users"

    class Widgets(BaseController.Widgets):
        avatar = Avatar()

    def _get_base_q(self):
        return ' AND '.join((
            'type_s:User',
            'public_b:true',
            'disabled_b:false'
        ))

    @expose('json')
    def allusers(self, **kw):
        g.security.require_authenticated()
        users = [x for x in User.query.find()
                    if x.is_real_user() and not x.disabled]
        usrs = []
        for ur in users:
            u = {}
            pinfo = ur.get_profile_info()
            u['name'] = ur.display_name
            u['expertise'] = ur.expertise
            u['url'] = ur.url();
            u['disabled'] = ur.disabled;
            u['icon'] = ur.icon_url()
            u['company'] = ur.user_fields.get('company')
            u['position'] = ur.user_fields.get('position')
            u['mission'] = pinfo.get('mission')
            u['email'] = ur.get_email_address()
            u['interests'] = pinfo.get('interests')
            u['telephone'] = ur.user_fields.get('telephone', None)
            u['jdate'] = pinfo.get('userSince')
            u['lastlog'] = ur.last_login
            u['username'] = ur.username
            usrs.append(u)
        return {'users': usrs, 'forgename': config.get('forge_name')}

    @expose('auth/user_browse.html')
    @validate(dict(
        limit=validators.Int(if_empty=100),
        start=validators.Int(if_empty=0),
        q=validators.String(if_empty=None)
    ))
    def index(self, q=None, limit=100, start=0, **kw):
        full_q = self._get_base_q()
        if q:
            full_q = ' AND '.join((q, full_q))
        params = {
            "q": full_q,
            "rows": limit,
            "start": start,
            "sort": 'trustscore_f desc'
        }
        never_listed = ('root', '*anonymous', '*authenticated')
        results = g.search(**params)
        if results:
            users = [
            User.by_username(doc['username_s']) for doc in results.docs
            if doc['username_s'] not in never_listed
        ]
        else:
            users = []
        c.avatar = self.Widgets.avatar
        return dict(
            users=users,
            hide_sidebar=self.hide_sidebar,
            user_title=self.user_title,
            limit=limit,
            cur_page=int(start / limit),
            count=results.hits,
            cur_url=request.path_info,
            visible=min(limit, results.hits)
        )
