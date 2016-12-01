# -*- coding: utf-8 -*-

"""
models

@summary: models

@author: U{tannern<tannern@gmail.com>}
"""
import os
import math
import posixpath
import logging
import hashlib
import jinja2

from datetime import datetime

from ming import schema as S
from ming.odm import session, FieldProperty, ForeignIdProperty, RelationProperty
from ming.utils import LazyProperty

from boto.s3.multipart import MultiPartUpload
from boto.s3.keyfile import KeyFile

from pylons import app_globals as g, tmpl_context as c, request
from vulcanforge.common.helpers import urlquote
from vulcanforge.common import exceptions as exc
from vulcanforge.common.util import \
    set_download_headers, \
    set_cache_headers, \
    get_client_ip
from vulcanforge.common.util.filesystem import guess_mime_type
from vulcanforge.common import helpers as h

from vulcanforge.exchange.model import ExchangeNode
from vulcanforge.artifact.model import LogEntry
from vulcanforge.common.model.session import visualizable_artifact_session
from vulcanforge.common.lib import zipfile
from vulcanforge.auth.model import User
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.artifact.model import VisualizableArtifact
from vulcanforge.exchange.model import ExchangeableArtifact
from vulcanforge.visualize.model import ProcessedArtifactFile
from vulcanforge.visualize.tasks import visualizable_task
from vulcanforge.virusscan.model import S3VirusScannableMixin

from vulcanforge.notification.model import Notification

from tasks import delete_content_from_s3

from . import get_resource_path

TEMPLATE_DIR = 'vulcanforge.tools.downloads.templates'
LOG = logging.getLogger(__name__)


class ForgeDownloadsAbstractItem(ExchangeableArtifact):

    type_s = 'ForgeDownloadsAbstractItem'
    item_key = FieldProperty(str)
    container_key = FieldProperty(str, if_missing=None)
    filename = FieldProperty(str, if_missing='')
    filesize = FieldProperty(int, if_missing=None)
    deleted = FieldProperty(bool, if_missing=False)
    creator_id = ForeignIdProperty(User, if_missing=None)
    creator = RelationProperty(User)

    def __init__(self, **kw):
        super(ForgeDownloadsAbstractItem, self).__init__(**kw)
        if self.creator_id is None:
            self.creator_id = c.user._id

    def url(self):
        return self.app_config.url() + 'content' + urlquote(self.item_key)

    def parent_url(self):
        return posixpath.dirname(self.url().rstrip('/')) + '/'

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

    @LazyProperty
    def is_scanned(self):
        return True


class ForgeDownloadsFile(ForgeDownloadsAbstractItem,
                         VisualizableArtifact,
                         S3VirusScannableMixin):

    class __mongometa__:
        name = 'forgedownloads_file'
        session = visualizable_artifact_session
        indexes = [
            'mod_date',
            ('app_config_id', 'item_key'),
            ('app_config_id', 'container_key'),
            ('app_config_id', 'deleted'),
            ('app_config_id', 'deleted', '_id')
        ]

    type_s = 'ForgeDownloadsFile'
    visualizable_kind = 'downloads_file'

    # Used for large files to support the resume operation
    md5_signature = FieldProperty(str, if_missing='')
    upload_completed = FieldProperty(bool, if_missing=True)
    mp_upload_id = FieldProperty(str, if_missing=None)
    extra_info = FieldProperty(None, if_missing={})

    # Virus scan status
    # Partially scanned is used because of limitations these files are assumed
    # safe but not with 100% certainty
    virus_scan_status = FieldProperty(
        S.OneOf('unscanned', 'failed', 'partially_scanned', 'passed',
                if_missing='unscanned'))
    virus_scan_date = FieldProperty(datetime, if_missing=None)

    def shorthand_id(self):
        return self.item_key

    @property
    def name(self):
        return self.title_s

    @property
    def title_s(self):
        return self.filename

    def email_template(self):
        template_loader = jinja2.Environment(
            loader=jinja2.PackageLoader(TEMPLATE_DIR, 'email'))
        return template_loader.get_template('File.txt')

    # CUD notifications
    def notify_create(self):
        subject = '{} was added'.format(self.title_s)
        text = "{} added {}".format(c.user.display_name, self.filename)
        Notification.post(self, "metadata", text=text, subject=subject)

    def notify_update(self):
        subject = '{} was modified'.format(self.title_s)
        text = "{} modified {}".format(c.user.display_name, self.filename)
        Notification.post(self, "metadata", text=text, subject=subject)

    def notify_delete(self):
        subject = '{} was deleted'.format(self.title_s)
        text = "{} deleted {}".format(c.user.display_name, self.filename)
        Notification.post(self, "metadata", text=text, subject=subject,
                          link=self.parent_url())

    def raw_url(self):
        return '/rest' + self.url()

    def local_url(self):
        return '/s3_proxy/{}/{}'.format(
            g.s3_bucket.name,
            g.make_s3_keyname('', self))

    def get_s3_temp_url(self):
        key = self.get_key()
        safe_name = self.filename.encode('utf-8')
        disposition = 'attachment; filename="{}"'.format(safe_name)
        content_type = guess_mime_type(self.filename).encode('utf-8')
        return key.generate_url(
            g.s3_url_expires_in,
            query_auth=True,
            response_headers={
                'response-content-disposition': disposition,
                'response-content-type': content_type
            }
        )

    @classmethod
    def upsert(cls,
               container_key='/',
               filename='',
               filesize=0,
               upload_completed=False,
               md5_signature=''):

        item_key = container_key + filename
        item = cls.query.get(
            app_config_id=c.app.config._id,
            item_key=item_key,
            md5_signature=md5_signature,
            deleted=False,
            upload_completed=upload_completed,
            filesize=filesize
        )

        if item is None:
            item = cls(
                app_config_id=c.app.config._id,
                item_key=item_key,
                container_key=container_key,
                filename=filename,
                md5_signature=md5_signature,
                deleted=False,
                upload_completed=upload_completed,
                filesize=filesize
            )
            ForgeDownloadsLogEntry.insert('create', downloads_obj=item)

        multipart = False
        if filesize > g.multipart_chunk_size:
            multipart = True

        if multipart and item.mp_upload_id is None:
            key = g.get_s3_key('', item)
            for mp in key.bucket.list_multipart_uploads():
                if mp.key_name == key.name:
                    item.mp_upload_id = mp.id
                    break

            if item.mp_upload_id is None:
                try:
                    mp = key.bucket.initiate_multipart_upload(
                        key.name, encrypt_key=g.s3_encryption)
                    item.mp_upload_id = mp.id
                except:
                    raise exc.AJAXMethodNotAllowed(
                        'This platform does not support multipart uploads.')

        item.flush_self()
        return item

    @LazyProperty
    def multipart(self):
        mp = MultiPartUpload(self.get_key().bucket)
        mp.key_name = self.get_key().name
        mp.id = self.mp_upload_id
        mp.encrypted = g.s3_encryption

        return mp

    @LazyProperty
    def pretty_size(self):
        return h.pretty_print_file_size(self.filesize)

    def is_zip(self):
        return self.filename.endswith('.zip')

    @LazyProperty
    def zip_manifest(self):
        return self.extra_info.get('zip_manifest', {})

    @LazyProperty
    def zip_file(self):
        if self.is_zip():
            zip_fp = KeyFile(self.get_key())
            return zipfile.ZipFile(zip_fp)

    def _populate_zip_manifest(self):
        try:
            zip_manifest = {}
            smallest_entry = None
            extra_info = self.extra_info or {}

            for zipinfo in self.zip_file.filelist:
                file_path = zipinfo.filename
                if not file_path.startswith('/'):
                    file_path = "/" + file_path
                key = hashlib.sha1(file_path).hexdigest()
                zip_manifest[key] = {
                    'filename': os.path.basename(zipinfo.filename.rstrip('/')),
                    'path': zipinfo.filename,
                    'offset': zipinfo.header_offset + len(zipinfo.FileHeader()),
                    'compressed_size': zipinfo.compress_size,
                    'file_size': zipinfo.file_size,
                    'timestamp': datetime(*zipinfo.date_time),
                    'compress_type': zipinfo.compress_type
                }
                if zipinfo.file_size > 0 and (
                    smallest_entry is None or smallest_entry['compressed_size'] > zipinfo.compress_size):

                    smallest_entry = zip_manifest[key]

            extra_info['zip_manifest'] = zip_manifest

        except:
            return

        self.extra_info = extra_info

    def _complete_hook(self):
        self.upload_completed = True
        if self.is_zip():
            self._populate_zip_manifest()
        self.flush_self()
        if (g.clamav_enabled):
            self.scan_for_virus.post(
                taskd_priority=g.clamav_task_priority)

    def add_file_part(self,
                         file_part,
                         resumableChunkNumber=1,
                         resumableCurrentChunkSize=0,
                         notify=True):

        chunk_count = int(math.ceil(self.filesize / float(g.multipart_chunk_size)))
        if int(resumableChunkNumber) > chunk_count:
            raise exc.AJAXMethodNotAllowed('Chunk number is out of bounds.')

        key = self.get_key()
        if self.filesize <= g.multipart_chunk_size:
            key.set_contents_from_file(file_part, encrypt_key=g.s3_encryption)
            self._complete_hook()
            ForgeDownloadsLogEntry.insert('completed upload', downloads_obj=self)
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
            self._complete_hook()
            ForgeDownloadsLogEntry.insert('completed upload', downloads_obj=self)
            if notify:
                self.notify_create()

    @property
    def upload_progress(self):
        chunk_count = int(math.ceil(self.filesize / float(g.multipart_chunk_size)))
        return float(len(self.part_number_list))/chunk_count

    @LazyProperty
    def part_number_list(self):
        part_list = self.multipart.get_all_parts()
        part_numbers = []
        if part_list is not None:
            part_numbers = [p.part_number for p in part_list]
        return part_numbers

    def get_key(self):
        return g.get_s3_key('', self)

    def delete(self, notify=True):
        if notify:
            self.notify_delete()

        delete_content_from_s3.post(self._id)

        #super(ForgeDownloadsFile, self).delete()
        # We want to keep this entry around but definitely want to unpublish:
        exchange_nodes = ExchangeNode.find_from_artifact(self).all()
        for exchange_node in exchange_nodes:
            exchange_node.unpublish()

        if self.is_zip():
            for zcf in ZipContainedFile.query.find({'container_id':self._id}):
                zcf.delete()

        self.deleted = True

    def read(self):
        return self.get_key().read()

    def get_content_to_folder(self, path):
        filename = os.path.basename(self.filename)
        full_path = os.path.join(path, filename)
        with open(full_path, 'w') as fp:
            self.get_key().get_contents_to_file(fp)
        return filename

    def index(self, **kwargs):
        index = kwargs
        base, ext = os.path.splitext(self.filename)
        basename = base.split('/')[-1]
        filename_with_ext = os.path.split(self.filename)[-1]
        text_objects = [basename, filename_with_ext]
        visualize = g.visualize_artifact(self)
        visualizers = visualize.find_visualizers()
        for visualizer in visualizers:
            try:
                text_content = visualizer.text_content(self)
            except:
                text_content = None
            if text_content:
                text_objects.append(text_content)

        index['text_objects'] = text_objects
        index['deleted_b'] = self.deleted

        return super(ForgeDownloadsFile, self).index(**index)

    @visualizable_task
    def trigger_vis_upload_hook(self):
        if self.upload_completed and not self.deleted:
            super(ForgeDownloadsFile, self).trigger_vis_upload_hook()

    def publish_hook(self, **kwargs):
        scope = kwargs.get('scope', 'public')
        extra_info = {}
        extra_info['scope'] = scope
        extra_info['replace_existing'] = kwargs.get('replace_existing', False)
        if kwargs.has_key('share_projects') and scope == 'project':
            projects = []
            for project in kwargs.get('share_projects',[]):
                projects.append(project.name)

            extra_info['projects'] = projects
        if kwargs.has_key('share_neighborhoods') and scope == 'neighborhood':
            neighborhoods = []
            for nbhd_id in kwargs.get('share_neighborhoods', []):
                nbhd = Neighborhood.query.get(_id=nbhd_id)
                neighborhoods.append(nbhd.name)

            extra_info['neighborhoods'] = neighborhoods
        ForgeDownloadsLogEntry.insert('publish', extra_information=extra_info, downloads_obj=self)

    def unpublish_hook(self, **kwargs):
        ForgeDownloadsLogEntry.insert('unpublish', downloads_obj=self)

    def view_hook(self, **kwargs):
        ForgeDownloadsLogEntry.insert('exchange view', downloads_obj=self)

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
        ForgeDownloadsLogEntry.insert('delete', downloads_obj=self,
                     extra_information={'reason': 'Virus was detected'})
        self.notify_virus_found()

    def virus_scanner_error(self, error):
        LOG.error(error)


class ZipContainedFile(VisualizableArtifact):
    class __mongometa__:
        name = 'forgedownloads_zip_contained_file'
        indexes = [
            'mod_date',
            ('app_config_id', 'item_key'),
            ('app_config_id', 'container_key')
        ]

    type_s = 'ZipContainedFile'
    visualizable_kind = 'zip_contained_file'

    container_id = FieldProperty(S.ObjectId, if_missing=None)
    filepath = FieldProperty(str, if_missing='')

    def __init__(self, container_id, filepath):
        self.container_id = container_id
        self.filepath = filepath

        if self.file_info is None:
            raise exc.AJAXNotFound()

    @classmethod
    def upsert(cls, container_id, filepath):
        z_file = ZipContainedFile.query.get(
            app_config_id=c.app.config._id,
            container_id=container_id,
            filepath=filepath)

        if z_file is None:
            z_file = ZipContainedFile(container_id, filepath)
            session(z_file).flush()

        return z_file

    def index(self, **kwargs):
        return False

    def read(self):
        zip_file = self.container.zip_file

        try:
            zinfo = zip_file.getinfo(self.filepath)
        except KeyError:
            zinfo = zip_file.getinfo(self.filepath[1:])

        return zip_file.open(zinfo).read()

    def serve(self, *args, **kwargs):
        """
        Sets the response headers and serves as a wsgi iter

        NOTE: it is generally better to provide a url directly to the s3 key
        (via the url method) than serving via this method

        """
        set_download_headers(self.filename)
        # enable caching
        set_cache_headers(self._id.generation_time)
        return self.read()

    @LazyProperty
    def container(self):
        return ForgeDownloadsFile.query.get(_id=self.container_id)

    @LazyProperty
    def filepath_hash(self):
        return hashlib.sha1(self.filepath).hexdigest()

    @LazyProperty
    def file_info(self):
        return self.container.zip_manifest.get(self.filepath_hash)

    @property
    def filename(self):
        return self.file_info["filename"]

    @property
    def _id(self):
        return self.filepath_hash

    def url(self):
        return '{}{}'.format(
            self.container.url(),
            self.filepath
        )

    def raw_url(self):
        return '/rest{}{}'.format(
            self.container.url(),
            self.filepath
        )

    def local_url(self):
        return self.raw_url()

    def delete(self):
        processed_files = ProcessedArtifactFile.query.find(
            {"unique_id": self.get_unique_id()}
        )

        for p_file in processed_files:
            p_file.delete()

        super(ZipContainedFile, self).delete()


class ForgeDownloadsDirectory(ForgeDownloadsAbstractItem):

    class __mongometa__:
        name = 'forgedownloads_directory'
        indexes = [
            'mod_date',
            ('app_config_id', 'item_key'),
            ('app_config_id', 'container_key')
        ]

    type_s = 'ForgeDownloadsDirectory'

    @property
    def title_s(self):
        return 'Folder ' + self.filename

    def index(self, *args, **kwargs):
        return False

    def child_resources(self, uploaded=True):
        file_resources = ForgeDownloadsFile.query.find({
            'app_config_id': self.app_config_id,
            'container_key': self.item_key,
            'deleted': {'$ne' : True }#,
            #'upload_completed': {'$ne' : not uploaded }
        }).all()
        folder_resources = ForgeDownloadsDirectory.query.find({
            'app_config_id': self.app_config_id,
            'container_key': self.item_key,
            'deleted': {'$ne' : True }
        }).all()
        return file_resources + folder_resources

    def get_entries(self, uploaded=True):
        entries = self.child_resources(uploaded)
        entries.append(self)
        return entries

    def delete(self, notify=True):
        self.deleted = True
        self.flush_self()
        file_resources = ForgeDownloadsFile.query.find({
            'app_config_id': self.app_config_id,
            'container_key': self.item_key
        }).all()
        for file_resource in file_resources:
            file_resource.delete(notify=False)

        folder_resources = ForgeDownloadsDirectory.query.find({
            'app_config_id': self.app_config_id,
            'container_key': self.item_key
        }).all()
        for folder_resource in folder_resources:
            folder_resource.delete(notify=False)
        if notify:
            self.notify_delete()

        super(ForgeDownloadsDirectory, self).delete()

    def email_template(self):
        template_loader = jinja2.Environment(
            loader=jinja2.PackageLoader(TEMPLATE_DIR, 'email'))
        return template_loader.get_template('Folder.txt')


class ForgeDownloadsLogEntry(LogEntry):

    @classmethod
    def _get_downloads_object(cls):
        file_path = get_resource_path()
        extra_information = {}
        if ".zip" in file_path:
            inner_path = file_path.split('.zip')[1]
            file_path = file_path.split('.zip')[0] + '.zip'

            extra_information["file_within_zip"] = inner_path

        downloads_obj = ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=file_path,
            deleted=False)

        if downloads_obj is None:
            downloads_obj = ForgeDownloadsDirectory.query.get(
                app_config_id=c.app.config._id,
                item_key=file_path,
                deleted=False)

        return downloads_obj, extra_information

    @classmethod
    def insert(cls, access_type='', permission_needed="read", extra_information=None, downloads_obj=None, access_denied_only=False):
        if extra_information is None:
            extra_information = {}

        if downloads_obj is None:
            downloads_obj, extra = cls._get_downloads_object()
            extra_information.update(extra)

        if downloads_obj:
            access_denied = not g.security.has_access(downloads_obj, permission_needed)

            if access_denied_only and not access_denied:
                return

            ip_address = get_client_ip() or '0.0.0.0'

            data = dict(
                project_id=downloads_obj.project._id,
                app_config_id=downloads_obj.app_config_id,
                artifact_id=downloads_obj._id,
                user_id=c.user._id,
                username=c.user.username,
                display_name=c.user.get_pref('display_name'),
                logged_ip=ip_address,
                timestamp=datetime.utcnow(),
                access_type=access_type,
                extra_information=extra_information,
                access_denied=access_denied,
                url=request.url
            )

            log_entry = ForgeDownloadsLogEntry(**data)
            log_entry.flush_self()

            return log_entry
