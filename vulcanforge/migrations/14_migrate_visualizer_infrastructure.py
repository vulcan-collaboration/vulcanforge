import os

from formencode.variabledecode import variable_decode
from ming.odm import ThreadLocalODMSession
from pylons import app_globals as g
from tg import config
from vulcanforge.common.util.filesystem import import_object

from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.migration.base import BaseMigration
from vulcanforge.visualize.model import VisualizerConfig, S3VisualizerFile
from vulcanforge.visualize.s3hosted import S3HostedVisualizer


class MigrateVisualizerInfrastructure(BaseMigration):
    def run(self):
        db, coll = pymongo_db_collection(VisualizerConfig)
        count = 0
        converted_ids = []

        # convert s3 visualizers
        s3visualizer = {
            "classname": S3HostedVisualizer.__name__,
            "module": S3HostedVisualizer.__module__
        }
        for doc in coll.find({"widget": "s3"}):
            count += 1
            converted_ids.append(doc["_id"])
            del doc['widget']
            del doc['thumb']
            del doc['bucket_name']
            doc['options'] = {
                "entry_point": doc.pop('entry_point', 'index.html')
            }
            if 'teaser_entry_point' in doc:
                doc['options']["teaser_entry_point"] = doc.pop(
                    'teaser_entry_point', None)
            doc['visualizer'] = s3visualizer
            bundle_content = doc.pop('bundle_content')
            for filename in bundle_content:
                if os.path.isdir(filename):
                    continue
                keyname = 'Visualizer/{}#{}'.format(doc['_id'], filename)
                key = g.get_s3_key(keyname)
                s3_file = S3VisualizerFile(
                    filename=filename,
                    visualizer_config_id=doc['_id'])
                s3_file.set_contents_from_string(key.read(), encrypt_key=g.s3_encryption)
            coll.save(doc)

        ThreadLocalODMSession.flush_all()

        # convert server-side visualizers
        decoded = variable_decode(config)
        visopts = decoded['visualizer']
        for shortname, path in visopts.items():
            count += 1
            doc = coll.find_one({
                "shortname": shortname,
                "widget": {"$exists": 1}})
            visualizer_obj = import_object(path)
            if doc:
                converted_ids.append(doc["_id"])
                split_path = path.split(':')
                path_spec = {
                    'module': split_path[0],
                    'classname': split_path[1]
                }
                self._convert_serverside(doc, path_spec)
                doc.update(visualizer_obj.default_options)
                coll.save(doc)

        # remove danglers
        coll.remove({"_id": {"$nin": converted_ids}})

        self.write_output('Migrated {} visualizers'.format(count))

    def _convert_serverside(self, doc, path_spec):
        del doc['widget']
        del doc['thumb']
        del doc['bucket_name']
        doc.pop('entry_point', None)
        doc.pop('teaser_entry_point', None)
        doc['visualizer'] = path_spec
        doc.pop('bundle_content', None)
