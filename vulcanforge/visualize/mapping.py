import hashlib
import logging
import mimetypes
import re
import time

from pylons import app_globals as g
import pymongo

from vulcanforge.visualize.model import VisualizerConfig, ProcessingStatus


LOG = logging.getLogger(__name__)


class VisualizerConfigMapper(object):
    """Uses the `extensions` property of VisualizerConfigs to make a pattern
    mapper for visualizer configs

    """
    CACHE_KEY = 'visualizer-pattern-cache-token'
    _additional_text_extensions = {
        '.ini',
        '.gitignore',
        '.svnignore',
        'readme'
    }

    def __init__(self):
        super(VisualizerConfigMapper, self).__init__()
        self.cache_token = 'init'
        self.visualization_map = []
        self.processing_map = []

    def clear(self):
        self.visualization_map = []
        self.processing_map = []

    def refresh(self):
        self.clear()
        cur = VisualizerConfig.query.find({"active": True})
        for vis_config in cur.sort("priority", pymongo.DESCENDING):
            exts, all_exts = self._compile_exts(vis_config.extensions)
            mime_types = vis_config.mime_types
            if mime_types:
                mime_types = map(re.compile, mime_types)
            self.visualization_map.append({
                "config_id": vis_config._id,
                "extensions": exts,
                "mime_types": mime_types,
                "all_exts": all_exts
            })
            processing_exts, all_processing = self._compile_exts(
                vis_config.processing_extensions)
            pmime_types = vis_config.processing_mime_types
            if pmime_types:
                pmime_types = map(re.compile, pmime_types)
            vis_spec = {
                "config_id": vis_config._id,
                "extensions": processing_exts,
                "mime_types": pmime_types,
                "all_exts": all_processing
            }
            self.processing_map.append(vis_spec)

    def get_cache_token(self):
        return g.cache.get(self.CACHE_KEY)

    def invalidate_cache(self):
        g.cache.set(self.CACHE_KEY, str(time.time()))

    def check_expiration(self):
        cache_token = self.get_cache_token()
        if cache_token != self.cache_token:
            self.refresh()
            self.cache_token = cache_token

    def find_for_visualization(self, filename):
        self.check_expiration()
        config_ids = list(
            self._match_config_ids(filename, self.visualization_map))
        if config_ids:
            cur = VisualizerConfig.query.find({"_id": {"$in": config_ids}})
            configs = cur.sort("priority", pymongo.DESCENDING).all()
        else:
            configs = []
        return configs

    def find_for_processing(self, filename, unique_id=None):
        self.check_expiration()
        config_ids = list(
            self._match_config_ids(filename, self.processing_map))
        if config_ids:
            cur = VisualizerConfig.query.find({
                "_id": {"$in": config_ids}
            }).sort("priority", pymongo.DESCENDING)
            if unique_id:
                configs = [config for config in cur if
                           not self._is_proc_excluded(unique_id, config)]
            else:
                configs = cur.all()
        else:
            configs = []
        return configs

    def find_for_all(self, filename, unique_id=None):
        self.check_expiration()
        vis_ids = list(
            self._match_config_ids(filename, self.visualization_map))
        proc_ids = list(self._match_config_ids(filename, self.processing_map))
        all_ids = list(set(vis_ids + proc_ids))
        if all_ids:
            cur = VisualizerConfig.query.find({
                "_id": {"$in": all_ids}
            }).sort("priority", pymongo.DESCENDING)
            if unique_id:
                configs = [
                    config for config in cur if not config._id in proc_ids or
                    not self._is_proc_excluded(unique_id, config)]
            else:
                configs = cur.all()
        else:
            configs = []
        return configs

    def get_for_visualization(self, filename):
        self.check_expiration()
        i_match = self._match_config_ids(filename, self.visualization_map)
        try:
            config_id = next(i_match)
        except StopIteration:
            return None
        else:
            return VisualizerConfig.query.get(_id=config_id)

    def get_for_all(self, filename, unique_id=None):
        self.check_expiration()
        config = None
        ivis_match = self._match_config_ids(filename, self.visualization_map)
        iproc_match = self._match_config_ids(filename, self.processing_map)

        try:
            vis_id = next(ivis_match)
        except StopIteration:
            pass
        else:
            config = VisualizerConfig.query.get(_id=vis_id)

        for proc_id in iproc_match:
            proc = VisualizerConfig.query.get(_id=proc_id)
            if config and proc.priority < config.priority:
                break
            if not unique_id or not self._is_proc_excluded(unique_id, proc):
                config = proc
                break

        return config

    def _compile_exts(self, exts):
        extensions = []
        all_exts = False
        for pattern in exts:
            if pattern == '*':
                all_exts = True
            else:
                extensions.append(re.compile(pattern))
        return extensions, all_exts

    def _matches_any(self, s, patterns):
        return any(p.search(s) for p in patterns)

    def _matches_spec(self, fname, mimetype, spec):
        if mimetype and spec["mime_types"]:
            if not self._matches_any(mimetype, spec["mime_types"]):
                return False
            if spec["all_exts"]:
                return True
        return self._matches_any(fname, spec["extensions"])

    def _match_config_ids(self, filename, vmap):
        mimetype = self._get_mimetype(filename)
        for vis_spec in vmap:
            matches = self._matches_spec(filename, mimetype, vis_spec)
            if matches:
                yield vis_spec["config_id"]

    def _is_proc_excluded(self, unique_id, config):
        """Checks whether the resource is excluded based on its processing
        status

        """
        if config.processing_status_exclude:
            status = ProcessingStatus.get_status_str(unique_id, config)
            if status in config.processing_status_exclude:
                return True
        return False

    def _get_mimetype(self, filename):
        filename = filename.lower()
        for ext in self._additional_text_extensions:
            if filename.endswith(ext):
                mtype = 'text/plain'
                break
        else:
            mtype = mimetypes.guess_type(filename)[0]

        return mtype

