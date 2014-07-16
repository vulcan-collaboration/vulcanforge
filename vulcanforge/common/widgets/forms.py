import logging

from formencode import validators as fev
import formencode
from pylons import app_globals as g
import tg
import ew as ew_core
import ew.jinja2_ew as ew
import webhelpers

from vulcanforge.common.util.diff import levenshtein
from vulcanforge.common.widgets.form_fields import SetPasswordField
from vulcanforge.auth.validators import PasswordValidator


LOG = logging.getLogger(__name__)
SHORTNAME_PATTERN = '[A-z][-A-z0-9]{2,}'
TEMPLATE_DIR = 'jinja:vulcanforge:common/templates/form/'


class ForgeForm(ew.SimpleForm):
    antispam = False
    template = TEMPLATE_DIR + 'forge_form.html'
    defaults = dict(
        ew.SimpleForm.defaults,
        submit_text='Save',
        style='standard',
        method='post',
        enctype=None,
        form_id=None,
        form_control_box=True,
        form_name=None,
        is_lightbox=False,
        links=[])

    def __init__(self, ignore_key_missing=True, *args, **kwargs):
        super(ForgeForm, self).__init__(*args, **kwargs)
        self.ignore_key_missing = ignore_key_missing

    def _make_schema(self):
        schema = super(ForgeForm, self)._make_schema()
        schema.ignore_key_missing = self.ignore_key_missing
        return schema

    def display_label(self, field, label_text=None):
        ctx = self.context_for(field)
        label_text = (
            label_text
            or ctx.get('label')
            or getattr(field, 'label', None)
            or ctx['name'])
        html = '<label for="%s">%s</label>' % (
            ctx['id'], label_text)
        return webhelpers.html.literal(html)

    def context_for(self, field):
        ctx = super(ForgeForm, self).context_for(field)
        if self.antispam:
            ctx['rendered_name'] = g.antispam.enc(ctx['name'])
        return ctx

    def display_field(self, field, ignore_errors=False, **kw):
        ctx = self.context_for(field)
        ctx.update(kw)
        display = field.display(**ctx)
        if ctx['errors'] and field.show_errors and not ignore_errors:
            display = "%s<div class='error'>%s</div>" % (
                display, ctx['errors'])
        return webhelpers.html.literal(display)


class PasswordChangeForm(ForgeForm):
    defaults = dict(
        ForgeForm.defaults,
        form_id="passwordChange",
        form_name="passwordChange",
        submit_text='Set password'
    )

    class fields(ew_core.NameList):
        oldpw = ew.PasswordField(
            label='Old Password',
            validator=fev.UnicodeString(not_empty=True),
            wide=True)
        password = SetPasswordField(
            label='New Password',
            validator=PasswordValidator(),
            wide=True)
        password2 = ew.PasswordField(
            label='Confirm Password',
            validator=fev.UnicodeString(not_empty=True),
            wide=True)

    def display(self, requirements_hidden=False, **kw):

        self.fields['password'].requirements_hidden = requirements_hidden

        return super(PasswordChangeForm, self).display(
            **kw
        )

    @ew_core.core.validator
    def to_python(self, value, state):
        d = super(PasswordChangeForm, self).to_python(value, state)
        if d['password'] != d['password2']:
            raise formencode.Invalid('Passwords must match', value, state)
        min_levenshtein = int(tg.config.get('auth.pw.min_levenshtein', 0))
        if min_levenshtein > 0:
            lev = levenshtein(value['oldpw'], value['password'])
            if lev < min_levenshtein:
                raise formencode.Invalid("Too similar to a previous password",
                                         value, state)
        return d


class UploadKeyForm(ForgeForm):
    class fields(ew_core.NameList):
        key = ew.TextArea(label='SSH Public Key')


class AdminForm(ForgeForm):
    template = TEMPLATE_DIR + 'admin_form.html'



