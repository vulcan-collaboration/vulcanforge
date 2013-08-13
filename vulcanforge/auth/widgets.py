# -*- coding: utf-8 -*-
import urllib
import urllib2
import logging

from paste.deploy.converters import asbool
from formencode.validators import FormValidator
from pylons import tmpl_context as c, app_globals as g, request
import tg
from tg import config
from formencode import Invalid
import ew as ew_core
from ew.core import validator
from ew.render import Snippet
import ew.jinja2_ew as ew
from webob.exc import HTTPUnauthorized

from vulcanforge.common import helpers as h
from vulcanforge.common.helpers import get_site_protocol
from vulcanforge.common.widgets.forms import ForgeForm
from vulcanforge.auth.model import FailedLogin, User

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:auth/templates/widgets/'


class LoginForm(ForgeForm):
    submit_text = 'Login'
    style = 'wide'
    defaults = dict(ForgeForm.defaults, autocomplete=True)

    class fields(ew_core.NameList):
        username = ew.TextField(
            label='Username', attrs=dict(autofocus='autofocus'), wide=True)
        password = ew.PasswordField(label='Password', wide=True)
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
            value['username'] = g.auth_provider.login()
        except HTTPUnauthorized:
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


class Avatar(ew_core.Widget):
    """
    An avatar-control for accessing user settings through interacting with
    the user-avatars on the screen

    """
    template = TEMPLATE_DIR + 'avatar.html'

    def display(self,
                user=None,
                size='48',
                className=None,
                show_icon=True,
                compact=False,
                extras=None,
                with_user_id=True,
                replace_with_userid=None,
                framed=False,
                **kw):

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
PUBLIC_KEY = tg.config.get(
    'recaptcha_public_key',
    '6LeTXcsSAAAAAAtmbk_0zHlDWT25db7dy-MYQOIo'
)
PRIVATE_KEY = tg.config.get(
    'recaptcha_private_key',
    '6LeTXcsSAAAAACxO7xaGEhp1UY9k4COKYiPbu6OO'
)
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
