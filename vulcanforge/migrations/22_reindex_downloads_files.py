import logging

from vulcanforge.tools.downloads import model as DM
from vulcanforge.migration.base import BaseMigration
from vulcanforge.artifact.tasks import add_artifacts, del_artifacts
from vulcanforge.common.util.model import chunked_find

LOG = logging.getLogger(__name__)


class ReindexDownloadsFiles(BaseMigration):


    def run(self):

        self.write_output('Reindexing downloads files...')
        for files in chunked_find(DM.ForgeDownloadsFile, {}):
            ref_ids = []
            for df in files:
                ref_ids.append(df.index_id())

            indexes = filter(None, ref_ids)
            add_artifacts(indexes, update_refs=False)

        self.write_output('Removing zip contained files from SOLR index...')
        for files in chunked_find(DM.ZipContainedFile, {}):
            delete_specs = []
            for zcf in files:
                delete_specs.append({"ref_id":zcf.index_id()})

            del_artifacts(delete_specs)

        self.write_output('Finished reindexing / removing files.')
