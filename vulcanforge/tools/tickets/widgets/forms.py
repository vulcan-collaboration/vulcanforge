# -*- coding: utf-8 -*-

"""
forms

@summary: forms

@author: U{tannern<tannern@gmail.com>}
"""
import logging
import shlex

import formencode.validators as fev
from pylons import tmpl_context as c
import ew as ew_core
import ew.jinja2_ew as ew
from vulcanforge.auth.validators import UsernameListValidator

from vulcanforge.common.widgets import form_fields
from vulcanforge.common.widgets.forms import ForgeForm
from vulcanforge.project.widgets import MultiProjectUserSelect

LOG = logging.getLogger(__name__)
TEMPLATE_FOLDER = 'jinja:vulcanforge.tools.tickets:templates/tracker_widgets/'


class TicketCustomFields(ew.CompoundField):
    template = TEMPLATE_FOLDER + 'ticket_custom_fields.html'

    @property
    def fields(self):
        return ew_core.NameList([TicketCustomField.make(cf)
                                 for cf in c.app.globals.custom_fields
                                 if c.app.globals.can_edit_field(cf.name)
                                 and cf.type != 'markdown'])


class TicketMarkdownFields(ew.CompoundField):
    template = TEMPLATE_FOLDER + 'ticket_custom_fields.html'

    @property
    def fields(self):
        return ew_core.NameList([TicketCustomField.make(cf)
                                 for cf in c.app.globals.custom_fields
                                 if c.app.globals.can_edit_field(cf.name)
                                 and cf.type == 'markdown'])


class TicketCustomField(object):

    @staticmethod
    def _select(field):
        options = []
        for opt in shlex.split(field.options):
            selected = False
            if opt.startswith('*'):
                opt = opt[1:]
                selected = True
            options.append(
                ew.Option(label=opt, html_value=opt, py_value=opt,
                          selected=selected))
        return ew.SingleSelectField(label=field.label,
                                    name=str(field.name),
                                    options=options)

    @staticmethod
    def _milestone(field):
        options = []
        for m in field.milestones:
            if not m.complete:
                options.append(ew.Option(
                        label=m.name,
                        py_value=m.name))
        ssf = ew.SingleSelectField(
            label=field.label, name=str(field.name),
            options=options)
        return ssf

    @staticmethod
    def _boolean(field):
        return ew.Checkbox(label=field.label, name=str(field.name))

    @staticmethod
    def _number(field):
        return ew.NumberField(label=field.label, name=str(field.name))

    @staticmethod
    def _markdown(field):
        return form_fields.MarkdownEdit(
            label=field.label, name=str(field.name), wide=True)

    @staticmethod
    def _default(field):
        return ew.TextField(label=field.label, name=str(field.name))

    @classmethod
    def make(cls, field):
        field_type = field.get('type')
        factory = getattr(cls, '_{}'.format(field_type), cls._default)
        return factory(field)


class TrackerTicketForm(ForgeForm):

    defaults = dict(
        ForgeForm.defaults,
        enctype='multipart/form-data',
        form_id='ticket_form',
        attachment_context_id=None
    )

    def __init__(self, comment=False, *args, **kw):
        self.comment = comment
        super(TrackerTicketForm, self).__init__(*args, **kw)

    @property
    def fields(self):
        raw_fields = [
            ew.HiddenField(
                name="ticket_num",
                validator=fev.Int(if_missing=None),
            ),
            ew.HiddenField(
                name="super_id",
                validator=fev.UnicodeString(if_missing=None),
            ),
            ew.TextField(
                name="summary",
                label='Summary',
                attrs={
                    'class': 'ticket-summary'
                },
                validator=fev.UnicodeString(
                    not_empty=True,
                    messages={'empty': "You must provide a Summary"},
                )
            )
        ]
        if c.app.globals.show_assigned_to:
            raw_fields.append(
                MultiProjectUserSelect(
                    name='assigned_to',
                    label=c.app.globals.assigned_to_label,
                    validator=UsernameListValidator()
                )
            )
        raw_fields.extend([
            ew.SingleSelectField(
                name="status",
                label='Status',
                options=lambda: c.app.globals.all_status_names.split(),
            ),
            TicketCustomFields(
                label="",
                name="custom_fields",
            ),
            form_fields.LabelEdit(
                name="labels",
                label='Labels',
                className='ticket_form_tags',
                wide=True
            ),
            ew.Checkbox(
                name="private",
                label='Make Issue Private',
                attrs={'class': 'mark-as-private-checkbox'},
            )
        ])
        if c.app.globals.show_description:
            raw_fields.append(
                form_fields.MarkdownEdit(
                    name="description",
                    label=c.app.globals.description_label,
                    attrs={'class': 'ticket-description'},
                    wide=True,
                )
            )
        else:
            raw_fields.append(None)
        raw_fields.extend([
            TicketMarkdownFields(
                label="",
                name="markdown_custom_fields",
            ),
            form_fields.RepeatedAttachmentField(
                name="new_attachments",
                label="Attach Files",
                wide=True,
            )
        ])
        if self.comment:
            raw_fields.append(form_fields.MarkdownEdit(
                name="comment",
                label="Comment",
                wide=True,
            ))
            # TODO: allow separate attachments for comment
            #   why this isn't done:
            #       Did not behave as expected when simply adding separate
            #       comment_attachments RepeatedAttachmentField

        def filter_check(item):
            return item is not None and c.app.globals.can_edit_field(item.name)

        return filter(filter_check, raw_fields)

    def context_for(self, field):
        ctx = super(TrackerTicketForm, self).context_for(field)
        if isinstance(field, form_fields.MarkdownEdit) or \
                isinstance(field, TicketMarkdownFields):
            w_ctx = ew_core.widget_context
            ctx['attachment_context_id'] = w_ctx.render_context.get(
                'attachment_context_id')
            if field.name.startswith('markdown_custom_fields'):
                value = w_ctx.render_context.get('value')
                if value:
                    ctx['value'] = getattr(value, 'custom_fields', {})
        return ctx
