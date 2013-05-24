from vulcanforge.stats import BaseStatsAggregator


class LoginAggregator(BaseStatsAggregator):
    user_field = 'context.user'
    timestamp_field = 'timestamp'

    def __init__(self, **kwargs):
        super(LoginAggregator, self).__init__(**kwargs)

        from zarkov.model import event as zevent
        self.collection = zevent.m.collection

    def make_query(self):
        super(LoginAggregator, self).make_query()
        self.query['type'] = 'login'
        return self.query