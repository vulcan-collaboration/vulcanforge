import logging
import posixpath
import math
from datetime import datetime

from ming import schema as S
from ming.odm import FieldProperty, ForeignIdProperty, RelationProperty
from ming.utils import LazyProperty
from pylons import app_globals as g, tmpl_context as c
from boto.s3.multipart import MultiPartUpload

from vulcanforge.artifact.model import VisualizableArtifact
from vulcanforge.auth.model import User
from vulcanforge.common.model.session import artifact_orm_session
from vulcanforge.common.exceptions import AJAXMethodNotAllowed
from vulcanforge.virusscan.model import S3VirusScannableMixin
from vulcanforge.notification.model import Notification

from vulcanforge.common.tasks.file import delete_content_from_s3

LOG = logging.getLogger(__name__)


class FileArtifact(VisualizableArtifact,
                   S3VirusScannableMixin):

    class __mongometa__:
        session = artifact_orm_session
        name = 'file_artifact'
        indexes = ['app_config_id', 'filename']

    type_s = 'File Artifact'
    item_key = FieldProperty(str)
    container_key = FieldProperty(str, if_missing=None)
    filename = FieldProperty(str, if_missing='')
    filesize = FieldProperty(int, if_missing=None)
    deleted = FieldProperty(bool, if_missing=False)
    creator_id = ForeignIdProperty(User, if_missing=None)
    creator = RelationProperty(User)

    # Upload related
    md5_signature = FieldProperty(str, if_missing='')
    upload_completed = FieldProperty(bool, if_missing=True)
    mp_upload_id = FieldProperty(str, if_missing=None)

    # Virus scan status
    # Partially scanned is used because of limitations these files are assumed
    # safe but not with 100% certainty
    virus_scan_status = FieldProperty(
        S.OneOf('unscanned', 'failed', 'partially_scanned', 'passed',
                if_missing='unscanned'))
    virus_scan_date = FieldProperty(datetime, if_missing=None)

    def parent_name(self):
        parsed_name = posixpath.basename(self.container_key.rstrip('/'))
        if not parsed_name:
            # must be root
            parsed_name = '/'
        return parsed_name

    # CUD notifications
    def notify_create(self):
        subject = '{} was added'.format(self.title_s)
        text = "{} added {}".format(c.user.display_name, self.title_s)
        Notification.post(self, "metadata", text=text, subject=subject)

    def notify_update(self):
        subject = '{} was modified'.format(self.title_s)
        text = "{} modified {}".format(c.user.display_name, self.title_s)
        Notification.post(self, "metadata", text=text, subject=subject)

    def notify_delete(self):
        subject = '{} was deleted'.format(self.title_s)
        text = "{} deleted {}".format(c.user.display_name, self.title_s)
        Notification.post(self, "metadata", text=text, subject=subject,
                          link=self.parent_url())

    def notify_virus_found(self):
        subject = '{} was deleted'.format(self.title_s)
        text = "{} detected a virus in {}.".format(
            g.forge_name, self.title_s)
        Notification.post(self, "metadata", text=text, subject=subject,
                          link=self.parent_url())

    ### Virus scanning related functions
    @LazyProperty
    def is_scanned(self):
        if (g.clamav_enabled and self.virus_scan_status == 'unscanned'):
            return False
        else:
            return True

    def virus_not_found(self, partial_scan):
        self.virus_scan_date = datetime.now()
        if partial_scan:
            self.virus_scan_status = 'partially_scanned'
        else:
            self.virus_scan_status = 'passed'
        self.flush_self()

    def virus_found(self, result=None):
        self.virus_scan_date = datetime.now()
        self.virus_scan_status = 'failed'
        self.delete()
        self.notify_virus_found()

    def virus_scanner_error(self, error):
        LOG.error(error)

    def get_key(self):
        return g.get_s3_key('', self)

    def delete(self):
        self.deleted = True
        delete_content_from_s3.post(self._id)

    @LazyProperty
    def multipart(self):
        mp = MultiPartUpload(self.get_key().bucket)
        mp.key_name = self.get_key().name
        mp.id = self.mp_upload_id
        mp.encrypted = g.s3_encryption

        return mp

    @property
    def upload_progress(self):
        chunk_count = int(
            math.ceil(self.filesize / float(g.multipart_chunk_size)))
        return float(len(self.part_number_list)) / chunk_count

    @LazyProperty
    def part_number_list(self):
        part_list = self.multipart.get_all_parts()
        part_numbers = []
        if part_list is not None:
            part_numbers = [p.part_number for p in part_list]
        return part_numbers

    def _complete_hook(self, notify=True):
        self.upload_completed = True
        self.flush_self()
        if (g.clamav_enabled):
            self.scan_for_virus.post(
                taskd_priority=g.clamav_task_priority)
        if notify:
            self.notify_create()

    def add_file_part(self,
                         file_part,
                         resumableChunkNumber=1,
                         notify=False):

        chunk_count = int(math.ceil(self.filesize / float(g.multipart_chunk_size)))
        if int(resumableChunkNumber) > chunk_count:
            raise AJAXMethodNotAllowed('Chunk number is out of bounds.')

        key = self.get_key()
        if self.filesize <= g.multipart_chunk_size:
            key.set_contents_from_file(file_part, encrypt_key=g.s3_encryption)
            self._complete_hook(notify)
            return

        parts = self.multipart.get_all_parts(max_parts=1, part_number_marker=resumableChunkNumber-1)
        if not parts or parts[0].part_number != resumableChunkNumber:
            self.multipart.upload_part_from_file(file_part,
                part_num=resumableChunkNumber)

        # Finish the upload
        if len(self.multipart.get_all_parts(max_parts=chunk_count)) == chunk_count:
            # The upload might have been finalized by a parallel thread
            try:
                self.multipart.complete_upload()
            except:
                pass
            self.mp_upload_id = None
            self._complete_hook(notify)

    def read(self):
        return self.get_key().read()