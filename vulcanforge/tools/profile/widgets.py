# -*- coding: utf-8 -*-
import logging

from paste.deploy.converters import asbool
from tg import config
from ew import jinja2_ew

from vulcanforge.common.widgets.forms import ForgeForm

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
                        name="display_name"
                    ),
                    jinja2_ew.TextField(
                        label="Organization",
                        name="company"
                    ),
                    jinja2_ew.TextField(
                        label="Position",
                        name="position"
                    ),
                    jinja2_ew.TextField(
                        label="Telephone",
                        name="telephone"
                    )
                ],
                wide=True,
                attrs={'class': 'vf-fieldset'}
            ),
            jinja2_ew.FieldSet(
                label='Additional Info',
                fields=[
                    jinja2_ew.TextArea(
                        label="Your Mission",
                        name="mission",
                        attrs={'maxlength': 512, 'cols': 80, 'rows': 3, 'style': "width:500px"}
                    ),
                    jinja2_ew.TextArea(
                        label="Your Interests",
                        name="interests",
                        attrs={'maxlength': 512, 'cols': 80, 'rows': 3, 'style': "width:500px"}
                    ),
                    jinja2_ew.TextArea(
                        label="Your Expertise",
                        name="expertise",
                        attrs={'maxlength': 512, 'cols': 80, 'rows': 3, 'style': "width:500px"}
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
