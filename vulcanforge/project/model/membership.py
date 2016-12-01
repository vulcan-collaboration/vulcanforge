import logging
import hashlib
import os
from datetime import datetime, timedelta

from ming.odm.odmsession import session
from ming.odm import FieldProperty, ForeignIdProperty
from ming import schema as S
from paste.deploy.converters import asint
from pylons import tmpl_context as c, app_globals as g
import tg

from vulcanforge.common.model.session import main_orm_session
from vulcanforge.auth.model import UserRegistrationToken, UsersDenied
from vulcanforge.artifact.model import Artifact
from vulcanforge.common.util.model import VFRelationProperty
from vulcanforge.notification.model import Notification
from vulcanforge.notification.util import gen_message_id
from vulcanforge.notification.tasks import sendmail
from vulcanforge.messaging.model import Conversation

LOG = logging.getLogger(__name__)

REQUEST_NOTIFICATION = u"""
A new user has requested membership to your project:

Name: {}
Email: {}
Profile: {}

To accept/deny this user, go to the membership administration section of your
project here: {}
"""

CANCEL_NOTIFICATION = u"""
The following user has requested to leave your project:

Name: {}
Email: {}
Profile: {}

To grant this user leave, go to the membership administration section of your
project here: {}
"""

REMOVAL_NOTIFICATION = u"""
{initiator_name} has requested the withdrawal of {recipient_name} from
{project_name}.
"""

REMOVAL_CONVERSATION = u"""
{initiator_name} has requested your withdrawal from {project_name}.

To accept and withdraw from {project_name}, visit {project_url} and click on
the "Accept Withdrawal" button at the top of the page.
"""

INVITATION_NOTIFICATION = u"""
The following user has been invited to join the project:

{}
Email: {}
{}
"""

INVITATION_EMAIL = u"""
{text}

You may accept this invitation by {means} {url}
"""

REGISTRATION_NOTIFICATION = u"""
A new user has requested access to the FORGE.

You may manage this request through your custom built administrative
interface*: {}

Name: {},
Email: {},
{}

*provided by Vanderbilt ISIS
"""


class RegistrationRequest(Artifact):

    class __mongometa__:
        name = 'registration_request'
        indexes = ['project_id']

    project_id = ForeignIdProperty('Project')
    name = FieldProperty(str)
    email = FieldProperty(str)
    user_fields = FieldProperty({str: None})
    status = FieldProperty(
        S.OneOf('tbd', 'denied', 'accepted', if_missing='tbd')
    )
    auto_add_to_project = FieldProperty(bool, if_missing=False)
    registration_url = FieldProperty(str, if_missing=None)
    resolution_actor = FieldProperty(str, if_missing=None)
    resolution_ts = FieldProperty(S.DateTime, if_missing=None)

    summary = "New User Registration Request"

    def index(self, **kw):
        return None

    def url(self):
        return self.app_config.url()

    def notify(self):
        Notification.post(
            artifact=self,
            topic="registration",
            text=self.notification_text,
            subject=self.summary
        )

    @property
    def notification_text(self):
        return REGISTRATION_NOTIFICATION.format(
            g.url(self.app_config.url() + u'registration'),
            self.name,
            self.email,
            u'\n'.join(
                u'{}: {}'.format(k, v) for k, v in self.user_fields.iteritems()
            )
        )

    def accept(self, actor=None):
        token = UserRegistrationToken(
            name=self.name,
            email=self.email,
            nonce=hashlib.sha256(os.urandom(10)).hexdigest(),
            user_fields=self.user_fields,
            registration_url=self.registration_url,
            expiry_date=datetime.utcnow() + timedelta(hours=48)
        )
        # Add the user to the project automatically. This is designed
        # for moderated competitions.
        if self.auto_add_to_project:
            token.project_id = c.project._id
        token.send()
        self.status = "accepted"
        self.resolution_actor = actor or c.user.username
        self.resolution_ts = datetime.utcnow()

    def deny(self, actor=None):
        self.status = "denied"
        self.resolution_actor = actor or c.user.username
        self.resolution_ts = datetime.utcnow()
        UsersDenied(email=self.email)

class AbstractRequestArtifact(Artifact):

    _id = FieldProperty(S.ObjectId)
    project_id = ForeignIdProperty('Project', if_missing=lambda: c.project._id)
    user_id = ForeignIdProperty('User', if_missing=lambda: c.user._id)
    text = FieldProperty(str)

    project = VFRelationProperty('Project')
    user = VFRelationProperty('User', via="user_id")

    def index(self, **kw):
        return dict(
            title_s=self.notification_subject
        )

    @property
    def notification_subject(self):
        return ''

    @property
    def notification_text(self):
        return ''

    def notify(self):
        return Notification.post(
            artifact=self,
            topic='membership',
            text=self.notification_text,
            subject=self.notification_subject
        )

    def url(self):
        return self.app_config.url()

    @classmethod
    def upsert(cls, user=None, project=None, text='', **kw):
        if user is None:
            user = c.user
        if project is None:
            project = c.project
        req = cls.query.get(user_id=user._id, project_id=project._id)
        if req is None:
            req = cls(
                user_id=user._id,
                project_id=project._id,
                **kw
            )
            session(cls).flush(req)
            req.notify()
        req.text = text
        return req


class MembershipRequest(AbstractRequestArtifact):

    class __mongometa__:
        session = main_orm_session
        name = 'membership_request'
        indexes = ['project_id', 'user_id']

    @property
    def notification_subject(self):
        return u'Membership Request from {}'.format(self.user.display_name)

    @property
    def notification_text(self):
        return REQUEST_NOTIFICATION.format(
            self.user.display_name,
            self.user.get_email_address(),
            g.url(self.user.url() + 'profile'),
            g.url(self.app_config.url() + 'members')
        )


class MembershipCancelRequest(AbstractRequestArtifact):

    class __mongometa__:
        session = main_orm_session
        name = "membership_cancel_request"
        indexes = ['project_id', 'user_id']

    @property
    def notification_subject(self):
        return u'Membership Cancellation from {}'.format(
            self.user.display_name)

    @property
    def notification_text(self):
        return CANCEL_NOTIFICATION.format(
            self.user.display_name,
            self.user.get_email_address(),
            g.url(self.user.url() + 'profile'),
            g.url(self.app_config.url() + 'members')
        )


class MembershipRemovalRequest(AbstractRequestArtifact):
    """
    For a moderation situation in which admins cannot even boot a member
    without the member's permission

    """

    class __mongometa__:
        session = main_orm_session
        name = "membership_removal_request"
        indexes = [('project_id', 'user_id')]

    initiator_id = ForeignIdProperty('User', if_missing=lambda: c.user._id)
    initiator = VFRelationProperty('User', via="initiator_id")

    @property
    def notification_subject(self):
        return u'Membership Withdrawal Request for {}'.format(
            self.user.display_name)

    @property
    def notification_text(self):
        return REMOVAL_NOTIFICATION.format(
            initiator_name=self.initiator.display_name,
            project_name=self.project.name,
            recipient_name=self.user.display_name
        )

    @property
    def conversation_text(self):
        return REMOVAL_CONVERSATION.format(
            initiator_name=self.initiator.display_name,
            project_name=self.project.name,
            project_url=g.url(self.project.home_ac.url())
        )

    def notify(self):
        notification = AbstractRequestArtifact.notify(self)
        conversation = Conversation(subject="Membership Withdrawal Request")
        conversation.add_user_id(self.user_id)
        conversation.add_user_id(self.initiator_id)
        conversation.add_message(self.initiator_id, self.conversation_text)
        return notification

    def reject(self, text=''):
        """Reject the removal request"""
        notification = Notification.post(
            artifact=self,
            topic='membership',
            text=u"{} has rejected the request for removal from {}\n{}".format(
                self.user.display_name,
                self.project.name,
                text
            ),
            subject=u"Membership Withdrawal Request Rejected by {}".format(
                self.user.display_name
            )
        )
        self.delete()
        return notification


class MembershipInvitation(Artifact):

    class __mongometa__:
        session = main_orm_session
        name = 'membership_invitation'
        indexes = ['project_id', 'email', 'user_id', 'registration_token_id']

    _id = FieldProperty(S.ObjectId)
    project_id = ForeignIdProperty('Project', if_missing=lambda: c.project._id)
    project = VFRelationProperty('Project')
    project_role_id = ForeignIdProperty('ProjectRole', if_missing=None)
    project_role = VFRelationProperty('ProjectRole')
    registration_token_id = ForeignIdProperty(UserRegistrationToken,
                                              if_missing=None)
    registration_token = VFRelationProperty(UserRegistrationToken)
    email = FieldProperty(str)
    user_id = ForeignIdProperty('User', if_missing=None)
    user = VFRelationProperty('User', via="user_id")
    creator_id = ForeignIdProperty('User', if_missing=lambda: c.user._id)
    creator = VFRelationProperty('User', via="creator_id")
    text = FieldProperty(str)

    @classmethod
    def from_email(cls, email, project=None, text='', role_id=None, user=None):
        if project is None:
            project = c.project
        obj = cls.query.get(email=email, project_id=project._id)
        if obj is None:
            obj = cls(
                email=email,
                project_id=project._id,
                text=text,
                project_role_id=role_id
            )
            if user:
                obj.user = user
            else:
                obj.generate_registration_token()
            Notification.post(
                artifact=obj,
                topic='membership',
                text=obj.notification_text,
                subject=obj.invitation_subject
            )
        else:
            obj.text = text
            obj.project_role_id = role_id
            if user:
                obj.user = user
        return obj

    @classmethod
    def from_user(cls, user, project=None, text=''):
        if project is None:
            project = c.project
        obj = cls.query.get(user_id=user._id, project_id=project._id)
        if obj is None:
            obj = cls(
                user_id=user._id,
                project_id=project._id,
                text=text
            )
            Notification.post(
                artifact=obj,
                topic='membership',
                text=obj.notification_text,
                subject=obj.invitation_subject
            )
        else:
            obj.text = text
        return obj

    @property
    def notification_text(self):
        if self.user_id:
            name_tag = u'Name: {}'.format(self.user.display_name)
            profile_tag = u'Profile: {}'.format(
                os.path.join(
                    tg.config.get('base_url', 'https://vulcanforge.org'),
                    self.user.url() + 'profile'
                )
            )
        else:
            name_tag = ''
            profile_tag = ''
        return INVITATION_NOTIFICATION.format(
            name_tag,
            self.email or self.user.get_email_address(),
            profile_tag
        )

    @property
    def invitation_text(self):
        if self.user_id:
            read_roles = self.project.get_read_roles()
            if 'anonymous' in read_roles or 'authenticated' in read_roles:
                url_text = "the project's home tool:"
                url = g.url(self.project.url())
            else:
                url_text = "your profile"
                if self.user_id:
                    url_text += ":"
                    url = g.url(self.user.url() + "profile")
                else:
                    url = ""
        else:
            url_text = "registering here: "
            if self.registration_token:
                url = self.registration_token.full_registration_url
            else:
                url = g.url('/auth/register')

        return INVITATION_EMAIL.format(
            text=self.text,
            means=url_text,
            url=url
        )

    @property
    def invitation_subject(self):
        return u'Membership Invitation from {}'.format(
            self.creator.display_name)

    def index(self, **kw):
        return {'title_s': self.invitation_subject}

    def url(self):
        return self.app_config.url()

    def send(self):
        if self.user_id:
            self.send_as_convo()
        else:
            self.send_as_email()

    def send_as_email(self):
        email = self.email or self.user.get_email_address()
        sendmail.post(
            fromaddr=g.forgemail_return_path,
            destinations=[email],
            reply_to='',
            subject="You have been invited to join a team{}".format(
                ' on ' + tg.config['forge_name'] if 'forge_name' in tg.config
                else ''),
            message_id=gen_message_id(),
            text=self.invitation_text
        )

    def send_as_convo(self):
        conversation = Conversation(subject="Project Invitation")
        conversation.add_user_id(self.user_id)
        conversation.add_user_id(self.creator_id)
        conversation.add_message(self.creator_id, self.invitation_text)

    def generate_registration_token(self):
        exp_hrs = asint(tg.config.get("auth.invitation_lifetime_hours", 48))
        expiry_date = datetime.utcnow() + timedelta(hours=exp_hrs)
        token = UserRegistrationToken(
            email=self.email,
            expiry_date=expiry_date,
            nonce=hashlib.sha256(os.urandom(10)).hexdigest(),
            project_role_id=self.project_role_id
        )
        self.registration_token = token
        return token
