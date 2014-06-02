from ming.odm import ThreadLocalODMSession
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.migration.base import BaseMigration
from vulcanforge.visualize.model import (
    ProcessedArtifactFile,
    VisualizableQueryParam
)


class AddVisualizableQueryParam(BaseMigration):
    def run(self):
        db, coll = pymongo_db_collection(ProcessedArtifactFile)
        pf_map = {}
        for doc in coll.find({"query_param": {"$exists": 1, "$ne": None}}):
            pf_map[doc["_id"]] = doc.pop('query_param')
            coll.save(doc)

        if pf_map:
            query = {"_id": {"$in": pf_map.keys()}}
            for pfile in ProcessedArtifactFile.query.find(query):
                VisualizableQueryParam(
                    visualizer_config_id=pfile.visualizer_config_id,
                    unique_id=pfile.unique_id,
                    query_param=pf_map[pfile._id],
                    query_val=pfile.url()
                )
            ThreadLocalODMSession.flush_all()
        self.write_output('Added {} query params'.format(len(pf_map)))