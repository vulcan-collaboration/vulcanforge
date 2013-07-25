# -*- coding: utf-8 -*-
import logging

from formencode import validators
from paste.deploy.converters import asbool
from tg import config
from ew import jinja2_ew

from vulcanforge.common.widgets.forms import ForgeForm
from vulcanforge.common.validators import HTMLEscapeValidator

LOG = logging.getLogger(__name__)


class EditProfileForm(ForgeForm):

    #template = 'jinja:vulcanforge.tools.profile:templates/widgets/edit_profile_form.html'
    submit_text = 'Update Profile'
    style = 'wide'
    defaults = dict(
        ForgeForm.defaults,
        form_id='edit_profile_form',
        enctype='multipart/form-data'
    )

    @property
    def fields(self):
        fields = [
            jinja2_ew.FieldSet(
                label="Avatar",
                fields=[
                    jinja2_ew.FileField(
                        label="Avatar",
                        name="avatar"
                    ),
                    jinja2_ew.Checkbox(
                        label="Remove Avatar",
                        name="remove_avatar"
                    )
                ],
                wide=True,
                attrs={'class': 'vf-fieldset'}
            ),
            jinja2_ew.FieldSet(
                label='Profile Info',
                fields=[
                    jinja2_ew.TextField(
                        label="Display Name",
                        name="display_name",
                        validator=HTMLEscapeValidator(max=255)
                    ),
                    jinja2_ew.TextArea(
                        label="Your Mission",
                        name="mission",
                        attrs={'maxlength': 37, 'cols': 30, 'rows': 3},
                        validator=HTMLEscapeValidator(max=255)
                    ),
                    jinja2_ew.TextArea(
                        label="Your Interests",
                        name="interests",
                        attrs={'maxlength': 37, 'cols': 30, 'rows': 3},
                        validator=HTMLEscapeValidator(max=255)
                    ),
                    jinja2_ew.TextArea(
                        label="Your Expertise",
                        name="expertise",
                        attrs={'maxlength': 37, 'cols': 30, 'rows': 3},
                        validator=HTMLEscapeValidator(max=255)
                    )
                ],
                wide=True,
                attrs={'class': 'vf-fieldset'}
            ),
            jinja2_ew.FieldSet(
                label='Marketplace Advertisement',
                fields=[
                    jinja2_ew.TextArea(
                        label="Marketplace Advertisement",
                        name='user_ad',
                        note="Add yourself to the marketplace listings. Plain "
                             "text only.",
                        attrs={
                            'maxlength': 255,
                            'cols': 30,
                            'rows': 10
                        },
                        validator=HTMLEscapeValidator(max=255)
                    ),
                    jinja2_ew.Checkbox(
                        label="Remove Advertisement",
                        name="remove_ad"
                    )
                ],
                wide=True,
                attrs={'class': 'vf-fieldset'}
            ),
            jinja2_ew.FieldSet(
                label='For Internal Use Only',
                fields=[
                    jinja2_ew.TextField(
                        label="Skype Name (for VCDE tool only)",
                        name="skype_name",
                        note="For use in VCDE tool",
                        validator=HTMLEscapeValidator(max=255)
                    )
                ],
                wide=True,
                attrs={'class': 'vf-fieldset'}
            )
        ]
        if not asbool(config.get('all_users_public', 'false')):
            fields.append(
                jinja2_ew.Checkbox(
                    label="Make Profile Public", name="public")
            )
        return fields
