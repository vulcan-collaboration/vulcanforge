# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from paste.deploy.converters import asbool
import tg
from tg import config
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


class UserRegistrationEmailForm(ForgeForm):
    submit_text = 'request email with activation link'
    style = 'wide'

    def __init__(self, affiliate=False, ignore_key_missing=False, **kwargs):
        super(UserRegistrationEmailForm, self).__init__(
            ignore_key_missing=ignore_key_missing,
            **kwargs
        )
        self.fields = [
            ew.TextField(
                label="Name",
                name="name",
                validator=UnicodeString(
                    min=2,
                    max=255,
                    messages={
                        'empty': "Please specify a display name",
                        'missing': "Please specify a display name"
                    }
                ),
                wide=True
            ),
            ew.TextField(
                label="Email address",
                validator=EmailValidator(),
                name="email",
                wide=True,
            )
        ]
        if not asbool(tg.config.get('disable_captcha_validation', 'false')):
            self.fields.append(
                ReCaptchaField(
                    name="recaptcha",
                    label=False
                )
            )

    @validator
    def validate(self, value, state=None):
        super(UserRegistrationEmailForm, self).validate(value, state)

        if asbool(config.get('is_itar', 'false')):
            if not value.get("verify_citizen"):
                raise Invalid("You must be a U.S. person to participate",
                    value, state)
            if not value.get("itar_agree"):
                raise Invalid(
                    ("You must certify that you understand that there may be "
                     "a potential to come into contact with ITAR controlled "
                     "data"),
                    value, state)
        ea = EmailAddress.by_address(value['email'], confirmed=True)
        if ea:
            value.pop('recaptcha', None)
            raise Invalid("This email has been registered.", value, None)

        if not asbool(tg.config.get('disable_captcha_validation', 'false')):
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

        user = User.by_username(value['username'])
        if user:
            raise_invalid("Username already taken!")

        return value


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
        if not user:
            raise Invalid(
                "This email address has not been claimed by any user.",
                dict(token=value['email']), None
            )
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
