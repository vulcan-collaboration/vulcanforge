import logging
import re
import os
import zipfile
import json

from pylons import app_globals as g

from vulcanforge.visualize.base import BaseVisualizer
from vulcanforge.visualize.exceptions import VisualizerError
from vulcanforge.visualize.model import VisualizerConfig, S3VisualizerFile
from vulcanforge.visualize.widgets import IFrame, ArtifactIFrame

LOG = logging.getLogger(__name__)


class S3HostedVisualizer(BaseVisualizer):
    """VF acts as a proxy to a visualizer stored in S3"""

    no_upload_extensions = [
        re.compile('\.git/'),
        re.compile('\.svn/'),
        re.compile('__MACOSX/'),
        re.compile('\.DS_Store'),
        re.compile('^/'),
        re.compile('\.\.'),
    ]
    # attrs editable by manifest file
    _editable_attrs = (
        'name',
        'mime_types',
        'description',
        'extensions',
        'shortname',
        'icon'
    )
    _options_attrs = (
        'entry_point',
        'teaser_entry_point'
    )

    default_options = {
        "config": {
            "entry_point": "index.html"
        }
    }

    @property
    def icon_url(self):
        url = None
        if self.config.icon:
            s3_file = S3VisualizerFile.query.get(
                filename=self.config.icon)
            if s3_file:
                url = s3_file.url()
            else:
                url = self.config.icon
        return url

    @classmethod
    def new_from_archive(cls, archive_fp):
        inst = cls(VisualizerConfig.from_visualizer(cls))
        inst.update_from_archive(archive_fp)

    @property
    def src_url(self):
        return self.get_entry_point_file().url()

    def get_entry_point_file(self):
        ep_file = S3VisualizerFile.query.get(
            filename=self.config.options["entry_point"],
            visualizer_config_id=self.config._id)
        return ep_file

    def update_from_archive(self, archive_fp):
        with zipfile.ZipFile(archive_fp) as zip_handle:
            # find the manifest file
            for zip_info in zip_handle.filelist:
                if os.path.basename(zip_info.filename) == 'manifest.json':
                    root = os.path.dirname(zip_info.filename)
                    manifest_filename = zip_info.filename
                    break
            else:
                raise VisualizerError("No Manifest File found")

            # parse manifest
            with zip_handle.open(manifest_filename) as manifest_fp:
                manifest_json = json.load(manifest_fp)
                self.update_from_manifest(manifest_json)

            # upload the files to the object store
            self._upload_files(zip_handle, root)

    def update_from_manifest(self, manifest):
        """@param manifest dict"""
        for k, v in manifest.items():
            if k in self._editable_attrs:
                setattr(self.config, k, v)
            elif k in self._options_attrs:
                setattr(self.config.options, k, v)
            else:
                LOG.info('manifest.json contains ignored key: %s = %s', k, v)
        if not self.config.shortname:
            shortname = VisualizerConfig.strip_name(self.config.name)
            self.config.shortname = shortname

    def download_to_archive(self, archive_fp):
        cur = S3VisualizerFile.query.find({
            "visualizer_id": self.config._id})
        for s3_file in cur:
            archive_fp.writestr(s3_file.filename, s3_file.read())

    def _can_upload(self, path):
        return not any(r.search(path) for r in self.no_upload_extensions)

    def _upload_files(self, zip_handle, root=''):
        for zip_info in zip_handle.filelist:
            filename = zip_info.filename
            if self._can_upload(filename) and not os.path.isdir(filename):
                with zip_handle.open(filename) as fp:
                    relative_path = os.path.relpath(filename, root)
                    s3_file = S3VisualizerFile(filename=relative_path)
                    s3_file.set_contents_from_string(fp.read())
