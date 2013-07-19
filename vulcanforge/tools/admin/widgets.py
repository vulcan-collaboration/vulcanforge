from pylons import tmpl_context as c
from bson import ObjectId
import ew as ew_core
from ew import jinja2_ew as ew

from vulcanforge.common import validators as V
from vulcanforge.common.validators import HTMLEscapeValidator
from vulcanforge.common.widgets.forms import ForgeForm, AdminForm
from vulcanforge.common.widgets.form_fields import MarkdownEdit
from vulcanforge.project.model import ProjectRole
from vulcanforge.project.validators import ProjectNameValidator
from vulcanforge.project.widgets import ProjectIconField
from vulcanforge.resources.widgets import CSSScript, JSScript

TEMPLATE_DIR = 'jinja:vulcanforge.tools.admin:templates/admin_widgets/'


class CardField(ew._Jinja2Widget):
    template = TEMPLATE_DIR + 'card_field.html'
    defaults = dict(
        ew_core.Widget.defaults,
        id=None,
        name='Deck',
        icon_name='group',
        items=None,
        roles=[],
        settings_href=None)

    def item_display(self, item):
        return repr(item)

    def item_id(self, item):
        return repr(item)

    def resources(self):
        yield CSSScript('''
.deck li input, .deck li select {
    margin: 2px 0 2px 3px;
    width: 148px;
}
        ''')
        yield JSScript('''$(function() {
    $('.active-card').each(function() {
        var newitem = $('.new-item', this);
        var adder = $('.adder', this);
        var deleters = $('.deleter', this);
        newitem.remove();
        newitem.removeClass('new-item');
        deleters.click(function(evt) {
            evt.stopPropagation();
            evt.preventDefault();
            var $this = $(this);
            $this.closest('li').remove();
        });
        adder.click(function(evt) {
            evt.stopPropagation();
            evt.preventDefault();
            newitem.clone().insertBefore(adder.closest('li'));
        });
    });
});''')


class GroupCard(CardField):
    new_item = ew.InputField(
        field_type='text',
        css_class='username_autocomplete',
        attrs=dict(placeholder='type a username'))

    def item_display(self, item):
        return item.user.username

    def item_id(self, item):
        return item.user._id

    def role_name(self, role_id):
        return ProjectRole.query.get(_id=ObjectId(role_id)).display_name

    def resources(self):
        yield CSSScript('''.deck li input, .deck li select {
margin: 2px 0 2px 3px;
width: 148px;
}''')
        yield JSScript('''$(function() {
    $('.active-card').each(function() {
        var that = this;
        var newitem = $('.new-item', this);
        var adder = $('.adder', this);
        var deleters = $('.deleter', this);
        newitem.remove();
        newitem.removeClass('new-item');
        deleters.click(function(evt) {
            evt.stopPropagation();
            evt.preventDefault();
            var $this = $(this);
            $this.closest('li').remove();
        });
        adder.click(function(evt) {
            evt.stopPropagation();
            evt.preventDefault();
            newitem.clone().insertBefore(adder.closest('li'));
            $('.username_autocomplete', that).
                autocomplete({
                    source: function (request, callback) {
                        $.ajax({
                            url: '/autocomplete/user',
                            data: {q: request.term},
                            success: function (data, status, request) {
                                callback(data.results);
                            }
                        });
                    },
                    autoFocus: true
                });
        });
    });
});''')


class _GroupSelect(ew.SingleSelectField):
    def options(self):
        auth_role = ProjectRole.authenticated()
        anon_role = ProjectRole.anonymous()
        options = [
            ew.Option(py_value=role._id, label=role.display_name)
            for role in c.project.named_roles
        ]
        options.append(ew.Option(
            py_value=auth_role._id,
            label=auth_role.display_name))
        if c.project.shortname == "--init--" \
                or c.project.neighborhood.can_grant_anonymous:
            options.append(ew.Option(
                py_value=anon_role._id,
                label=anon_role.display_name))
        return options


class _RestrictedGroupSelect(ew.SingleSelectField):
    """Restricted to project read roles"""

    def options(self):
        options = [
            ew.Option(py_value=role._id, label=role.display_name)
            for role in c.project.get_expanded_read_roles()]
        return options


class PermissionCard(CardField):
    new_item = _GroupSelect()

    def item_display(self, role):
        return role.display_name

    def item_id(self, role):
        return role._id


class ToolPermissionCard(PermissionCard):
    new_item = _RestrictedGroupSelect()


class GroupSettings(ew.SimpleForm):
    submit_text = None

    class hidden_fields(ew_core.NameList):
        _id = ew.HiddenField(
            validator=V.MingValidator(ProjectRole))

    class fields(ew_core.NameList):
        name = ew.InputField(label='Name')

    class buttons(ew_core.NameList):
        save = ew.SubmitButton(label='Save')
        delete = ew.SubmitButton(label='Delete Group')


class NewGroupSettings(AdminForm):
    submit_text = 'Save'

    class fields(ew_core.NameList):
        name = ew.InputField(label='Name')


class ScreenshotAdmin(AdminForm):
    defaults = dict(
        AdminForm.defaults,
        enctype='multipart/form-data',
        form_id='admin_screenshot_form'
    )

    @property
    def fields(self):
        fields = [
            ew.InputField(
                name='screenshot',
                field_type='file',
                label='New Screenshot'),
            ew.InputField(
                name='caption',
                field_type="text",
                label='Caption')
        ]
        return fields


class ProjectOverviewForm(ForgeForm):
    defaults = dict(
        ForgeForm.defaults,
        delete_label="delete project",
        enctype='multipart/form-data')

    @property
    def fields(self):
        fields = [
            ew.TextField(
                name="name",
                label="Name",
                wide=True,
                validator=ProjectNameValidator()
            ),
            ew.TextField(
                name="shortname",
                label="Shortname (read only)",
                attrs={
                    'readonly': 'readonly',
                    'title': 'The shortname of a project cannot be changed',
                },
                wide=True
            ),
            ew.TextArea(
                name="short_description",
                label="summary",
                wide=True,
                attrs={
                    'cols': 30,
                    'rows': 10
                },
                validator=HTMLEscapeValidator()
            ),
            MarkdownEdit(
                name="description",
                label="Description",
                wide=True
            ),
            ew.FieldSet(
                label="Project Icon",
                fields=[
                    ProjectIconField(
                        name="icon",
                        label="Icon",
                        wide=True
                    ),
                    ew.Checkbox(
                        name="delete_icon",
                        label="Delete Icon",
                        wide=True
                    ),
                ],
                wide=True,
                attrs={
                    'class': 'vf-fieldset',
                }
            ),
            ew.FieldSet(
                label="Marketplace",
                fields=[
                    ew.TextArea(
                        name="ad_text",
                        label="Marketplace Advertisement",
                        wide=True,
                        attrs={
                            'maxlength': 255,
                            'cols': 30,
                            'rows': 10
                        },
                        validator=HTMLEscapeValidator()
                    ),
                    ew.Checkbox(
                        name="unpublish_ad",
                        label="Remove Published Advertisement",
                        wide=True
                    ),
                ],
                wide=True,
                attrs={
                    'class': 'vf-fieldset',
                }
            ),
        ]
        perils = []
        if c.project.deleted:
            perils.append(
                ew.Checkbox(
                    name="undelete",
                    label="Un{}".format(self.delete_label),
                    wide=True
                )
            )
        else:
            perils.append(
                ew.Checkbox(
                    name="delete",
                    label=self.delete_label.capitalize(),
                    wide=True
                )
            )
        if len(perils):
            fields.append(ew.FieldSet(
                label="Region of Great Peril",
                fields=perils,
                wide=True,
                attrs={
                    'class': "vf-fieldset perilous",
                }
            ))
        return fields


class ProjectMemberAgreementForm(ForgeForm):
    defaults = dict(ForgeForm.defaults, enctype='multipart/form-data')

    class fields(ew_core.NameList):
        member_agreement_html = ew.HTMLField(wide=True)
        member_agreement = ew.FileField(label="Upload New")
        delete_member_agreement = ew.Checkbox(label="Delete Current Plan")
