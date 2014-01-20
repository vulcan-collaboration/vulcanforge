from vulcanforge.artifact.util import iter_artifact_classes
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.migration.base import BaseMigration


class RemoveAltResourceKeys(BaseMigration):
    def run(self):
        count = 0
        query = {"$or": [
            {"alt_resources": {"$exists": 1}},
            {"_alt_loading": {"$exists": 1}}
        ]}
        for a_cls in iter_artifact_classes():
            db, coll = pymongo_db_collection(a_cls)
            for a_doc in coll.find(query):
                a_doc.pop("alt_resources", None)
                a_doc.pop("_alt_loading", None)
                count += 1
                coll.save(a_doc)
        self.write_output("Repaired %d artifacts")
