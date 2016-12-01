from datetime import datetime

from ming import schema as S
from ming.odm import ForeignIdProperty, RelationProperty, FieldProperty

from vulcanforge.common.model.session import artifact_orm_session
from vulcanforge.artifact.model import Artifact
from vulcanforge.notification.model import Notification
from vulcanforge.project.model import Project
from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.common.model.session import main_orm_session

from .dashboard import PortalConfig


class UserStatusChange(Artifact):
    """Base class for UserJoin and UserLeave"""

    project_id = ForeignIdProperty(Project)
    project = RelationProperty(Project, via="project_id")
    user_id = ForeignIdProperty('User')
    user = RelationProperty('User', via="user_id")

    def index(self, **kw):
        return None

    def url(self):
        return self.app_config.url()

    def notify(self):
        Notification.post(
            artifact=self,
            topic="membership",
            text=self.notification_text,
            subject=self.summary
        )

    @property
    def project_type(self):
        if self.project.neighborhood.kind == "competition":
            if self.project.shortname == '--init--':
                return "competition"
            else:
                return "team"
        else:
            if self.project.shortname == '--init--':
                return "neighborhood"
            else:
                return "project"


class UserJoin(UserStatusChange):

    class __mongometa__:
        session = artifact_orm_session
        name = "user_join"
        indexes = ['project_id', 'user_id']

    type_s = 'Member Join'
    added_by_id = ForeignIdProperty('User', if_missing=None)
    added_by = RelationProperty('User', via='added_by_id')

    @property
    def summary(self):
        return 'Member {} Joined the {}'.format(
            self.user.username,
            self.project_type.capitalize()
        )

    @property
    def notification_text(self):
        return (
            'A new user, {}, has joined the {}! For more information, '
            'check out their profile: {}'
        ).format(
            self.user.display_name,
            self.project_type,
            self.user.url() + 'profile'
        )


class UserExit(UserStatusChange):

    class __mongometa__:
        session = artifact_orm_session
        name = "user_exit"
        indexes = ['project_id', 'user_id']

    type_s = 'Member Exit'
    removed_by_id = ForeignIdProperty('User', if_missing=None)
    removed_by = RelationProperty('User', via='removed_by_id')

    @property
    def summary(self):
        return 'Member {} Left the Team'.format(
            self.user.username,
            self.project_type.capitalize()
        )

    @property
    def notification_text(self):
        text = "{} has left the {}."
        return text.format(self.user.display_name, self.project_type)


class AccessLogChecked(BaseMappedClass):

    class __mongometa__:
        name = 'access_log_checked'
        session = main_orm_session
        indexes = [('user_id', 'app_config_id')]

    _id = FieldProperty(S.ObjectId)
    user_id = ForeignIdProperty('User', if_missing=None)
    project_id = ForeignIdProperty('Project', if_missing=None)
    app_config_id = ForeignIdProperty('AppConfig', if_missing=None)

    last_checked = FieldProperty(datetime, if_missing=None)

    @classmethod
    def upsert(cls, user_id, app_config_id, project_id):
        visit = cls.query.get(user_id=user_id, app_config_id=app_config_id)
        if not visit:
            visit = cls(user_id=user_id, app_config_id=app_config_id, project_id=project_id)

        visit.last_checked = datetime.utcnow()
        visit.flush_self()

        return visit