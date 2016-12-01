from formencode import validators as fev
from pylons import tmpl_context as c
import tg
import ew as ew_core
import ew.jinja2_ew as ew

from vulcanforge.common.widgets.forms import ForgeForm
from vulcanforge.common.widgets.form_fields import MarkdownEdit
from vulcanforge.resources.widgets import CSSLink, JSLink
from vulcanforge.project.validators import (
    ProjectNameValidator,
    AvailableShortnameValidator
)
from vulcanforge.project.widgets import ProjectUserSelect

TEMPLATE_DIR = 'jinja:vulcanforge:neighborhood/templates/widgets/'


class ToolSpecValidator(fev.StringBool):
    if_empty = False
    if_missing = False

    ep_name = None
    mount_point = None
    mount_label = None

    def __init__(self, *args, **kw):
        super(ToolSpecValidator, self).__init__(*args, **kw)
        if self.mount_point is None:
            self.mount_point = self.ep_name.lower()

    def _to_python(self, value, state=None):
        value = super(ToolSpecValidator, self)._to_python(value, state)
        if value:
            return self.ep_name, self.mount_point, self.mount_label
        else:
            return value


class NeighborhoodAddProjectForm(ForgeForm):
    template = TEMPLATE_DIR + 'add_project.html'
    defaults = dict(
        ForgeForm.defaults,
        method='post',
        submit_text='Start',
        neighborhood=None,
        base_url=None)
    TOOL_OPTIONS = [
        ('Wiki', 'Docs'),
        ('Tickets', 'Manage'),
        ('Downloads', 'Downloads'),
        ('Discussion', 'Forums')
    ]

    def __init__(self, *args, **kwargs):
        super(NeighborhoodAddProjectForm, self).__init__(*args, **kwargs)
        self._fields_dict = None

    @property
    def tool_fields(self):
        fields = []
        for name, label in self.TOOL_OPTIONS:
            fields.append(
                ew.Checkbox(
                    name=name, label=label, attrs={"class": "unlabeled"},
                    validator=ToolSpecValidator(
                        ep_name=name.lower(),
                        mount_label=label
                    )
                )
            )
        return fields

    @property
    def fields(self):
        field_list = [
            ew.HiddenField(
                label='Public Description', name='project_description'),
            ew.Checkbox(
                name='private_project',
                label="",
                attrs={'class': 'unlabeled'}),
            ew.InputField(
                name='project_name',
                label='Project Name',
                field_type='text',
                validator=ProjectNameValidator()),
            ew.InputField(
                name='project_unixname',
                label='Short Name',
                field_type='text',
                validator=AvailableShortnameValidator())
        ]
        field_list.extend(self.tool_fields)
        return ew_core.NameList(field_list)

    @property
    def fields_dict(self):
        if self._fields_dict is None:
            self._fields_dict = {f.name: f for f in self.fields}
        return self._fields_dict

    def resources(self):
        for r in super(NeighborhoodAddProjectForm, self).resources():
            yield r
        yield CSSLink('neighborhood/add_project.css')
        yield JSLink(
            'neighborhood/project_registration.js',
            scope='page'
        )

    def prepare_context(self, context):
        context = ForgeForm.prepare_context(self, context)
        if tg.config.get('base_url'):
            context['base_url'] = tg.config['base_url']
        return context


class NeighborhoodAdminOverview(ForgeForm):
    defaults = dict(
        ForgeForm.defaults,
        form_id="neighborhood_admin_form",
        enctype='multipart/form-data',
    )

    @property
    def fields(self):
        proj_label = c.neighborhood.project_cls.type_label
        fields = [
            ew.TextField(
                name="name",
                label="Name",
                validator=fev.String(non_empty=True),
                wide=True),
            ew.HTMLField(
                name="icon_img",
                wide=True),
            ew.FileField(
                name="icon",
                label="New Icon",
                wide=True),
            ew.Checkbox(
                name="allow_browse",
                label="Allow Browsing",
                wide=True),
            MarkdownEdit(
                name="homepage",
                label="Home Content (Markdown/HTML)",
                wide=True),
            ew.Checkbox(
                name="can_register_users",
                label="Allow User Registration",
                wide=True),
            ew.FieldSet(
                label='{} formation'.format(proj_label),
                wide=True,
                attrs={'class': "vf-fieldset"},
                fields=[
                    ew.Checkbox(
                        name="enable_marketplace",
                        label="Enable Marketplace",
                        wide=True),
                    ew.Checkbox(
                        name="project_registration_enabled",
                        label="Enable {} Formation".format(proj_label),
                        wide=True)
                ]
            ),
            ew.Checkbox(
                name="can_grant_anonymous",
                label="Allow projects to grant anonymous access",
                wide=True),
            ew.TextArea(
                name="project_template",
                label="{} Template".format(proj_label),
                wide=True),
            ew.Checkbox(
                name="moderate_deletion",
                label="Moderate Deletion",
                wide=True
            ),
            ProjectUserSelect(
                name="delete_moderator",
                label="Delete Moderator",
                wide=True
            )
        ]
        return fields
