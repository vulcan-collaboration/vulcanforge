from vulcanforge.common.model.session import main_doc_session
from vulcanforge.migration.base import BaseMigration

PAGESIZE = 1024


class MigrateEvents(BaseMigration):

    zarkov_event_collection = main_doc_session.bind.conn['zarkov']['event']
    allura_event_collection = main_doc_session.bind.conn['allura']['event']

    def is_needed(self):
        try:
            zarkov_event = self.zarkov_event_collection.find_one()
        except Exception as e:
            zarkov_event = None
        if zarkov_event is None:
            return False

        zarkov_event.pop('_id')
        allura_event = self.allura_event_collection.find_one(zarkov_event)

        # The migration is needed if we could not find the new one
        return allura_event is None

    def run(self):
        for zarkov_events_chunk in self._chunked_event_iterator():
            allura_events = []
            for zarkov_event in zarkov_events_chunk:
                zarkov_event.pop('_id')
                allura_events.append(zarkov_event)

            if len(allura_events):
                self.allura_event_collection.insert(allura_events)

    def _chunked_event_iterator(self):
        # Taking advantage of the fact that the id is an integer
        page = 0
        while True:
            results = self.zarkov_event_collection.find({
                '$and':[
                    {'_id': {'$gte': PAGESIZE*page}},
                    {'_id': {'$lt': PAGESIZE*(page+1)}}
                ]
            })
            if results.count() == 0: break
            yield list(results)
            page += 1
