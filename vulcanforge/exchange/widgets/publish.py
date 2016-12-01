import logging
from itertools import chain

from formencode.validators import String, StringBool
from pylons import app_globals as g, tmpl_context as c
from ew import jinja2_ew

from vulcanforge.common.validators import ObjectIdValidator, CommaSeparatedEach
from vulcanforge.common.widgets.forms import ForgeForm
from vulcanforge.resources.widgets import CSSLink, JSLink
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.widgets import MultiProjectSelect

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.exchange:templates/widgets/'


class PermissiveSingleSelectField(jinja2_ew.SingleSelectField):
    def _make_schema(self):
        return self.validator


class ShareWithField(jinja2_ew.CompoundField):
    defaults = dict(
        jinja2_ew.CompoundField.defaults,
        show_label=False,
        share_label='Share With')
    template = TEMPLATE_DIR + 'share_with_field.html'

    def resources(self):
        for r in super(ShareWithField, self).resources():
            yield r
        yield JSLink('exchange/js/publish_form.js')

    @property
    def scope_options(self):
        return [
            jinja2_ew.Option(py_value='public', label='Everyone'),
            #jinja2_ew.Option(py_value='neighborhood',
            #                 label='Neighborhood(s)...'),
            jinja2_ew.Option(py_value='project', label='Team(s)...')
        ]

    @property
    def fields(self):
        nbhd_opts = [
            jinja2_ew.Option(py_value=str(n._id), label=n.name)
            for n in Neighborhood.query.find() if not n.is_user_neighboorhood()
            and g.security.has_access(n, 'read')
        ]
        return [
            jinja2_ew.SingleSelectField(
                name="scope",
                show_label=False,
                options=self.scope_options
            ),
            jinja2_ew.FieldSet(
                attrs={"id": 'publish-acl-dependents'},
                fields=[
#                    jinja2_ew.MultiSelectField(
#                        name="share_neighborhoods",
#                        show_label=False,
#                        options=nbhd_opts,
#                        validator=ObjectIdValidator
#                    ),
                    MultiProjectSelect(name="share_projects", show_label=False)
                ]
            )
        ]


class ArtifactPublishForm(ForgeForm):
    submit_text = 'Share'
    style = "wide"
    defaults = dict(
        ForgeForm.defaults,
        form_id="artifact-publish-form"
    )

    def resources(self):
        for r in super(ArtifactPublishForm, self).resources():
            yield r
        yield CSSLink('exchange/css/publish_form.css')

    @property
    def _replace_fields(self):
        return [
            jinja2_ew.Checkbox(
                name="replace_existing",
                label="Update Existing Exchange Node",
                suppress_label=False),
            PermissiveSingleSelectField(
                name="replace_node",
                show_label=False,
                options=[
                    jinja2_ew.Option(
                        py_value=str(node._id),
                        label=node.title + ' @ ' + node.revision)
                    for node in getattr(c, "replaceable_nodes", [])
                ],
                validator=ObjectIdValidator()
            )
        ]

    def _all_fields(self):
        return chain(super(ArtifactPublishForm, self)._all_fields(),
                     self._replace_fields)

    @property
    def publish_detail_fields(self):
        fields = []
        if getattr(c, 'replaceable_nodes', None):
            fields.extend(self._replace_fields)
        fields.extend([
            jinja2_ew.InputField(
                name="title",
                label="Title",
                show_label=True,
            ),
            jinja2_ew.InputField(
                name="revision",
                label="Revision",
                css_class="short",
                show_label=True,
            ),
            jinja2_ew.TextArea(
                name="change_log",
                label="Publish Log",
                attrs={'maxlength': 256, 'cols': 40, 'rows': 3},
                show_label=True,
            )
        ])
        return fields

    @property
    def scope_fields(self):
        return [ShareWithField()]

    @property
    def fields(self):
        fields = [
            jinja2_ew.FieldSet(
                label="Share Scope",
                fields=self.scope_fields,
                wide=True,
                attrs={'class': 'vf-fieldset'}
            ),
            jinja2_ew.FieldSet(
                label="Share Details",
                fields=self.publish_detail_fields,
                wide=True,
                attrs={'class': 'vf-fieldset'}
            ),
            jinja2_ew.HiddenField(
                name="artifact_id",
                validator=ObjectIdValidator()
            )
        ]
        return fields

    def prepare_context(self, context):
        context['links'] = []
        ctx = super(ArtifactPublishForm, self).prepare_context(context)
        if 'artifact' in ctx:
            ctx['links'].append({
                "href": ctx["artifact"].url(),
                "label": "Cancel",
                "css_class": "btn"
            })
        return ctx
