import os

from pylons import app_globals as g

from vulcanforge.common.helpers import urlquote
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.migration.base import BaseMigration
from vulcanforge.visualize.model import VisualizerConfig


class SanitizeVisualizerKeys(BaseMigration):
    def run(self):
        count = 0
        db, coll = pymongo_db_collection(VisualizerConfig)
        for vis_doc in coll.find({"widget": "iframe"}):
            vis_doc['widget'] = 's3'
            for path in vis_doc.get('bundle_content', []):
                prefix = 'Visualizer/' + str(vis_doc['_id'])
                keyname = prefix + path
                if not g.get_s3_key(keyname, insert_if_missing=False):
                    key0 = g.get_s3_key(prefix + '%23' + path)
                    key1 = g.get_s3_key(keyname)
                    key1.set_contents_from_string(key0.read(), encrypt_key=g.s3_encryption)
                    key0.delete()
            count += 1
        self.write_output('Sanitized {} visualizers'.format(count))
