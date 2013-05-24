import logging

from bson.son import SON
import pymongo
from formencode import Schema, validators as fev

from vulcanforge.common.validators import DatetimeValidator, CommaSeparatedEach


LOG = logging.getLogger(__name__)

STATS_CACHE_TIMEOUT = 2 * 60 * 60


class StatsError(Exception):
    pass


class SortingField(fev.String):

    def _to_python(self, value, state):
        value = super(SortingField, self)._to_python(value, state)
        if value.endswith(' ASC'):
            value = (value[:-4], pymongo.ASCENDING)
        elif value.endswith(' DESC'):
            value = (value[:-5], pymongo.DESCENDING)
        else:
            value = (value, pymongo.ASCENDING)
        return value


class StatsQuerySchema(Schema):
    ignore_key_missing = True
    allow_extra_fields = True

    date_start = DatetimeValidator('%Y-%m-%d')
    date_end = DatetimeValidator('%Y-%m-%d')
    bins = CommaSeparatedEach(fev.String())
    order = CommaSeparatedEach(SortingField())
    label = fev.String()

    # override when ObjectIds
    user = fev.String()
    project = fev.String()


class BaseStatsAggregator(object):
    """
    Object for outputting statistics for artifacts with timestamps and
    project context

    """
    project_field = None
    user_field = None
    timestamp_field = None

    VALUE_CONVERTERS = {
        'weekday': {
            1: "Sunday",
            2: "Monday",
            3: "Tuesday",
            4: "Wednesday",
            5: "Thursday",
            6: "Friday",
            7: "Saturday"
        }
    }

    def __init__(self, date_start=None, date_end=None, extra_query=None,
                 bins=None, order=None, label=None, user=None, project=None):
        self.date_start = date_start
        self.date_end = date_end
        self.user = user
        self.project = project
        self.query = {}
        self.extra_query = extra_query or {}
        self.bins = bins or ["daily"]
        self.order = order
        self.label = label

        self.group_spec = None
        self.results = None

        # this should be overridden
        self.collection = None

    def make_query_value(self, key, value):
        if isinstance(value, basestring):
            return value
        else:
            return {'$in': value}

    def make_query(self):
        self.query.update(self.extra_query)
        if self.date_start:
            self.query.setdefault(
                self.timestamp_field, {})['$gt'] = self.date_start
        if self.date_end:
            self.query.setdefault(
                self.timestamp_field, {})['$lt'] = self.date_end
        if self.user and self.user_field:
            self.query[self.user_field] = self.make_query_value(
                self.user_field, self.user)
        if self.project and self.project_field:
            self.query[self.project_field] = self.make_query_value(
                self.project_field, self.project)
        return self.query

    def make_group_id_spec(self):
        id_spec = {}
        if any(b in self.bins for b in ('daily', 'hourly')):
            id_spec.update({
                'year': {'$year': '$' + self.timestamp_field},
                'month': {'$month': '$' + self.timestamp_field},
            })
            if 'daily' in self.bins:
                id_spec['day'] = {'$dayOfMonth': '$' + self.timestamp_field}
            elif 'hourly' in self.bins:
                id_spec.update({
                    "day": {'$dayOfMonth': '$' + self.timestamp_field},
                    "hour": {'$hour': '$' + self.timestamp_field}
                })
        elif 'weekly' in self.bins:
            id_spec.update({
                'week': {'$week': '$' + self.timestamp_field},
                'year': {'$year': '$' + self.timestamp_field}
            })
        elif 'weekday' in self.bins:
            id_spec['weekday'] = {'$dayOfWeek': '$' + self.timestamp_field}
        if self.project_field and 'project' in self.bins:
            id_spec['project'] = '$' + self.project_field
        if self.user_field and 'user' in self.bins:
            id_spec['user'] = '$' + self.user_field
        return id_spec

    def make_group_spec(self):
        id_spec = self.make_group_id_spec()
        self.group_spec = {
            '_id': id_spec,
            'count': {'$sum': 1}
        }
        return self.group_spec

    def make_doc_project_spec(self):
        return None

    def make_group_project_spec(self):
        if self.label:
            if self.label in self.group_spec['_id']:
                lbl = '$_id.' + self.label
            else:
                lbl = self.label
            d = {
                'label': lbl
            }
            d.update(
                {k: '$' + k for k in self.group_spec.keys() if k != '_id'})
            return d

    def make_order_spec(self, group_spec):
        order_spec = []
        for field in self.order:
            if isinstance(field, basestring):
                field = (field, pymongo.ASCENDING)
            if field[0] in group_spec.get('_id', []):
                order_spec.append(('_id.{}'.format(field[0]), field[1]))
            else:
                order_spec.append(field)
        return order_spec

    def create_pipeline(self, query, group_spec):
        pipeline = [
            {'$match': query}
        ]
        doc_project_spec = self.make_doc_project_spec()
        if doc_project_spec is not None:
            pipeline.append({'$project': doc_project_spec})
        pipeline.append({'$group': group_spec})
        group_project_spec = self.make_group_project_spec()
        if group_project_spec is not None:
            pipeline.append({'$project': group_project_spec})
        if self.order:
            order_spec = self.make_order_spec(group_spec)
            pipeline.append({'$sort': SON(order_spec)})
        return pipeline

    def run(self):
        query = self.make_query()
        grouping = self.make_group_spec()
        pipeline = self.create_pipeline(query, grouping)
        self.results = self.collection.aggregate(pipeline)
        return self.results

    def make_label(self, key):
        return key.capitalize()

    def fix_value(self, key, value, row):
        if key == '_id' and isinstance(value, dict):
            return {k: self.fix_value(k, v, row) for k, v in value.items()}
        if key == 'label':
            key = self.label
        if key in self.VALUE_CONVERTERS:
            try:
                return self.VALUE_CONVERTERS[key][value]
            except KeyError:
                pass
        return value

    def iter_fixed(self):
        if not self.results:
            raise StatsError('No Results Found')

        if self.results.get('result'):
            for row in self.results['result']:
                fixed = {
                    k: self.fix_value(k, v, row) for k, v in row.items()
                }
                yield fixed

    def fix_results(self):
        self.results['result'] = list(self.iter_fixed())
        return self.results

    def write_csv(self, fp):
        if self.results is None:
            self.run()

        gs = self.group_spec.copy()
        gs_id_keys = gs.pop('_id', {}).keys()
        gs_keys = gs.keys()

        headers = [self.make_label(k) for k in gs_id_keys] +\
                  [self.make_label(k) for k in gs_keys]
        fp.write(','.join(headers))
        fp.write('\n')

        for row in self.iter_fixed():
            values = [str(row['_id'][k]) for k in gs_id_keys] + \
                     [str(row[k]) for k in gs_keys]
            fp.write(','.join(values))
            fp.write('\n')
