from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.stats import BaseStatsAggregator
from vulcanforge.events.model import Event


class LoginAggregator(BaseStatsAggregator):
    user_field = 'context.user'
    timestamp_field = 'timestamp'

    def __init__(self, **kwargs):
        super(LoginAggregator, self).__init__(**kwargs)
        db, self.collection = pymongo_db_collection(Event)

    def make_query(self):
        super(LoginAggregator, self).make_query()
        self.query['type'] = 'login'
        return self.query