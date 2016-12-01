# -*- coding: utf-8 -*-

"""
controllers

@summary: controllers

@author: U{tannern<tannern@gmail.com>}
"""
import urllib
import os
import logging
import hashlib
import simplejson
import pymongo
import re

from tg import expose, request, flash, redirect, validate
from tg.controllers import RestController, TGController
from pylons import app_globals as g, tmpl_context as c
from markupsafe import Markup

from vulcanforge.common import helpers as h
from vulcanforge.common.app import DefaultLogController
from vulcanforge.common.controllers import BaseController, BaseTGController
from vulcanforge.common.helpers import urlquote
from vulcanforge.common.util.http import (
    set_cache_headers,
    set_download_headers,
    raise_400
)
from vulcanforge.common.util.datatable import DATATABLE_SCHEMA

from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.common import exceptions as exc
from vulcanforge.artifact.widgets import RelatedArtifactsWidget, \
    ArtifactMenuBar
from vulcanforge.artifact.model import LogEntry

from vulcanforge.tools.downloads import model as FDM
from vulcanforge.tools.downloads import get_resource_path
from vulcanforge.tools.downloads.decorators import log_access

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:tools/downloads/templates/'
# Added space to this list even though it is not URL safe
URL_SAFE_REGEX = re.compile("^[0-9a-zA-Z\$\-\_\.\+\!\*\'\(\)\, ]+$")


class FileController(BaseTGController):

    class Widgets(BaseTGController.Widgets):
        related_artifacts = RelatedArtifactsWidget()
        menu_bar = ArtifactMenuBar()

    @expose(TEMPLATE_DIR + 'access_log.html')
    def access_log(self, *args, **kwargs):
        file_path = get_resource_path().split('/access_log')[0]
        fd_file = FDM.ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=file_path,
            deleted=False
        )
        if fd_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')

        g.security.require_access(fd_file, 'read')
        c.menu_bar = self.Widgets.menu_bar
        c.related_artifacts_widget = self.Widgets.related_artifacts

        data_url = "/rest{}content/log_data?path={}".format(
            c.app.config.url(),
            urlquote(fd_file.item_key)
        )

        content_root_path = c.app.url + 'content'

        return dict(
            hide_sidebar=False,
            fd_file=fd_file,
            file_path=file_path,
            data_url=data_url,
            content_root=content_root_path
        )


    @expose(TEMPLATE_DIR + 'file.html')
    @log_access('view')
    def _default(self, *args, **kwargs):
        file_path = get_resource_path()
        fd_file = FDM.ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=file_path,
            deleted=False
        )
        if fd_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')

        c.menu_bar = self.Widgets.menu_bar
        c.related_artifacts_widget = self.Widgets.related_artifacts
        rendered_file = g.visualize_artifact(fd_file).full_render(
            on_unvisualizable=lambda fd: redirect(fd_file.raw_url()))

        return dict(
            hide_sidebar=False,
            fd_file=fd_file,
            file_path=file_path,
            editable=g.security.has_access(c.app, 'write'),
            rendered_file=rendered_file)


class ZipFileController(BaseTGController):

    class Widgets(BaseTGController.Widgets):
        related_artifacts = RelatedArtifactsWidget()
        menu_bar = ArtifactMenuBar()

    @expose(TEMPLATE_DIR + 'file.html')
    @log_access('view')
    def _default(self, *args, **kwargs):
        file_path = get_resource_path()
        zip_path = file_path.split('.zip')[0] + '.zip'
        inner_path = file_path.split('.zip')[1]

        zip_file = FDM.ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=zip_path,
            deleted=False
        )
        if zip_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')

        zip_contained_file = FDM.ZipContainedFile.upsert(zip_file._id, inner_path)

        c.menu_bar = self.Widgets.menu_bar
        c.related_artifacts_widget = self.Widgets.related_artifacts
        rendered_file = g.visualize_artifact(zip_contained_file).full_render(
            on_unvisualizable=lambda fd: redirect(zip_contained_file.raw_url()))

        return dict(
            hide_sidebar=False,
            fd_file=zip_contained_file,
            file_path=file_path,
            editable=False,
            rendered_file=rendered_file)


class TreeController(TGController):

    class Widgets(BaseTGController.Widgets):
        related_artifacts = RelatedArtifactsWidget()

    @expose(TEMPLATE_DIR + 'tree.html')
    def _default(self, *args, **kwargs):
        folder_path = get_resource_path()

        fd_folder = FDM.ForgeDownloadsDirectory.query.get(
            app_config_id=c.app.config._id,
            item_key=folder_path
        )
        if fd_folder is None:
            # It might be a zip file or zip folder
            if ".zip" not in request.url:
                raise exc.AJAXNotFound('The requested folder does not exist.')
            else:
                zip_path = folder_path.split('.zip')[0] + '.zip'
                inner_path = folder_path.split('.zip')[1]
                zip_file = FDM.ForgeDownloadsFile.query.get(
                    app_config_id=c.app.config._id,
                    item_key=zip_path,
                    deleted=False
                )
                if zip_file is None:
                    raise exc.AJAXNotFound('The requested file does not exist.')
                else:
                    initial_path = zip_file.item_key + inner_path
        else:
            initial_path = fd_folder.item_key

        content_root_path = c.app.url + 'content'
        resumable_path = "/rest{}resumable".format(c.app.config.url())
        c.related_artifacts_widget = self.Widgets.related_artifacts
        return dict(
            hide_sidebar=False,
            initial_path=initial_path,
            editable=g.security.has_access(c.app, 'write'),
            content_root_path=content_root_path,
            resumable_path=resumable_path
        )


class ContentController(TGController):

    @expose()
    def _lookup(self, next=None, *rest):
        is_folder = request.url.endswith('/')
        path_last = request.url.split('/')[-1]
        if next is None:
            params = list(rest)
        else:
            params = [next] + list(rest)

        # Handle access_log routing
        if next is not None and 'access_log' == params[-1]:
            return FileController(), ['access_log']

        if next is not None and not is_folder:
            if ".zip" in request.url:
                if request.url.endswith('.zip'):
                    # we need to redirect because we clearly want to show ZIP content
                    # in this context
                    redirect(urllib.unquote(request.url) + '/')
                return ZipFileController(), params
            else:
                return FileController(), params

        return TreeController(), params


class ForgeDownloadsRootController(BaseController):

    content = ContentController()
    log = DefaultLogController(url_prefix_to_ignore="content")

    def _check_security(self):
        LogEntry.insert(access_denied_only=True)
        g.security.require_access(c.app.config, "read")

    @expose()
    def index(self):
        redirect('./content/')


class ContentRestController(RestController):

    _custom_actions = ['log_data']

    _log_table_columns = [
        {
            "sTitle": "Access time",
            "mongo_field": "timestamp"
        },
        {
            "sTitle": "User",
            "mongo_field": "display_name"
        },
        {
            "sTitle": "Access type",
            "mongo_field": "access_type"
        },
        {
            "sTitle": "Access denied",
            "mongo_field": "access_denied"
        },
        {
            "sTitle": "Additional information",
            "mongo_field": "extra_information",
            "bSortable": False
        }
    ]

    @expose('json')
    def post(self, *args, **kwargs):
        g.security.require_access(c.app, 'write')

        path = get_resource_path()

        if ".zip" in path:
            raise exc.AJAXForbidden(
                "Adding files to a ZIP archive is not supported yet.")

        if kwargs.has_key('resumableFilename'):
            resumableFilename = kwargs.get('resumableFilename')
            resumableTotalSize = int(kwargs.get('resumableTotalSize', 0))
            resumableChunkSize = int(kwargs.get('resumableChunkSize', g.multipart_chunk_size))
            resumableIdentifier = kwargs.get('resumableIdentifier', '')
            resumableChunkNumber = int(kwargs.get('resumableChunkNumber', 1))
            resumableCurrentChunkSize = int(kwargs.get('resumableCurrentChunkSize', 0))
            forceReplace = bool(kwargs.get('forceReplace', False))

            if g.multipart_chunk_size != long(resumableChunkSize):
                raise exc.AJAXBadRequest(
                    'The chunk size does not match with the supported: ' +
                    str(g.multipart_chunk_size))

            if not kwargs.has_key('file'):
                downloads_file = FDM.ForgeDownloadsFile.query.get(
                    app_config_id=c.app.config._id,
                    filename=resumableFilename,
                    container_key=path,
                    deleted=False
                )
                if downloads_file is not None:
                    if downloads_file.filesize == resumableTotalSize and \
                        downloads_file.md5_signature == resumableIdentifier and \
                        downloads_file.upload_completed:

                        raise exc.AJAXFound('File already exists')

                    if downloads_file.filesize != resumableTotalSize or \
                       downloads_file.md5_signature != resumableIdentifier:

                        if forceReplace:
                            downloads_file.delete(notify=False)
                        else:
                            raise exc.AJAXFound('File with different content exists')

                FDM.ForgeDownloadsFile.upsert(
                    filename=resumableFilename,
                    container_key=path,
                    filesize=resumableTotalSize,
                    upload_completed=False,
                    md5_signature=resumableIdentifier
                )
            else:
                downloads_file = FDM.ForgeDownloadsFile.query.get(
                    app_config_id=c.app.config._id,
                    filename=resumableFilename,
                    container_key=path,
                    filesize=resumableTotalSize,
                    upload_completed=False,
                    deleted=False,
                    md5_signature=resumableIdentifier
                )
                if downloads_file:
                    downloads_file.add_file_part(
                        kwargs['file'].file,
                        resumableChunkNumber,
                        resumableCurrentChunkSize
                    )
                    if downloads_file.upload_completed:
                        downloads_file.notify_create()
                        flash('Added %s' % resumableFilename, 'success')

        elif kwargs.has_key('folder'):
            folder_name = kwargs['folder'].strip('/')

            if folder_name == '':
                raise exc.AJAXBadRequest('Empty folder names are not supported')

            if not URL_SAFE_REGEX.match(folder_name):
                raise exc.AJAXBadRequest('Folder name contains unsupported characters')

            item_key = path + folder_name + '/'
            folder_object = FDM.ForgeDownloadsDirectory.query.get(
                app_config_id=c.app.config._id,
                item_key=item_key
            )
            if folder_object is not None:
                raise exc.AJAXFound('Folder already exists')

            new_folder = FDM.ForgeDownloadsDirectory(
                app_config_id=c.app.config._id,
                container_key=path,
                item_key=item_key,
                filename=folder_name
            )
            new_folder.notify_create()
            flash('Added %s' % folder_name, 'success')

    @expose('json')
    def put(self, *args, **kwargs):
        g.security.require_access(c.app, 'write')

        folder_path = get_resource_path()
        fd_folder = FDM.ForgeDownloadsDirectory.query.get(
            app_config_id=c.app.config._id,
            item_key=folder_path
        )
        if fd_folder is None:
            raise exc.AJAXNotFound('The requested folder does not exist.')


        if kwargs['command'] == 'move_files':
            file_paths = simplejson.loads(kwargs['file_paths'])
            for file_path in file_paths:
                # Fixing the path for ZIPs
                # This is not really nice
                if file_path.endswith(".zip/"):
                    file_path = file_path[:-1]

                downloads_file = FDM.ForgeDownloadsFile.query.get(
                    app_config_id=c.app.config._id,
                    item_key=file_path,
                    deleted=False
                )
                if downloads_file is not None and downloads_file.upload_completed:
                    path_parts = file_path.split('/')
                    downloads_file.item_key = folder_path + path_parts[-1]
                    downloads_file.container_key = folder_path

                    FDM.ForgeDownloadsLogEntry.insert(
                        'move',
                        extra_information={'moved_to': folder_path},
                        downloads_obj=downloads_file
                    )

    def _get_file_or_404(self):
        path = get_resource_path()
        downloads_file = FDM.ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=path,
            deleted=False
        )

        if downloads_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')

        return downloads_file

    def _resumable_get(self, *args, **kwargs):
        g.security.require_access(c.app, 'write')

        resumableFilename = kwargs.get('resumableFilename')
        resumableTotalSize = int(kwargs.get('resumableTotalSize'))
        resumableChunkSize = int(kwargs.get('resumableChunkSize'))
        resumableIdentifier = kwargs.get('resumableIdentifier', '')
        resumableChunkNumber = int(kwargs.get('resumableChunkNumber', 1))

        path = "".join([get_resource_path(), urllib.unquote(resumableFilename)])
        downloads_file = FDM.ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=path,
            filesize=resumableTotalSize,
            md5_signature=resumableIdentifier,
            deleted=False
        )

        if downloads_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')

        if g.multipart_chunk_size != long(resumableChunkSize):
            raise exc.AJAXBadRequest(
                'The chunk size does not match with the supported: ' +
                str(g.multipart_chunk_size))

        if downloads_file.upload_completed:
            # We need to send a 200, because we already have this file
            return {}

        key = g.get_s3_key('', downloads_file)
        mp_upload = None
        for mp in key.bucket.list_multipart_uploads():
            if mp.key_name == key.name:
                mp_upload = mp
                break

        if mp_upload is None:
            raise exc.AJAXNotFound('The requested multipart file has no parts uploaded.')

        parts = mp_upload.get_all_parts(max_parts=1, part_number_marker=resumableChunkNumber-1)
        if not parts or parts[0].part_number != resumableChunkNumber:
            raise exc.AJAXNotFound('The requested chunk does not exist.')

        return {}

    def _file(self, *args, **kwargs):
        downloads_file = self._get_file_or_404()

        FDM.ForgeDownloadsLogEntry.insert('download')

        if g.s3_serve_local:
            set_download_headers(os.path.basename(downloads_file.item_key))
            set_cache_headers(expires_in=1)
            return iter(downloads_file.get_key())
        else:
            redirect(downloads_file.get_s3_temp_url())

    def _zip_file(self, *args, **kwargs):
        resource_path = get_resource_path()
        zip_path = resource_path.split('.zip')[0] + '.zip'
        inner_path = resource_path.split('.zip')[1]

        zip_file = FDM.ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=zip_path,
            deleted=False
        )
        if zip_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')

        FDM.ForgeDownloadsLogEntry.insert('download')

        file_hash = hashlib.sha1(inner_path).hexdigest()
        file_info = zip_file.zip_manifest.get(file_hash)
        if file_info is None:
            raise exc.AJAXNotFound()

        zip_contained_file = FDM.ZipContainedFile.upsert(zip_file._id, inner_path)
        set_download_headers(os.path.basename(file_info['filename']))
        set_cache_headers(expires_in=1)
        return zip_contained_file.read()

    def _exchange_info(self):
        file_xcng_info, folder_xcng_info = [], []
        file_exchanges = g.exchange_manager.get_exchanges(
            c.app.config, FDM.ForgeDownloadsFile)
        for xcng, artifact_config in file_exchanges:
            file_xcng_info.append({
                "label": "Share in {}".format(xcng.config["name"]),
                "icon": artifact_config.get('publish_icon', 'ico-share'),
                "base_url": artifact_config.get("publish_url")
            })
        folder_exchanges = g.exchange_manager.get_exchanges(
            c.app.config, FDM.ForgeDownloadsDirectory)
        for xcng, artifact_config in folder_exchanges:
            folder_xcng_info.append({
                "label": "Share in {}".format(xcng.config["name"]),
                "icon": artifact_config.get('publish_icon', 'ico-share'),
                "base_url": artifact_config.get("publish_url")
            })
        return file_xcng_info, folder_xcng_info

    def _add_entry_data(self, entry, data, file_xcng_info, folder_xcng_info):
        path = entry.item_key
        if isinstance(entry, FDM.ForgeDownloadsFile) and entry.is_zip() and not path.endswith("/"):
            path += "/"
        if entry.is_scanned:
            href = "{}content{}".format(
                c.app.config.url(),
                urlquote(path)
            )
        else:
            href = ''
        download_url = "/rest{}content{}".format(
            c.app.config.url(),
            urlquote(entry.item_key)
        )
        access_log_url = "{}content{}/access_log".format(
            c.app.config.url(),
            urlquote(entry.item_key)
        )

        data[path] = {
            "name": h.really_unicode(entry.filename),
            "path": h.really_unicode(path),
            "href": href,
            "modified": entry.mod_date.isoformat(),
            "extra": {}
        }
        if isinstance(entry, FDM.ForgeDownloadsDirectory):
            data[path]['type'] = 'DIR'
            exchanges_info = folder_xcng_info
        elif isinstance(entry, FDM.ForgeDownloadsFile):
            data[path]['type'] = 'FILE'
            if entry.is_scanned:
                data[path]['downloadURL'] = download_url
            elif g.clamav_enabled:
                data[path]['virus_scan_status'] = entry.virus_scan_status

            data[path]['accessLogURL'] = access_log_url
            if entry.is_zip():
                data[path]['type'] = 'ZIP_FILE'

            data[path]['artifact'] = {
                'reference_id': entry.index_id(),
                'type': entry.type_s
            }
            data[path]['uploadCompleted'] = entry.upload_completed
            if not entry.upload_completed:
                data[path]['md5Signature'] = entry.md5_signature
                data[path]['uploadProgress'] = entry.upload_progress
                data[path]['partNumbers'] = entry.part_number_list

            exchanges_info = file_xcng_info

        if entry.is_scanned:
            exchanges = []
            for xcng_info in exchanges_info:
                xcng = xcng_info.copy()
                xcng['href'] = xcng.pop("base_url") +\
                               '?artifact_id={}'.format(entry._id)
                exchanges.append(xcng)
            data[path]['exchanges'] = exchanges

        icon_url = g.visualize_url(path).get_icon_url()
        if icon_url:
            data[path]['extra']['iconURL'] = icon_url

        if entry.filesize is not None:
            data[path]['extra']['size'] = h.pretty_print_file_size(
                entry.filesize)

        if entry.creator_id is not None:
            data[path]['extra']['creator'] = {
                "display_name": entry.creator.display_name,
                "url": entry.creator.url()
            }

    def _folder(self, *args, **kwargs):
        """
        Create a specially formatted dictionary for the filebrowser widget
        """
        resource_path = get_resource_path()

        folder_object = FDM.ForgeDownloadsDirectory.query.get(
            app_config_id=c.app.config._id,
            item_key=resource_path
        )
        if folder_object is None:
            raise exc.AJAXNotFound('The requested folder does not exist.')

        data = {}
        entries = folder_object.get_entries()
        if g.security.has_access(c.app, 'publish'):
            file_xcng_info, folder_xcng_info = self._exchange_info()
        else:
            file_xcng_info, folder_xcng_info = [], []

        for entry in entries:
            self._add_entry_data(entry, data, file_xcng_info, folder_xcng_info)

        return data

    def _zip_folder(self, *args, **kwargs):
        """
        """
        resource_path = get_resource_path()
        zip_path = resource_path.split('.zip')[0] + '.zip'

        data = {}

        def add_ancestors(path):
            parent_path = '/{}/'.format(os.path.dirname(path.lstrip('/').rstrip('/')))
            if not parent_path or parent_path == '//':
                return

            exposed_path = zip_path + parent_path
            if exposed_path in data:
                return

            href = "{}content{}".format(
                c.app.config.url(),
                urlquote(exposed_path)
            )

            data[exposed_path] = {
                'type': 'ZIP_DIR',
                'name': os.path.basename(os.path.dirname(exposed_path)),
                'path': exposed_path,
                'href': href,
                'extra': {}
            }
            add_ancestors(parent_path)


        zip_file = FDM.ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=zip_path,
            deleted=False
        )
        if zip_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')
        if g.security.has_access(c.app, 'publish'):
            file_xcng_info, folder_xcng_info = self._exchange_info()
        else:
            file_xcng_info, folder_xcng_info = [], []
        self._add_entry_data(zip_file, data, file_xcng_info, folder_xcng_info)

        zip_manifest = zip_file.extra_info.get('zip_manifest', {})
        for info in zip_manifest.values():
            path = '{}/{}'.format(zip_path, info['path'])
            href = "{}content{}".format(
                c.app.config.url(),
                urlquote(path)
            )
            download_url = "/rest{}content{}".format(
                c.app.config.url(),
                urlquote(path)
            )

            if path.endswith('/'):
                data[path] = {
                    'type': 'ZIP_DIR',
                    'name': info['filename'],
                    'path': path,
                    'href': href,
                    'extra': {}
                }
            else:
                data[path] = {
                    'type': 'ZIP_CONTAINED_FILE',
                    'name': h.really_unicode(info['filename']),
                    'path': h.really_unicode(path),
                    'href': href,
                    'downloadURL': download_url,
                    'extra': {
                        'size': h.pretty_print_file_size(info['file_size']),
                        'actions': Markup((
                            '<a class="ico-download icon"'
                            'title="Download"'
                            'href="{}"></a>'
                            ).format('download_url'))
                    }
                }
                icon_url = g.visualize_url(path).get_icon_url()
                if icon_url:
                    data[path]['extra']['iconURL'] = icon_url
                if zip_file.creator_id is not None:
                    data[path]['extra']['creator'] = {
                        "display_name": zip_file.creator.display_name,
                        "url": zip_file.creator.url()
                    }

            add_ancestors(info['path'])

        return data

    @expose('json')
    @log_access('view', access_denied_only=True)
    def get_one(self, *args, **kwargs):
        g.security.require_access(c.app, 'read')
        if kwargs.has_key('resumableFilename'):
            return self._resumable_get(*args, **kwargs)

        if '.zip/' in request.url:
            if request.url.endswith('/'):
                return self._zip_folder(*args)
            else:
                return self._zip_file(*args, **kwargs)
        else:
            if request.url.endswith('/'):
                return self._folder(*args)
            else:
                return self._file(*args, **kwargs)

    @expose('json')
    @log_access('delete')
    def post_delete(self, *args, **kwargs):
        """

        @param property_id:
        @param kwargs:
        @return:
        """
        g.security.require_access(c.app, 'write')
        path = get_resource_path()

        # Fixing the path for ZIPs
        # This is not really nice
        if path.endswith(".zip/"):
            path = path[:-1]

        if path.endswith('/'):
            file_type = 'folder'
            folder_object = FDM.ForgeDownloadsDirectory.query.get(
                app_config_id=c.app.config._id,
                item_key=path
            )
            if folder_object is None:
                raise exc.AJAXNotFound('The requested folder does not exist.')
            folder_object.delete()
            file_name = folder_object.filename
        else:
            file_type = 'file'
            file_object = FDM.ForgeDownloadsFile.query.get(
                app_config_id=c.app.config._id,
                item_key=path,
                deleted=False
            )
            if file_object is None:
                raise exc.AJAXNotFound('The requested file does not exist.')
            file_object.delete()
            file_name = file_object.filename

        ret_dict = dict(success=True)
        flash('Deleted %s %s' % (file_type, file_name), 'success')
        return ret_dict

    @expose('json', render_params={"sanitize": False})
    @validate(DATATABLE_SCHEMA, error_handler=raise_400)
    def log_data(self, **kwargs):
        g.security.require_access(c.app, 'read')

        file_path = urllib.unquote(kwargs.get('path', ''))
        fd_file = FDM.ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=file_path
        )
        if fd_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')

        # assemble the query
        db, coll = pymongo_db_collection(FDM.ForgeDownloadsLogEntry)

        query_dict = {'artifact_id': fd_file._id}
        total = coll.find(query_dict).count()
        pipeline = [
            {'$match': query_dict}
        ]
        if kwargs.get('iSortingCols', 0) > 0:
            sort_column = int(kwargs['iSortCol_0'])
            sort_dir_str = kwargs['sSortDir_0']
            field_name = self._log_table_columns[sort_column]['mongo_field']
            sort_dir = pymongo.ASCENDING
            if sort_dir_str.lower() == 'desc':
                sort_dir = pymongo.DESCENDING
            pipeline.append({'$sort': {field_name: sort_dir}})
        pipeline.append({'$skip' : kwargs.get('iDisplayStart', 0)})
        pipeline.append({'$limit' : kwargs.get('iDisplayLength', 50)})

        aggregate = coll.aggregate(pipeline)

        # format the data
        data = []
        for log_entry in aggregate['result']:
            row = [
                log_entry['timestamp'].strftime('%m/%d/%Y %H:%M:%S UTC'),
                Markup('<a href="/u/{}">{}</a>'.format(
                    log_entry['username'], log_entry['display_name'])),
                log_entry['access_type'],
                log_entry.get('access_denied', False)
            ]
            if log_entry['extra_information'] is None:
                row.append('')
            else:
                row.append(simplejson.dumps(log_entry['extra_information']))

            data.append(row)

        response = {
            'iTotalRecords': total,
            'iTotalDisplayRecords': total,
            'sEcho': kwargs.get('sEcho', 0),
            'aaData': data
        }
        return response

class ForgeDownloadsRestController(TGController):
    content = ContentRestController()

