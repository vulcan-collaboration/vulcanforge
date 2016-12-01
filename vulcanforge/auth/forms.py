# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from paste.deploy.converters import asbool
import tg
import ew as ew_core
from ew.core import validator
import ew.jinja2_ew as ew
from formencode import Invalid
from formencode.validators import UnicodeString, Empty

from vulcanforge.common.validators import EmailValidator
from vulcanforge.common.widgets.forms import ForgeForm
from vulcanforge.common.widgets.form_fields import SetPasswordField
from vulcanforge.auth.model import (
    EmailAddress,
    UserRegistrationToken,
    User,
    PasswordResetToken
)
from vulcanforge.auth.validators import UsernameValidator, PasswordValidator
from vulcanforge.auth.widgets import (
    UsernameRegistrationField,
    ReCaptchaField,
    ReCaptchaValidator
)


class NameField(ew.TextField):
    defaults = dict(
        ew.TextField.defaults,
        label="Name",
        name="name",
        wide=True
    )
    validator = UnicodeString(
        min=2,
        max=255,
        messages={
            'empty': "Please specify a display name",
            'missing': "Please specify a display name"
        }
    )


class UserRegistrationEmailForm(ForgeForm):
    submit_text = 'request email with activation link'
    style = 'wide'

    def __init__(self, affiliate=False, ignore_key_missing=False, **kwargs):
        self.fields = []
        self.affiliate = affiliate
        if self.affiliate:
            name = tg.config.get('forge_name', 'this site')
            err_msg = "Please specify your affiliation with {}".format(name)
            self.fields.append(
                ew.TextArea(
                    label="Affiliation with {}".format(name),
                    name="affiliation",
                    min=2,
                    max=255,
                    messages={'empty': err_msg, 'missing': err_msg},
                    wide=True
                )
            )

        self.fields = [
            NameField(),
            ew.TextField(
                label="Email address",
                validator=EmailValidator(),
                name="email",
                wide=True,
            )
        ]
        if not asbool(tg.config.get('disable_captcha_validation', 'false')) \
                and tg.config.get('recaptcha_public_key'):
            self.fields.append(
                ReCaptchaField(
                    name="recaptcha",
                    label=False
                )
            )
            ignore_key_missing = True

        super(UserRegistrationEmailForm, self).__init__(
            ignore_key_missing=ignore_key_missing,
            **kwargs
        )

    @validator
    def validate(self, value, state=None):
        super(UserRegistrationEmailForm, self).validate(value, state)
        if self.ignore_key_missing and (not 'name' in value
                or not 'email' in value):
            raise Invalid('Missing Value', value, state)

        ea = EmailAddress.by_address(value['email'], confirmed=True)
        if ea:
            value.pop('recaptcha', None)
            raise Invalid("This email has been registered.", value, None)

        if not asbool(tg.config.get('disable_captcha_validation', 'false')) \
                and tg.config.get('recaptcha_public_key'):
            recaptcha_validator = ReCaptchaValidator()
            error = recaptcha_validator.validate(value)
            if error:
                raise Invalid(error, value, None)

        return value


class UserRegistrationForm(ForgeForm):
    submit_text = 'create account'
    style = 'wide'

    @property
    def fields(self):
        return [
            UsernameRegistrationField(
                name="username",
                label="Username",
                validator=UsernameValidator(),
                wide=True
            ),
            SetPasswordField(
                name="password",
                label="Password",
                validator=PasswordValidator(),
                wide=True
            ),
            ew.PasswordField(
                name="password_confirm",
                label="Confirm Password",
                wide=True
            ),
            ew.HiddenField(name="token")
        ]

    @validator
    def validate(self, value, state):
        super(UserRegistrationForm, self).validate(value, state)

        def raise_invalid(msg):
            raise Invalid(msg, dict(token=value['token']), None)

        token = UserRegistrationToken.query.get(nonce=value['token'])
        if not token or not token.is_valid:
            raise_invalid("Invalid token")
        if value['password'] != value['password_confirm']:
            raise_invalid("Passwords do not match!")

        return value


class UnnamedUserRegistrationForm(UserRegistrationForm):
    @property
    def fields(self):
        reg_fields = super(UnnamedUserRegistrationForm, self).fields
        reg_fields.insert(0, NameField())
        return reg_fields


class PasswordResetEmailForm(ForgeForm):
    submit_text = 'send reset link'
    style = 'wide'
    defaults = dict(
        ForgeForm.defaults,
        form_id="password_reset_email_form"
    )

    class fields(ew_core.NameList):
        email = ew.TextField(label="Email address",
                             validator=EmailValidator())

    @validator
    def validate(self, value, state=None):
        super(PasswordResetEmailForm, self).validate(value, state)
        user = User.by_email_address(value['email'])
        if user:
            min_hours = int(tg.config.get('auth.pw.min_lifetime.hours', 24))
            if user.password_set_at is None:
                now = datetime.utcnow()
                user.password_set_at = now - timedelta(hours=min_hours)
            age = datetime.utcnow() - user.password_set_at
            if age < timedelta(hours=min_hours):
                raise Invalid("Passwords may only be changed once "
                              "every {} hours".format(min_hours),
                              value, state)
        return value


class PasswordResetForm(ForgeForm):
    submit_text = 'save'
    style = 'wide'
    defaults = dict(
        ForgeForm.defaults,
        form_id="password_reset_form"
    )

    @property
    def fields(self):
        return [
            SetPasswordField(
                label="New Password",
                name="password",
                validator=PasswordValidator(),
                wide=True),
            ew.PasswordField(
                label="Confirm",
                name="password_confirm",
                wide=True),
            ew.HiddenField(name="token")
        ]

    @validator
    def validate(self, value, state):
        super(PasswordResetForm, self).validate(value, state)

        def raise_invalid(msg):
            raise Invalid(msg, dict(token=value['token']), None)

        token = PasswordResetToken.query.get(nonce=value['token'])
        if not token or not token.is_valid:
            raise_invalid("Invalid token")
        if value['password'] != value['password_confirm']:
            raise_invalid("Passwords do not match!")

        user = token.user

        min_hours = int(tg.config.get('auth.pw.min_lifetime.hours', 24))
        if user.password_set_at is None:
            now = datetime.utcnow()
            user.password_set_at = now - timedelta(hours=min_hours)
        age = datetime.utcnow() - user.password_set_at
        if age < timedelta(hours=min_hours):
            raise Invalid("Passwords may only be changed once "
                          "every {} hours".format(min_hours),
                          value, state)
        return value


class TwoFactorAuthenticationForm(ForgeForm):
    submit_text = "Change Setting"
    defaults = dict(
        ForgeForm.defaults,
        errors=None,
        show_errors=False,
        form_id="two_factor_auth_form"
    )

    @property
    def fields(self):
        return [
            ew.Checkbox(label='Use Two-Factor Authentication',
                        name='totp_auth')
        ]


class TwoFactorCredentialForm(ForgeForm):
    submit_text = "Change Key"

    defaults = dict(
        ForgeForm.defaults,
        errors=None,
        show_errors=False,
        form_id="two_factor_auth_key_form"
    )
