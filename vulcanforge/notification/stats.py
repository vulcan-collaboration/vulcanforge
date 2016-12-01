import bson

from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.notification.model import Notification
from vulcanforge.stats import StatsQuerySchema, BaseStatsAggregator


class NotificationQuerySchema(StatsQuerySchema):
    pass

class NotificationAggregator(BaseStatsAggregator):
    """Notifications"""

    timestamp_field = 'pubdate'

    def __init__(self, **kwargs):
        filters = ('app_config_id', 'exchange_uri')
        self._filters = {f: kwargs.pop(f) for f in filters if f in kwargs}
        super(NotificationAggregator, self).__init__(**kwargs)
        db, self.collection = pymongo_db_collection(Notification)

    def make_query(self):
        super(NotificationAggregator, self).make_query()
        valued = [k for k, v in self._filters.items() if v]
        if len(valued) > 1:
            elements = [{f: {"$in": self._filters[f]}} for f in valued]
            self.query.update({"$or": elements})
        else:
            self.query.update({f: {"$in": self._filters[f]} for f in valued})
        return self.query
