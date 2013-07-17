# -*- coding: utf-8 -*-

"""
messaging

@summary: messaging

@author: U{tannern<tannern@gmail.com>}

# examples

## starting a conversation between users

>>> me = User.by_username('me')
>>> them = User.by_username('them')
>>> conversation = Conversation()
>>> conversation.add_user_id(me._id)
>>> conversation.add_user_id(them._id)
>>> conversation.add_message(me._id, "hi there!")

## make an announcement as a project

>>> project = Project.query.get(shortname="myproject")
>>> admin_role = ProjectRole.query.get(project_id=project._id, name='Admin')
>>> member_role = ProjectRole.query.get(project_id=project._id, name='Member')
>>> conversation = Conversation()
>>> conversation.is_announcement = True
>>> conversation.allow_comments = False
>>> conversation.add_role_id(member_role._id)
>>> conversation.add_message(me._id, "hi there again!", role_id=admin_role._id)
"""

from datetime import datetime

from pylons import tmpl_context as c, app_globals as g
import pymongo
from ming import schema
from ming.odm import session
from ming.odm.declarative import MappedClass
from ming.odm.property import (
    FieldProperty,
    RelationProperty,
    ForeignIdProperty
)

from vulcanforge.auth.model import User
from vulcanforge.auth.security_manager import RoleCache
from vulcanforge.common.model.session import main_orm_session
from vulcanforge.project.model import ProjectRole

__all__ = ["Conversation", "ConversationStatus", "ConversationMessage"]


class Conversation(MappedClass):
    """
    Conversations contain messages and control access to those messages
    """

    class __mongometa__:
        name = "messaging_conversation"
        session = main_orm_session
        indexes = [
            '_id',
            'user_ids',
            'role_ids',
            'updated_at',
        ]

    # fields
    _id = FieldProperty(schema.ObjectId)
    hidden = FieldProperty(schema.Bool, if_missing=False)
    updated_at = FieldProperty(datetime, if_missing=datetime.utcnow)
    subject = FieldProperty(schema.String, if_missing="No Subject")
    initiating_user_id = FieldProperty(schema.ObjectId,
                                       if_missing=lambda:c.user._id)
    user_ids = FieldProperty([schema.ObjectId])
    role_ids = FieldProperty([schema.ObjectId])
    is_announcement = FieldProperty(schema.Bool, if_missing=False)
    allow_comments = FieldProperty(schema.Bool, if_missing=True)

    @classmethod
    def by_user(cls, user, **kwargs):
        role_ids = user.get_role_ids()
        params = {
            '$or': [
                {'user_ids': {'$in': [user._id]}},
                {'role_ids': {'$in': role_ids}},
            ],
        }
        cursor = cls.query.find(params, **kwargs)
        cursor.sort('updated_at', pymongo.DESCENDING)
        return cursor

    def get_url(self):
        return '/dashboard/messages/{}'.format(self._id)

    def get_messages(self):
        params = {
            'conversation_id': self._id,
        }
        cursor = ConversationMessage.query.find(params)
        cursor.sort('pubdate', pymongo.ASCENDING)
        return cursor

    def get_message_count(self):
        params = {
            'conversation_id': self._id,
        }
        cursor = ConversationMessage.query.find(params)
        return cursor.count()

    def get_users(self):
        return User.query.find({
            '_id': {'$in': self.user_ids},
        })

    def get_latest_message(self):
        messages = self.get_messages()
        count = messages.count()
        if count > 0:
            return messages.all()[count - 1]
        return None

    def get_user_ids(self):
        user_ids = set(self.user_ids)
        role_cursor = ProjectRole.query.find({
            '_id': {'$in': self.role_ids},
        })
        for role in role_cursor:
            for user_role in role.users_with_role():
                user_ids.add(user_role.user._id)
        return list(user_ids)

    def get_status_for_user_id(self, user_id):
        params = {
            'user_id': user_id,
            'conversation_id': self._id,
        }
        status = ConversationStatus.query.get(**params)
        if status is None:
            status = ConversationStatus(**params)
            status.query.session.flush(status)
        return status

    def add_user_id(self, user_id):
        if user_id in self.user_ids:
            return
        self.user_ids.append(user_id)
        db = session(ConversationStatus).impl.bind.db
        coll = db[ConversationStatus.__mongometa__.name]
        coll.save({
            'user_id': user_id,
            'conversation_id': self._id,
        })

    def add_role_id(self, role_id):
        if role_id in self.role_ids:
            return
        self.role_ids.append(role_id)
        role = ProjectRole.query.find({'_id':role_id})
        cache = RoleCache(g.security.credentials, role)
        for user in cache.users_that_reach:
            if not user.active():
                continue
            self.add_user_id(user._id)

    def add_message(self, user_id, text, role_id=None,
                    unread_for_sender=False):
        now = datetime.utcnow()
        message_params = {
            'conversation_id': self._id,
            'user_id': user_id,
            'role_id': role_id,
            'text': text,
            'pubdate': now,
        }
        self.updated_at = now
        message = ConversationMessage(**message_params)
        message.query.session.flush_all()
        db = session(ConversationStatus).impl.bind.db
        coll = db[ConversationStatus.__mongometa__.name]
        update_spec = {
            'conversation_id': self._id
        }
        update_document = {
            '$set': {
                'unread': True,
                'updated_at': now,
            }
        }
        coll.update(update_spec, update_document, multi=True)
        user_ids = self.get_user_ids()
        recipient_ids = set(user_ids)
        try:
            recipient_ids.remove(user_id)
        except KeyError:
            pass
        self._send_emails_for_message(message, recipient_ids)
        return message

    def _send_emails_for_message(self, message, email_recipient_ids):
        from vulcanforge.notification.tasks import sendmail
        messages = self.get_messages()
        if messages.count() > 1:
            in_reply_to = str(messages.first()._id)
        else:
            in_reply_to = None
        subject = u"New message on vehicleFORGE: \"{}\"".format(
            message.get_summary_text())
        sender = g.forgemail_return_path
        email_text = (
            u"You have received a new message from {}:\n\n{}\n\n{}"
        ).format(
            message.author_info['name'],
            message.text,
            message.get_url()
        )
        recipient_ids = set()
        for user_id in email_recipient_ids:
            user = User.by_id(user_id)
            if user and user.get_pref('message_emails'):
                recipient_ids.add(user_id)
        sendmail.post(sender, list(recipient_ids), email_text,
                                 sender, subject, str(message._id),
                                 in_reply_to)


class ConversationStatus(MappedClass):

    class __mongometa__:
        name = "messaging_conversation"
        session = main_orm_session
        indexes = [
            '_id',
            'user_id',
            'conversation_id',
            ('user_id', 'unread'),
            ('user_id', 'conversation_id')
        ]

    # fields
    _id = FieldProperty(schema.ObjectId)
    updated_at = FieldProperty(datetime, if_missing=datetime.utcnow)
    conversation_id = ForeignIdProperty('Conversation')
    user_id = ForeignIdProperty('User')
    unread = FieldProperty(schema.Bool)
    # relations
    conversation = RelationProperty('Conversation')
    user = RelationProperty('User')

    @classmethod
    def unread_count_for_user_id(cls, user_id):
        return cls.query.find({
            'user_id': user_id,
            'unread': True,
        }).count()


class ConversationMessage(MappedClass):

    class __mongometa__:
        name = "messaging_message"
        session = main_orm_session
        indexes = [
            '_id',
            'conversation_id',
            'user_id',
            'role_id',
            'pubdate',
        ]

    # fields
    _id = FieldProperty(schema.ObjectId)
    hidden = FieldProperty(schema.Bool)
    pubdate = FieldProperty(datetime, if_missing=datetime.utcnow)
    conversation_id = ForeignIdProperty('Conversation')
    user_id = ForeignIdProperty('User')
    role_id = ForeignIdProperty('ProjectRole')
    text = FieldProperty(str, if_missing='')
    # relations
    conversation = RelationProperty('Conversation')
    user = RelationProperty('User')
    role = RelationProperty('ProjectRole')

    @property
    def author_info(self):
        if self.role_id is not None:
            role = self.role
            project = role.project
            return {
                'name': u"{} {}".format(project.name, role.name),
                'icon_url': project.icon_url,
                'url': project.url(),
            }
        else:
            user = self.user
            return {
                'name': u"{0.display_name} ({0.username})".format(user),
                'icon_url': user.icon_url(),
                'url': user.url(),
            }

    def get_url(self):
        return '/dashboard/messages/{}#message-{}'.format(
            self.conversation._id,
            self._id
        )

    def get_summary_text(self, summary_chars=80):
        if len(self.text) > summary_chars:
            return u"{}...".format(' '.join(self.text[:summary_chars].split()[:-1]))
        return self.text
