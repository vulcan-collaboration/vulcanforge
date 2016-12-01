import logging
import pyclamd

from pylons import app_globals as g
from boto.s3.keyfile import KeyFile
from boto.connection import ConnectionPool
from ming.utils import LazyProperty

from vulcanforge.taskd import model_task
from vulcanforge.common.lib import zipfile

LOG = logging.getLogger(__name__)


class ClamAVDown(Exception):
    pass


class ClamAVDisabled(Exception):
    pass


class S3VirusScannableMixin(object):
    """ File Objects that have their content in S3 and are virus scannable
    """

    @LazyProperty
    def is_scanned(self):
        raise NotImplementedError('is_scanned')

    def is_zip(self):
        return False

    def index_id(self):
        raise NotImplementedError('index_id')

    def get_key(self):
        """
        Should return the S3 key to so the scanner can retrieve the content.
        """
        raise NotImplementedError('get_key')

    def virus_not_found(self, partial_scan=False):
        """

        :param partial_scan: True if the file was not fully scanned
        """
        raise NotImplementedError('virus_not_found')

    def virus_found(self):
        raise NotImplementedError('virus_found')

    def virus_scanner_error(self, error):
        raise NotImplementedError('virus_scanner_error')

    def _scan_zip(self, cns):
        # Keep the connection pool to an absolute minimum
        ConnectionPool.STALE_DURATION = 0.0

        key = self.get_key()
        zip_fp = KeyFile(key)
        zip_file = zipfile.ZipFile(zip_fp)
        partial_scan = False
        for zipinfo in zip_file.filelist:
            if zipinfo.file_size > 0:
                partial_scan = partial_scan or \
                               (g.clamav_stream_max < zipinfo.file_size)
                contained_file = zip_file.open(zipinfo)
                content = contained_file.read(min(g.clamav_stream_max, zipinfo.file_size))
                result = cns.scan_stream(content)
                contained_file.close()
                if result is not None:
                    LOG.error('ClamAV detected a virus in {}: {}'.format(
                        self.index_id(),
                        result
                    ))
                    self.virus_found()
                    key.close()
                    return
        self.virus_not_found(partial_scan)
        key.close()

    def _scan_file(self, cns):
        key = self.get_key()
        partial_scan = (g.clamav_stream_max < key.size)
        content = key.read(min(g.clamav_stream_max, key.size))
        result = cns.scan_stream(content)
        if result is None:
            self.virus_not_found(partial_scan)
        else:
            LOG.error('ClamAV detected a virus in {}: {}'.format(
                self.index_id(),
                result
            ))
            self.virus_found()
        key.close()

    @model_task
    def scan_for_virus(self):
        if (g.clamav_enabled):
            try:
                cns = pyclamd.ClamdNetworkSocket(g.clamav_host, g.clamav_port)
                if cns.ping():
                    try:
                        if self.is_zip():
                            try:
                                self._scan_zip(cns)
                            except RuntimeError:
                                # The file must have been encrypted
                                self._scan_file(cns)
                        else:
                            self._scan_file(cns)
                    except Exception as e:
                        self.virus_scanner_error(e)
                else:
                    self.virus_scanner_error(
                        ClamAVDown('ClamAV could not be pinged'))
            except pyclamd.ConnectionError:
                self.virus_scanner_error(
                    ClamAVDown('ClamAV could not be reached'))
        else:
            self.virus_scanner_error(
                ClamAVDisabled('ClamAV is not enabled'))
