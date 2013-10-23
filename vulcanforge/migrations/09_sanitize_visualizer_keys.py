from pylons import app_globals as g

from vulcanforge.common.helpers import urlquote
from vulcanforge.migration.base import BaseMigration
from vulcanforge.visualize.model import Visualizer


class SanitizeVisualizerKeys(BaseMigration):
    def run(self):
        count = 0
        for visualizer in Visualizer.query.find({"widget": "iframe"}):
            visualizer.widget = 's3'
            for path in visualizer.bundle_content:
                if not visualizer.get_s3_key(path, insert_if_missing=False):
                    key0 = g.get_s3_key(urlquote(visualizer.key_prefix) + path)
                    key1 = visualizer.get_s3_key(path)
                    key1.set_contents_from_string(key0.read())
                    key0.delete()
            count += 1
        self.write_output('Sanitized {} visualizers'.format(count))
