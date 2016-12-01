import logging

from ming.odm import session

from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.downloads.model import ForgeDownloadsFile


LOG = logging.getLogger(__name__)


class SetNewFileAttributes(BaseMigration):

    sesh = session(ForgeDownloadsFile)
    db = sesh.impl.bind.db

    def run(self):
        self.write_output('Setting deleted attribute ...')
        coll = self.db[ForgeDownloadsFile.__mongometa__.name]

        coll.update(
            {'deleted': {'$exists': False}},
            {'$set':{'deleted': False}},
            multi=True
        )

        coll.update(
            {'upload_completed': {'$exists': False}},
            {'$set':{'upload_completed': True}},
            multi=True
        )

        self.write_output('Finished setting the deleted upload_completed attributes for files.')


        self.write_output('Setting zip manifest...')
        cursor = ForgeDownloadsFile.query.find({
            'filename':{'$regex':'.zip'}
        })
        for f in cursor:
            # We only want downloads files
            if not f.zip_manifest and not f.deleted:
                f._populate_zip_manifest()
                f.flush_self()

        self.write_output('Finished setting zip_manifest.')
