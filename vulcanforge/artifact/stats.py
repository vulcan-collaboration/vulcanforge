import re

from formencode.validators import String
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.common.validators import CommaSeparatedEach
from vulcanforge.events.model import Event
from vulcanforge.stats import StatsQuerySchema, BaseStatsAggregator


class ArtifactQuerySchema(StatsQuerySchema):
    artifact_type = CommaSeparatedEach(String())
    neighborhood = String()


class ArtifactAggregator(BaseStatsAggregator):
    """Artifact Events"""

    project_field = 'context.project'
    user_field = 'context.user'
    timestamp_field = 'timestamp'

    VALID_TYPES = [
        'Tickets',
        'Wiki',
        'Discussion'
    ]

    def __init__(self, filter_posts=False, artifact_type=None, action=None,
                 neighborhood=None, **kwargs):
        super(ArtifactAggregator, self).__init__(**kwargs)
        self.filter_posts = filter_posts
        self.artifact_type = artifact_type
        self.action = action
        self.neighborhood = neighborhood

        db, self.collection = pymongo_db_collection(Event)

    def make_query(self):
        super(ArtifactAggregator, self).make_query()
        if self.filter_posts:
            self.query['extra'] = {
                "$and": [
                    {"$ne": None},
                    {"$ne": re.compile(r'^vulcanforge/discussion/model/')}
                ]
            }
        else:
            self.query['extra'] = {"$ne": None}
        atype = self.artifact_type or self.VALID_TYPES
        self.query['context.tool'] = self.make_query_value(
            'context.tool', atype)
        if self.action:
            self.query['type'] = self.make_query_value('type', self.action)
        if self.neighborhood:
            self.query['context.neighborhood'] = self.make_query_value(
                'context.neighborhood', self.neighborhood)
        return self.query

    def make_group_id_spec(self):
        id_spec = super(ArtifactAggregator, self).make_group_id_spec()
        if 'artifact' in self.bins:
            id_spec['artifact'] = '$context.tool'
        if 'action' in self.bins:
            id_spec['action'] = '$type'
        return id_spec


