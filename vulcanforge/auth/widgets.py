# -*- coding: utf-8 -*-
import urllib
import urllib2
import logging

from paste.deploy.converters import asbool
from formencode.validators import FormValidator
from pylons import tmpl_context as c, app_globals as g, request
import tg
from tg import config, request, response
from formencode import Invalid, validators
import ew as ew_core
from ew.core import validator
from ew.render import Snippet
import ew.jinja2_ew as ew
from webob.exc import HTTPUnauthorized

from vulcanforge.common import helpers as h
from vulcanforge.common.helpers import get_site_protocol
from vulcanforge.common.util import get_client_ip
from vulcanforge.common.widgets.forms import ForgeForm
from vulcanforge.auth.model import (
    FailedLogin,
    User,
    LoginVerificationToken,
    TwoFactorAuthenticationToken
)
from vulcanforge.auth.validators import PasswordValidator

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:auth/templates/widgets/'


class LoginForm(ForgeForm):
    submit_text = 'Login'
    style = 'wide'
    defaults = dict(ForgeForm.defaults, autocomplete=True)

    class fields(ew_core.NameList):
        username = ew.TextField(
            label='Username', attrs=dict(autofocus='autofocus'), wide=True)
        password = ew.PasswordField(
            label='Password',
            wide=True,
            validator=PasswordValidator()
        )
        return_to = ew.HiddenField()

    def context_for(self, field):
        ctx = super(LoginForm, self).context_for(field)
        if True or not self.autocomplete:
            ctx.setdefault("attrs", {})['autocomplete'] = 'off'
        return ctx

    @validator
    def validate(self, value, state=None):
        track_fails = asbool(config.get('login_lock.engaged', 'false'))
        if track_fails and FailedLogin.is_locked(request):
            msg = 'Maximum retry attempts exceeded. Please wait {} minutes' + \
                  ' and try again.'
            msg = msg.format(config.get('login_lock.interval', 'a couple'))
            raise Invalid(msg, value, state)
        try:
            value = super(LoginForm, self).validate(value, state)
            u = User.query.get(username=value['username'])
            two_factor = (g.auth_two_factor and
                          u and u.get_pref('two_factor_auth'))
            client_ip = get_client_ip()
            has_known_ips = u and len(u.login_clients) > 0
            can_check_ip = has_known_ips and client_ip is not None
            check_unknown = g.verify_login_clients and can_check_ip
            unknown_ip = (check_unknown and
                          client_ip.replace(".", "_") not in u.login_clients)
            verification = (u and u.needs_account_verification) or unknown_ip
            if two_factor or verification:
                if u.disabled:
                    msg = "User disabled"
                    raise Invalid(msg, dict(username=value['username']), None)
                valp = g.auth_provider.validate_password
                if valp(u, value['password']):
                    value['username'] = u
                else:
                    msg = 'Invalid login'
                    if track_fails:
                        FailedLogin.from_request(request)
                    raise Invalid(msg, dict(username=value['username']), None)
            else:
                value['username'] = g.auth_provider.login()
        except (Invalid, HTTPUnauthorized):
            # if user needs a password reset
            targeted_user = User.query.get(username=value['username'])
            if targeted_user and targeted_user.disabled:
                msg = 'Your account has been disabled. ' \
                      'Please contact us to re-enable your account.'
            elif (
                targeted_user is not None and
                targeted_user.needs_password_reset
            ):
                tg.flash('Your password has expired and must be reset.',
                         'error')
                tg.redirect('/auth/password_reset')
            else:
                msg = 'Invalid login'
                if track_fails:
                    FailedLogin.from_request(request)
            raise Invalid(msg, dict(username=value['username']), None)
        return value


class Login2Form(ForgeForm):
    submit_text = 'Login'
    style = 'wide'
    defaults = dict(ForgeForm.defaults, autocomplete=False)

    class fields(ew_core.NameList):

        totp_code = ew.NumberField(
            label='Code', attrs=dict(autofocus='autofocus'), wide=False)

    def context_for(self, field):
        ctx = super(Login2Form, self).context_for(field)
        if True or not self.autocomplete:
            ctx.setdefault("attrs", {})['autocomplete'] = 'off'
        return ctx

    @validator
    def validate(self, value, state=None):
        user = username = None
        track_fails = asbool(config.get('login_lock.engaged', 'false'))
        if track_fails and FailedLogin.is_locked(request):
            msg = 'Maximum retry attempts exceeded. Please wait {} minutes' + \
                  ' and try again.'
            msg = msg.format(config.get('login_lock.interval', 'a couple'))
            raise Invalid(msg, value, state)
        try:
            value = super(Login2Form, self).validate(value, state)
            c = request.cookies.pop('auth2', None)
            if not c:
                msg = "Maximum time exceeded.  Please begin login again."
                raise Invalid(msg, value, state)
            token = TwoFactorAuthenticationToken.query.get(cookie=c)
            if not (token and token.is_valid):
                msg = "Maximum time exceeded.  Please begin login again."
                raise Invalid(msg, value, state)
            if not token.verify(value['totp_code']):
                msg = "Invalid code"
                raise Invalid(msg, value, state)
            if token.user.needs_account_verification:
                value['username'] = token.user
            else:
                g.auth_provider.login(token.user)
            value['destination'] = token.destination
            token.delete()
            response.delete_cookie('auth2')
        except HTTPUnauthorized:
            # if user needs a password reset
            if user and user.disabled:
                msg = 'Your account has been disabled. ' \
                      'Please contact us to re-enable your account.'
            elif user is not None and user.needs_password_reset:
                tg.flash('Your password has expired and must be reset.',
                         'error')
                tg.redirect('/auth/password_reset')
            raise Invalid(msg, dict(username=username), None)
        except Invalid as e:
            if track_fails:
                d = dict(params={'username': username}, environ=request.environ)
                req = type('failed_request', (object,), d)
                FailedLogin.from_request(req)
            raise e
        return value


class LoginVerifyForm(ForgeForm):
    submit_text = 'Verify'
    style = 'wide'
    defaults = dict(ForgeForm.defaults, autocomplete=False)

    class fields(ew_core.NameList):

        code = ew.NumberField(
            label='Code', attrs=dict(autofocus='autofocus'), wide=False)

    def context_for(self, field):
        ctx = super(LoginVerifyForm, self).context_for(field)
        if True or not self.autocomplete:
            ctx.setdefault("attrs", {})['autocomplete'] = 'off'
        return ctx

    @validator
    def validate(self, value, state=None):
        user = username = None
        track_fails = asbool(config.get('login_lock.engaged', 'false'))
        if track_fails and FailedLogin.is_locked(request):
            msg = 'Maximum retry attempts exceeded. Please wait {} minutes' + \
                  ' and try again.'
            msg = msg.format(config.get('login_lock.interval', 'a couple'))
            raise Invalid(msg, value, state)
        try:
            value = super(LoginVerifyForm, self).validate(value, state)
            c = request.cookies.pop('authverify', None)
            if not c:
                msg = "Maximum time exceeded.  Please begin login again."
                raise Invalid(msg, value, state)
            token = LoginVerificationToken.query.get(cookie=c)
            if not (token and token.is_valid):
                msg = "Maximum time exceeded.  Please begin login again."
                raise Invalid(msg, value, state)
            if value['code'] != int(token.nonce):
                msg = "Invalid code"
                raise Invalid(msg, value, state)
            g.auth_provider.login(token.user)
            value['destination'] = token.destination
            token.user.needs_account_verification = False
            token.delete()
            response.delete_cookie('authverify')
        except HTTPUnauthorized:
            # if user needs a password reset
            if user and user.disabled:
                msg = 'Your account has been disabled. ' \
                      'Please contact us to re-enable your account.'
            elif user is not None and user.needs_password_reset:
                tg.flash('Your password has expired and must be reset.',
                         'error')
                tg.redirect('/auth/password_reset')
            raise Invalid(msg, dict(username=username), None)
        except Invalid as e:
            if track_fails:
                d = dict(params={'username': username}, environ=request.environ)
                req = type('failed_request', (object,), d)
                FailedLogin.from_request(req)
            raise e
        return value


class Avatar(ew_core.Widget):
    """
    An avatar-control for accessing user settings through interacting with
    the user-avatars on the screen

    """
    template = TEMPLATE_DIR + 'avatar.html'

    def display(self, user=None, size='48', className=None, show_icon=True,
                compact=False, extras=None, with_user_id=True,
                replace_with_userid=None, framed=False, **kw):

        profile_public = user.public or c.user == user

        if not profile_public:
            with_user_id = False

        display_name = h.really_unicode(user.display_name)
        icon_url = user.icon_url()
        class_str = ' '.join([
            'avatar',
            className or '',
            'user-list-item' if framed else '',
            'with-user-id' if with_user_id else ''
        ])

        return ew_core.Widget.display(
            self,
            display_name=display_name,
            icon_url=icon_url,
            class_str=class_str,
            size=size,
            compact=compact,
            show_icon=show_icon,
            extras=extras,
            href=user.url() if profile_public else None,
            framed=framed,
            username=h.really_unicode(user.username),
            replace_with_userid=replace_with_userid,
            **kw
        )


class UsernameRegistrationField(ew.TextField):
    template = Snippet('''<input id="username_field"
        {{widget.j2_attrs({
        'type':field_type,
        'name':rendered_name,
        'class':css_class,
        'readonly':readonly,
        'value':value},
        attrs)}}>
        <span id="username_status" class="status"></span>''', 'jinja2')


API_URL = tg.config.get('recaptcha_api_url', "www.google.com/recaptcha/api")
PUBLIC_KEY = tg.config.get('recaptcha_public_key')
PRIVATE_KEY = tg.config.get('recaptcha_private_key')
VERIFY_URL = 'http://{}/verify'.format(API_URL)


class ReCaptchaValidator(FormValidator):
    validate_partial_form = True

    @validator
    def validate(self, values):
        if not 'recaptcha_challenge_field' in values\
           or not 'recaptcha_response_field' in values\
           or not values['recaptcha_challenge_field']\
        or not values['recaptcha_response_field']:
            return "Missing ReCaptcha answer"

        challenge = values['recaptcha_challenge_field']
        response = values['recaptcha_response_field']

        handle = urllib2.urlopen(VERIFY_URL, data=urllib.urlencode(dict(
            privatekey=PRIVATE_KEY,
            remoteip=tg.request.environ['REMOTE_ADDR'],
            challenge=challenge,
            response=response
        )))
        verification = handle.read()
        handle.close()

        if not 'true' in verification:
            return "Incorrect ReCaptcha answer"

        return None


class ReCaptchaField(ew.fields.InputField):
    label = "ReCaptcha"
    template = TEMPLATE_DIR + "recaptcha.html"
    wide = True

    def prepare_context(self, context):
        context = super(ReCaptchaField, self).prepare_context(context)
        context['label'] = self.label
        context['public_key'] = PUBLIC_KEY
        context['api_url'] = API_URL
        context['protocol'] = get_site_protocol()
        return context
