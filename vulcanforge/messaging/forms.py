# -*- coding: utf-8 -*-

"""
messaging

@summary: messaging

@author: U{tannern<tannern@gmail.com>} 
"""
import ew as ew_core
import ew.jinja2_ew as ew
from formencode import validators as fev
from pylons import tmpl_context as c, app_globals as g

from vulcanforge.common.validators import ObjectIdValidator
from vulcanforge.common.widgets.forms import ForgeForm
from vulcanforge.auth.model import User
from vulcanforge.auth.validators import UsernameListValidator
from vulcanforge.project.model import ProjectRole


__all__ = ['StartConversationForm', 'MakeAnnouncementForm',
           'ConversationReplyForm']


class ConversationForm(ForgeForm):
    defaults = dict(
        ForgeForm.defaults,
        links=[
            {'label': 'cancel', 'href': '/dashboard/messages/'},
        ]
    )

    def _mk_role_entry(self, role):
        return ew.Option(
            label='{} {}'.format(role.project.name, role.name),
            html_value=str(role._id),
            py_value=role._id
        )

    def _mk_user_entry(self, user):
        return ew.Option(
            label='{} ({})'.format(user.display_name, user.username),
            html_value=str(user._id),
            py_value=user._id
        )

    def _filter_role(self, role):
        project = role.project
        return (
            not project.shortname.startswith('u/')
            and g.security.has_access(project, 'read')
        )

    def _available_recipient_users(self):
        user_cursor = User.query.find({
            'disabled': {'$in': [False, None]},
            'public': {'$in': [True, None]},
        })
        options = [self._mk_user_entry(u) for u in user_cursor if u.active()]
        options.sort(key=lambda x: x.label)
        return options

    def _available_recipient_roles(self):
        cache = g.security.RoleCache(
            g.security.credentials, c.user.get_roles())
        admin_roles = cache.reaching_roles.find(name='Admin')
        options = []
        for role in admin_roles:
            options.extend([self._mk_role_entry(r)
                            for r in role.project.named_roles
                            if self._filter_role(r)])
        options.sort(key=lambda x: x.label)
        return options

    def _available_sender_roles(self):
        cache = g.security.RoleCache(g.security.credentials, c.user.get_roles())
        roles = cache.reaching_roles.find(name='Admin')
        options = [self._mk_role_entry(r)
                   for r in roles
                   if self._filter_role(r)]
        options.sort(key=lambda x: x.label)
        return options


class StartConversationForm(ConversationForm):
    defaults = dict(
        ConversationForm.defaults,
        form_id="messageForm",
        form_name="messageForm",
        submit_text='send',
        action='do_start_conversation'
    )

    @property
    def fields(self):
        return ew_core.NameList([
            ew.InputField(
                label="recipients",
                name="recipients",
                css_class="recipients-field",
                wide=True,
                validator=UsernameListValidator(not_empty=True)
            ),
            ew.InputField(
                label="subject",
                name="subject",
                wide=True,
                validator=fev.UnicodeString(not_empty=True)
            ),
            ew.TextArea(
                label="message",
                name="text",
                wide=True,
                css_class="big-textarea",
                validator=fev.UnicodeString(not_empty=True)
            ),
        ])


class MakeAnnouncementForm(ConversationForm):
    defaults = dict(
        ConversationForm.defaults,
        form_id="messageForm",
        form_name="messageForm",
        submit_text='send',
        action='do_make_announcement'
    )

    @property
    def fields(self):
        return ew_core.NameList([
            ew.SingleSelectField(
                label="to role",
                name="to_role",
                wide=True,
                options=self._available_recipient_roles,
                validator=ObjectIdValidator(mapped_class=ProjectRole)
            ),
            ew.SingleSelectField(
                label="as role",
                name="as_role",
                wide=True,
                options=self._available_sender_roles,
                validator=ObjectIdValidator(mapped_class=ProjectRole)
            ),
            ew.InputField(
                label="subject",
                name="subject",
                wide=True,
                validator=fev.UnicodeString(not_empty=True)
            ),
            ew.TextArea(
                label="announcement",
                name="text",
                wide=True,
                css_class="big-textarea",
                validator=fev.UnicodeString(not_empty=True)),
            ew.Checkbox(
                label="allow comments",
                name="allow_comments",
                wide=True),
        ])


class AnnounceToAllForm(ConversationForm):
    defaults = dict(
        ConversationForm.defaults,
        form_id="messageForm",
        form_name="messageForm",
        submit_text="send",
        action="do_announce_to_all"
    )

    @property
    def fields(self):
        return ew_core.NameList([
            ew.SingleSelectField(
                label="as role",
                name="as_role",
                wide=True,
                options=self._available_sender_roles,
                validator=ObjectIdValidator(mapped_class=ProjectRole)
            ),
            ew.InputField(
                label="subject",
                name="subject",
                wide=True,
                validator=fev.UnicodeString(not_empty=True)
            ),
            ew.TextArea(
                label="announcement",
                name="text",
                wide=True,
                css_class="big-textarea",
                validator=fev.UnicodeString(not_empty=True)),
            ew.Checkbox(
                label="allow comments",
                name="allow_comments",
                wide=True),
        ])


class ConversationReplyForm(ForgeForm):
    defaults = dict(
        ForgeForm.defaults,
        form_id="respondForm",
        form_name="respondForm",
        submit_text='send',
        action='do_reply'
    )

    @property
    def fields(self):
        return ew_core.NameList([
            ew.TextArea(
                label="reply",
                name="text",
                wide=True,
                css_class="big-textarea",
                validator=fev.UnicodeString(not_empty=True)),
        ])
