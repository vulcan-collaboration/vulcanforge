from datetime import datetime

from ming import schema
from ming.odm import (
    FieldProperty,
    ForeignIdProperty,
    RelationProperty,
    Mapper
)
from pylons import app_globals as g

from vulcanforge.common.model.index import SOLRIndexed
from vulcanforge.common.model.session import solr_indexed_session


class UserAdvertisement(SOLRIndexed):

    class __mongometa__:
        session = solr_indexed_session
        name = 'user_advertisement'
        indexes = ['user_id', 'pub_date']

    type_s = 'UserAdvertisement'
    _id = FieldProperty(schema.ObjectId)
    pub_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    user_id = ForeignIdProperty('User')
    user = RelationProperty('User')
    text_content = FieldProperty(str)

    @property
    def index_dict(self):
        return {
            '_id_s': self._id,
            'type_s': self.type_s,
            'title_s': self.get_title(),
            'url_s': self.url(),
            'pubdate_dt': self.pub_date,
            'user_id_s': str(self.user_id),
            'text_content_s': self.text_content
        }

    @property
    def index_text_objects(self):
        return [self.text_content, self.user.display_name, self.user.username]

    def url(self):
        return self.user.url()

    def get_title(self):
        return self.user.display_name


class ProjectAdvertisement(SOLRIndexed):

    class __mongometa__:
        session = solr_indexed_session
        name = 'project_advertisement'
        indexes = ['project_id', 'pub_date']

    type_s = 'ProjectAdvertisement'
    _id = FieldProperty(schema.ObjectId)
    pub_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    project_id = ForeignIdProperty('Project')
    project = RelationProperty('Project')
    text_content = FieldProperty(str)

    @property
    def index_dict(self):
        return {
            '_id_s': self._id,
            'type_s': self.type_s,
            'title_s': self.get_title(),
            'url_s': self.url(),
            'pubdate_dt': self.pub_date,
            'project_id_s': str(self.project_id),
            'read_roles': self.get_read_roles(),
            'text_content_s': self.text_content
        }

    @property
    def index_text_objects(self):
        return [self.text_content, self.project.name, self.project.shortname]

    def get_read_roles(self):
        return g.security.roles_with_permission(self.project, 'read')

    def url(self):
        return self.project.url()

    def get_title(self):
        return self.project.name



