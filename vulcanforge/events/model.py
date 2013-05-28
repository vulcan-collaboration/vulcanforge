from datetime import datetime

from ming.odm.declarative import MappedClass
from ming.odm.property import FieldProperty
from pylons import tmpl_context as c

from vulcanforge.common.model.session import main_orm_session


class Event(MappedClass):

    class __mongometa__:
        name = 'event'
        session = main_orm_session

    _id = FieldProperty(int)
    timestamp = FieldProperty(datetime, if_missing=datetime.utcnow)
    type = FieldProperty(str)
    context = FieldProperty({str: None})
    extra = FieldProperty(None)

    @classmethod
    def make_event(cls, user=None, neighborhood=None, project=None, app=None,
                   **kwargs):
        """Automagically generates the context from the request globals"""
        if user is None:
            user = getattr(c, 'user', None)
        if project is None:
            project = getattr(c, 'project', None)
        if app is None:
            app = getattr(c, 'app', None)

        if project and user:
            is_project_member = project.user_in_project(user=user)
        else:
            is_project_member = False

        if project and not neighborhood:
            neighborhood = project.neighborhood

        context = {
            'user': user.username if user else None,
            'neighborhood': neighborhood.name if neighborhood else None,
            'project': project.shortname if project else None,
            'tool': app.tool_name if app else None,
            'mount_point': app.config.options.mount_point if app else None,
            'is_project_member': is_project_member
        }

        return cls(context=context, **kwargs)
