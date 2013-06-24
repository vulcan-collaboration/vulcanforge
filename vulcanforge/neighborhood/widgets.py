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
    ProjectShortnameValidator
)
from vulcanforge.project.widgets import ProjectUserSelect

TEMPLATE_DIR = 'jinja:vulcanforge:neighborhood/templates/widgets/'


class NeighborhoodAddProjectForm(ForgeForm):
    template = TEMPLATE_DIR + 'add_project.html'
    antispam = True
    defaults = dict(
        ForgeForm.defaults,
        method='post',
        submit_text='Start',
        neighborhood=None,
        base_url=None)

    class fields(ew_core.NameList):
        project_description = ew.HiddenField(label='Public Description')
        private_project = ew.Checkbox(label="", attrs={'class': 'unlabeled'})
        project_name = ew.InputField(
            label='Project Name',
            field_type='text',
            validator=ProjectNameValidator())
        project_unixname = ew.InputField(
            label='Short Name',
            field_type='text',
            validator=ProjectShortnameValidator()
        )
        Wiki = ew.Checkbox(label="Docs", attrs={'class': 'unlabeled'})
        Git = ew.Checkbox(label="Git", attrs={'class': 'labeled scm'})
        SVN = ew.Checkbox(label="Subversion", attrs={'class': 'labeled scm'})
        Tickets = ew.Checkbox(label="Manage", attrs={'class': 'unlabeled'})
        Downloads = ew.Checkbox(
            label="Downloads",
            attrs={'class': 'unlabeled'}
        )
        Discussion = ew.Checkbox(label="Forums", attrs={'class': 'unlabeled'})

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