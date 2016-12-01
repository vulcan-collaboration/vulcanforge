import logging

from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.downloads import model as FDM
from vulcanforge.common.util.model import pymongo_db_collection

LOG = logging.getLogger(__name__)


class MoveDownloadsLogCollection(BaseMigration):

    def run(self):
        self.write_output('Moving downloads collection ...')

        db, new_coll = pymongo_db_collection(FDM.ForgeDownloadsLogEntry)
        coll = db["forgedownloads_log_entry"]

        for log_entry in coll.find():
            log_entry.pop('file_name')
            log_entry.pop('file_path')
            log_entry['artifact_id'] = log_entry.get('file_id',None)
            log_entry.pop('file_id')
            d_file = FDM.ForgeDownloadsFile.query.get(_id=log_entry.get('artifact_id',None))
            if d_file is not None:
                log_entry['app_config_id'] = d_file.app_config_id
                log_entry['project_id'] = d_file.project._id
                log_entry['url'] = d_file.url()

            access_denied = log_entry.get('artifact_id',None)
            if access_denied is None:
                log_entry['access_denied'] = False

            try:
                new_coll.insert(log_entry)
            except:
                pass

        self.write_output('Finished moving downloads collection.')