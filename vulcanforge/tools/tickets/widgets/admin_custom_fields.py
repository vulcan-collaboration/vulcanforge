import shlex
import ew as ew_core
import ew.jinja2_ew as ew
from formencode import Invalid

from vulcanforge.common.widgets import form_fields, forms
from vulcanforge.resources.widgets import JSLink, CSSScript

TEMPLATE_FOLDER = 'jinja:vulcanforge.tools.tickets:templates/tracker_widgets/'


class MilestonesAdmin(form_fields.SortableTable):
    defaults = dict(
        form_fields.SortableTable.defaults,
        button=form_fields.AdminField(
            field=ew.InputField(
                css_class='add', field_type='button', value='New Milestone')),
        empty_msg='No milestones have been created.',
        nonempty_msg='Drag and drop the milestones to reorder.',
        repetitions=0)
    fields = [
        ew.Checkbox(
            name='complete',
            show_label=True,
            suppress_label=True),
        ew.TextField(
            name='name',
            attrs={'style': 'width: 80px'}),
        form_fields.DateField(
            name='due_date',
            attrs={'style': 'width: 80px'}),
        ew.TextArea(
            name='description',
            attrs={'style': 'height:1.5em; width: 100px'}),
        ew.InputField(
            label='Delete',
            field_type='button',
            attrs={'class': 'delete', 'value': 'Delete'}),
    ]
    button = ew.InputField(
        css_class='add',
        field_type='button',
        value='New Milestone')

    def resources(self):
        for r in super(MilestonesAdmin, self).resources():
            yield r
        yield CSSScript('''div.state-field table{ width: 700px; }''')


class CustomFieldAdminDetail(form_fields.StateField):
    template = TEMPLATE_FOLDER + 'custom_field_admin_detail.html'
    defaults = dict(
        form_fields.StateField.defaults,
        selector=form_fields.AdminField(field=ew.SingleSelectField(
            name='type',
            options=[
                ew.Option(py_value='string', label='Text'),
                ew.Option(py_value='markdown', label='Markdown'),
                ew.Option(py_value='number', label='Number'),
                ew.Option(py_value='boolean', label='Boolean'),
                ew.Option(py_value='select', label='Select'),
                ew.Option(py_value='milestone', label='Milestone'),
            ],
        )),
        states=dict(
            select=form_fields.FieldCluster(
                fields=[
                    form_fields.AdminField(field=ew.TextField(name='options'))
                ],
                show_labels=False),
            milestone=form_fields.FieldCluster(
                # name='milestones',
                fields=[MilestonesAdmin(name='milestones')])
        ))


class CustomFieldAdmin(ew.CompoundField):
    template = TEMPLATE_FOLDER + 'custom_field_admin.html'

    def resources(self):
        for r in super(CustomFieldAdmin, self).resources():
            yield r
        yield JSLink('tickets/js/custom-fields.js')

    fields = [
        ew.TextField(name='label'),
        ew.Checkbox(
            name='show_in_search',
            label='Show in search',
            show_label=True,
            suppress_label=True),
        ew.Checkbox(
            name='required',
            label='Required',
            show_label=True,
            suppress_label=True),
        CustomFieldAdminDetail()]

    def to_python(self, value, state=None):
        value = super(CustomFieldAdmin, self).to_python(value, state)
        if value.get('type') == 'select':
            try:
                shlex.split(value.get('options', ''))
            except ValueError, e:
                raise Invalid(str(e), value, state)
        return value


class TrackerFieldAdmin(forms.ForgeForm):
    submit_text = None
    fields = ew_core.NameList([
        ew.FieldSet(
            label="Status",
            fields=ew_core.NameList([
                ew.TextField(
                    name='open_status_names',
                    label='Open Statuses',
                    wide=True),
                ew.TextField(
                    name='closed_status_names',
                    label='Closed Statuses',
                    wide=True),
            ]),
            wide=True
        ),
        ew.FieldSet(
            label="Default Fields",
            fields=ew_core.NameList([
                ew.TextField(
                    name='protected_field_names',
                    label='Protected Fields',
                    wide=True),
                ew.Checkbox(
                    name='show_assigned_to',
                    label='Show Assigned to Field',
                    wide=True),
                ew.TextField(
                    name='assigned_to_label',
                    label='Custom label for Assigned to Field',
                    wide=True),
                ew.Checkbox(
                    name='show_description',
                    label='Show Description Field',
                    wide=True),
                ew.TextField(
                    name='description_label',
                    label='Custom Label for Description Field',
                    wide=True),
            ]),
            wide=True
        ),
        form_fields.SortableRepeatedField(
            name='custom_fields',
            field=CustomFieldAdmin(),
            wide=True,
            show_label=False)
    ])

    class buttons(ew_core.NameList):
        save = ew.SubmitButton(label='Save')
        cancel = ew.SubmitButton(
            label="Cancel",
            css_class='cancel', attrs=dict(
                onclick='window.location.reload(); return false;'))

    def resources(self):
        for rr in self.fields['custom_fields'].resources():
            yield rr


class CustomFieldDisplay(ew.CompoundField):
    template = TEMPLATE_FOLDER + 'custom_field_display.html'


class CustomFieldsDisplay(ew.RepeatedField):
    template = TEMPLATE_FOLDER + 'custom_fields_display.html'


class TrackerFieldDisplay(forms.ForgeForm):
    class fields(ew_core.NameList):
        milestone_names = ew.TextField()
        open_status_names = ew.TextField(label='Open Statuses')
        closed_status_names = ew.TextField(label='Open Statuses')
        custom_fields = CustomFieldsDisplay()

    def resources(self):
        for rr in self.fields['custom_fields'].resources():
            yield rr
