import logging
import urllib
import os
import bson
import simplejson

from markupsafe import Markup
from tg import expose, request, redirect, validate, flash, response
from tg.controllers import RestController
from pylons import app_globals as g, tmpl_context as c
from ming.odm import ThreadLocalODMSession

from vulcanforge.common.controllers.decorators import require_post
from vulcanforge.common import helpers as h
from vulcanforge.common import exceptions as exc
from vulcanforge.common.widgets.form_fields import MarkdownEdit
from vulcanforge.common.exceptions import (
    AJAXServerError,
    AJAXNotFound,
    AJAXForbidden
)
from vulcanforge.common.util.datatable import DATATABLE_SCHEMA
from vulcanforge.common.util.http import (
    set_cache_headers,
    set_download_headers,
    raise_400
)
from vulcanforge.common.util.filesystem import guess_mime_type, md5_signature

from vulcanforge.common.helpers import urlquote
from vulcanforge.artifact.widgets import RelatedArtifactsWidget

from . import _parse_solr_date
from vulcanforge.tools.catalogue.model import (
    VersionedItem,
    VersionedItemFolder,
    VersionedItemFile
)
LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:tools/catalogue/templates/'
CUSTOM_CONTENT_TYPE = 'CUSTOM/LEAVE'


def set_versioned_item(versioned_item_class, id_str):
    c.versioned_item = versioned_item_class.query.get(_id=bson.ObjectId(id_str))

    if c.versioned_item is None:
        raise AJAXNotFound(
            "No Item found with the \"{}\" identifier".format(
                id_str))

    if c.app is not None and c.versioned_item.app_config_id != c.app.config._id:
        raise AJAXForbidden("You do not have access to this item in this tool.")


class FileController(RestController):
    versioned_item_class = None
    mount_point = "versioned_item"

    def _get_resource_path(self):
        return urllib.unquote(
            request.url.split('files')[1]).split('?')[0]

    def _before(self, *args, **kwargs):
        item_id = request.url.split(self.mount_point+'/')[-1].split('/')[0]
        set_versioned_item(self.versioned_item_class, item_id)

    def __init__(self, versioned_item_class=None):
        self.mount_point = versioned_item_class.mount_point
        self.versioned_item_class = versioned_item_class

    def _set_file(self, id_str):
        c.file = VersionedItemFile.query.get(_id=bson.ObjectId(id_str))

        if c.file is None:
            raise AJAXNotFound(
                "No File found with the \"{}\" identifier".format(
                    id_str))

        if not c.file.container_keys.has_key(c.versioned_item.version_escaped):
            raise AJAXNotFound(
                "This version does not contain this file")

        if c.app is not None and c.file.app_config_id != c.app.config._id:
            raise AJAXForbidden(
                "You do not have access to this item in this tool.")

    def _file_content(self, download):
        response.content_type = guess_mime_type(c.file.filename)
        if download:
            response.headerlist.append((
                'Content-Disposition',
                'attachment;filename="{}"'.format(
                    c.file.filename)
            ))
            g.security.require_access(c.versioned_item, 'read')

        return c.file.read()

    @expose(content_type=CUSTOM_CONTENT_TYPE)
    def raw(self, id_str, **kwargs):
        """
        Compute requested path adding extension back in.
        Find manifest info for path.
        Get data for path from Object Store.

        keyword arguments:
            download: if present adds Content-Disposition header
        """
        self._set_file(id_str)
        return self._file_content(False)

    @expose(content_type=CUSTOM_CONTENT_TYPE)
    def download(self, id_str, **kwargs):
        """
        Compute requested path adding extension back in.
        Find manifest info for path.
        Get data for path from Object Store.

        keyword arguments:
            download: if present adds Content-Disposition header
        """
        g.security.require_access(c.versioned_item, 'read')
        self._set_file(id_str)
        return self._file_content(True)

    @expose(TEMPLATE_DIR + 'item_file.html')
    def get_one(self, id_str, **kwargs):
        g.security.require_access(c.versioned_item, 'read')
        self._set_file(id_str)

        download_url = "{}/files/{}/download".format(c.versioned_item.url(), id_str)
        visualize = g.visualize_artifact(c.file)

        return {
            'download_url': download_url,
            'visualize': visualize
        }

    @expose('json')
    def post(self, *args, **kwargs):
        g.security.require_access(c.versioned_item, 'write')
        container_key = self._get_resource_path()

        if kwargs.has_key('resumableFilename'):
            resumableFilename = kwargs.get('resumableFilename')
            resumableTotalSize = int(kwargs.get('resumableTotalSize', 0))
            resumableChunkSize = int(
                kwargs.get('resumableChunkSize', g.multipart_chunk_size))
            resumableIdentifier = kwargs.get('resumableIdentifier', '')
            resumableChunkNumber = int(kwargs.get('resumableChunkNumber', 1))
            forceReplace = bool(kwargs.get('forceReplace', False))

            if g.multipart_chunk_size != long(resumableChunkSize):
                raise exc.AJAXBadRequest(
                    'The chunk size does not match with the supported: ' +
                    str(g.multipart_chunk_size))

            container_keys_versioned = 'container_keys.{}'.format(
                c.versioned_item.version_escaped)
            if not kwargs.has_key('file'):
                # We are just checking if this file exists
                item_files = VersionedItemFile.query.find({
                    'app_config_id': c.app.config._id,
                    'mount_point': c.versioned_item.mount_point,
                    'item_master_id': c.versioned_item.master_id,
                    container_keys_versioned: {'$in': [container_key]},
                    'filename': resumableFilename,
                }).all()

                if item_files:
                    existing_file = item_files[0]
                    if existing_file.filesize != resumableTotalSize or \
                                    existing_file.md5_signature != \
                                    resumableIdentifier:

                        if forceReplace:
                            existing_file.delete(c.versioned_item, container_key)
                        else:
                            raise exc.AJAXFound(
                                'File with different content exists')

                    if existing_file.filesize == resumableTotalSize and \
                        existing_file.md5_signature == resumableIdentifier:
                        raise exc.AJAXFound('File already exists')
                else:
                    # Check if some other version already had this content
                    item_file = VersionedItemFile.query.get(
                        app_config_id=c.app.config._id,
                        mount_point=c.versioned_item.mount_point,
                        item_master_id=c.versioned_item.master_id,
                        filename=resumableFilename,
                        filesize=resumableTotalSize,
                        md5_signature=resumableIdentifier,
                        upload_completed=True
                    )
                    if item_file:
                        container_keys = item_file.container_keys.get(
                            c.versioned_item.version_escaped, [])
                        if container_key not in container_keys:
                            container_keys.append(container_key)
                            item_file.container_keys[c.versioned_item.version_escaped] = container_keys
                            item_file.flush_self()

                            raise exc.AJAXFound('File already exists')
                    else:
                        VersionedItemFile.insert(
                            c.versioned_item,
                            container_key=container_key,
                            app_config_id=c.app.config._id,
                            creator_id=c.user._id,
                            filename=resumableFilename,
                            filesize=resumableTotalSize,
                            upload_completed=False,
                            md5_signature=resumableIdentifier
                        )

            else:
                item_files = VersionedItemFile.query.find({
                    'app_config_id': c.app.config._id,
                    'mount_point': c.versioned_item.mount_point,
                    'item_master_id': c.versioned_item.master_id,
                    'filename': resumableFilename,
                    'filesize': resumableTotalSize,
                    'md5_signature': resumableIdentifier,
                    container_keys_versioned: {'$in': [container_key]}
                }).all()
                if item_files:
                    item_files[0].add_file_part(
                        kwargs['file'].file,
                        resumableChunkNumber
                    )
                    if item_files[0].upload_completed:
                        flash('Added %s' % resumableFilename, 'success')

    @expose('json')
    def post_delete(self, id_str, **kwargs):
        g.security.require_access(c.versioned_item, 'read')
        self._set_file(id_str)
        container_key = kwargs.get('container_key', '')
        c.file.delete(c.versioned_item, container_key)
        flash('Deleted %s' % c.file.filename, 'success')

        return dict(success=True)


class FolderController(RestController):
    mount_point = "versioned_item"
    versioned_item_class = None

    def _before(self, *args, **kwargs):
        item_id = request.url.split(self.mount_point + '/')[-1].split('/')[0]
        set_versioned_item(self.versioned_item_class, item_id)

    def __init__(self, versioned_item_class=None):
        self.mount_point = versioned_item_class.mount_point
        self.versioned_item_class = versioned_item_class

    def _get_resource_path(self):
        return urllib.unquote(
            request.url.split('folders')[1]).split('?')[0]

    def _set_folder(self, folder_path):
        c.folder = VersionedItemFolder.query.get(
            app_config_id=c.app.config._id,
            mount_point=c.versioned_item.mount_point,
            versioned_item_id=c.versioned_item._id,
            item_key=folder_path)
        if c.folder is None:
            raise AJAXNotFound('No such folder')

    @expose(TEMPLATE_DIR + 'item_folder.html')
    def get_one(self, *args, **kwargs):
        g.security.require_access(c.versioned_item, 'read')
        initial_path = self._get_resource_path()
        files_rest_url = c.versioned_item.url() + "files"
        folders_rest_url = c.versioned_item.url() + "folders"

        return dict(
            initial_path=initial_path,
            editable=g.security.has_access(c.versioned_item, 'write'),
            folders_rest_url=folders_rest_url,
            files_rest_url=files_rest_url
        )

    @expose('json')
    def path_data(self, *args, **kwargs):
        """
        Convert folder and file entries to filebrowser widget compatible
        JSON structure.

        @param kwargs:
        @return:
        """
        g.security.require_access(c.versioned_item, 'read')
        folder_path = self._get_resource_path().split('path_data')[1]
        self._set_folder(folder_path)
        data = {}

        for entry in c.folder.get_entries(c.versioned_item):
            if isinstance(entry, VersionedItemFolder):
                path = entry.item_key
                folders_url = c.versioned_item.url() + 'folders'
                folder_url = folders_url + urlquote(path)

                data[path] = {
                    'type': 'DIR',
                    'name': entry.folder_name,
                    'path': path,
                    'href': folder_url,
                    'extra': {}
                }
                #add_ancestors(path)
            elif isinstance(entry, VersionedItemFile):
                path = entry.temp_item_key()
                files_url = c.versioned_item.url() + 'files'
                download_url = file_url = ''
                if entry.is_scanned:
                    download_url = "{}/{}/download".format(files_url, str(entry._id))
                    file_url = "{}/{}/".format(files_url, str(entry._id))
                data[path] = {
                    'type': 'FILE',
                    'name': entry.filename,
                    'path': path,
                    'id': str(entry._id),
                    'href': file_url,
                    'downloadURL': download_url,
                    'uploadCompleted': entry.upload_completed,
                    'extra': {
                        'size': h.pretty_print_file_size(entry.filesize),
                        'actions': Markup((
                            '<a class="ico-download icon"'
                            'title="Download"'
                            'href="{}"></a>'
                            ).format(download_url))
                    },
                    'mimetype': guess_mime_type(path)
                }
                if not entry.upload_completed:
                    data[path]['md5Signature'] = entry.md5_signature
                    data[path]['uploadProgress'] = entry.upload_progress
                    data[path]['partNumbers'] = entry.part_number_list

                #add_ancestors(path)

        return data

    @expose('json')
    def post(self, *args, **kwargs):
        g.security.require_access(c.versioned_item, 'write')

        if kwargs.has_key('container') and kwargs.has_key('folderName'):
            VersionedItemFolder(
                c.versioned_item,
                kwargs['container'],
                kwargs['folderName'])
            flash('Folder was successfully created', 'success')

    @expose('json')
    def put(self, *args, **kwargs):
        g.security.require_access(c.versioned_item, 'write')
        to_folder = self._get_resource_path()

        if kwargs.get('command', '') == 'move_files' and \
                kwargs.has_key('file_paths'):

            container_keys_versioned = 'container_keys.{}'.format(
                c.versioned_item.version_escaped)

            file_paths = simplejson.loads(kwargs['file_paths'])
            flash_message = 'Files moved successfully'
            for file_path in file_paths:
                from_folder = os.path.dirname(file_path)
                file_name = os.path.basename(file_path)
                if not from_folder.endswith('/'):
                    from_folder += '/'

                source_files = VersionedItemFile.query.find({
                    'app_config_id': c.app.config._id,
                    'mount_point': c.versioned_item.mount_point,
                    'item_master_id': c.versioned_item.master_id,
                    container_keys_versioned: {'$in': [from_folder]},
                    'filename': file_name,
                }).all()
                target_files = VersionedItemFile.query.find({
                    'app_config_id': c.app.config._id,
                    'mount_point': c.versioned_item.mount_point,
                    'item_master_id': c.versioned_item.master_id,
                    container_keys_versioned: {'$in': [to_folder]},
                    'filename': file_name,
                }).all()
                if source_files and not target_files:
                    source_files[0].move(
                        c.versioned_item, from_folder, to_folder)
                if source_files and target_files:
                    flash_message = 'Some files were not moved'

            flash(flash_message, 'success')

    @expose('json')
    def post_delete(self, *args, **kwargs):
        g.security.require_access(c.versioned_item, 'write')
        folder_path = self._get_resource_path()
        self._set_folder(folder_path)
        c.folder.delete(c.versioned_item)

        return dict(success=True)


class VersionedItemController(RestController):
    mount_point = None
    versioned_item_class = VersionedItem
    versioned_file_class = VersionedItemFile
    plural_item_name = "Versioned Items"
    item_name = "Versioned Item"

    _custom_actions = [
        'list_data',
        'resumable',
        'data'
    ]

    _table_columns = [
        {
            "sTitle": "Name",
            "solr_field": "title_s"
        },
        {
            "sTitle": "Version",
            "solr_field": "version_s"
        },
        {
            "sTitle": "Released",
            "solr_field": "upload_status_s"
        },
        {
            "sTitle": "Modification Date",
            "solr_field": "mod_date_dt"
        }
    ]

    class Widgets(object):
        related_artifacts = RelatedArtifactsWidget()
        markdown_editor = MarkdownEdit()
        #menu_bar = VersionedItemMenuBar()

    def __init__(self):
        self.mount_point = self.versioned_item_class.mount_point
        self.folders = FolderController(self.versioned_item_class)
        self.files = FileController(self.versioned_item_class)

    @expose(TEMPLATE_DIR + 'item_edit.html')
    def new(self, *args, **kwargs):
        g.security.require_access(c.app, 'write')
        c.markdown_editor = self.Widgets.markdown_editor
        rest_url = "{}{}/".format(
            c.app.url,
            self.mount_point)

        return dict(
            rest_url=rest_url,
            item_type=self.item_name,
            desc_file_extensions=self.versioned_item_class.meta_file_extensions()
        )

    @expose(TEMPLATE_DIR + 'item_edit.html')
    def edit(self, id_str, **kwargs):
        set_versioned_item(self.versioned_item_class, id_str)
        g.security.require_access(c.versioned_item, 'write')

        c.markdown_editor = self.Widgets.markdown_editor
        c.related_artifacts_widget = self.Widgets.related_artifacts
        #c.menu_bar = self.Widgets.menu_bar

        rest_url = "{}{}/".format(
            c.app.url,
            self.mount_point)

        return dict(rest_url=rest_url,
            item_type=self.item_name,
            desc_file_extensions=self.versioned_item_class.meta_file_extensions()
        )

    @expose('json')
    def post(self, meta_file=None, *args, **kwargs):
        """
        """
        g.security.require_access(c.app, 'write')

        file_obj = None
        if meta_file is not None:
            file_obj = meta_file.file
            _, extension = os.path.splitext(meta_file.filename)
            if extension.startswith('.'):
                extension = extension[1:]
            if extension not in self.versioned_item_class.meta_file_extensions():
                raise AJAXServerError('Not recognized file type')

        name = kwargs.pop("name", "")
        version = kwargs.pop("version", "")
        description = kwargs.pop("description", "")

        versioned_item = self.versioned_item_class.upsert(
            name,
            version,
            description,
            file_obj,
            **kwargs
        )
        if file_obj is not None:
            container_keys_versioned = 'container_keys.{}'.format(
                versioned_item.version_escaped)
            container_key = '/'
            md5_sig = md5_signature(file_obj)
            file_obj.seek(0, 2)
            filesize = file_obj.tell()
            file_obj.seek(0, 0)

            item_files = VersionedItemFile.query.find({
                'app_config_id': c.app.config._id,
                'mount_point': versioned_item.mount_point,
                'item_master_id': versioned_item.master_id,
                container_keys_versioned: {'$in': [container_key]},
                'filename': meta_file.filename,
            }).all()

            if item_files:
                existing_file = item_files[0]
                existing_file.delete(versioned_item, container_key)
                if existing_file.filesize != filesize or \
                                existing_file.md5_signature != \
                                md5_sig:
                    existing_file.delete(versioned_item, container_key)

            versioned_file = VersionedItemFile.insert(
                versioned_item,
                container_key=container_key,
                app_config_id=c.app.config._id,
                creator_id=c.user._id,
                filename=meta_file.filename,
                filesize=filesize,
                upload_completed=False,
                md5_signature=md5_sig
            )
            versioned_file.add_file_part(file_obj, 0)

        ThreadLocalODMSession.flush_all()

        return versioned_item.dict()

    @expose('json')
    def put(self, id_str, *args, **kwargs):
        """
        """
        set_versioned_item(self.versioned_item_class, id_str)
        g.security.require_access(c.versioned_item, 'write')

        if 'release' in args or kwargs.get('command','') == 'release':
            c.versioned_item.released = True
            flash('{} was released'.format(c.versioned_item.name), 'success')

        if kwargs.get('command', '') == 'save':
            base_properties = simplejson.loads(kwargs.get('baseProperties', '{}'))
            if 'name' in base_properties:
                c.versioned_item.name = base_properties['name']

            flash('Changes were saved successfully', 'success')

        ThreadLocalODMSession.flush_all()

        return c.versioned_item.dict()

    @expose(TEMPLATE_DIR + 'item_view.html')
    def get_one(self, id_str, *args, **kwargs):
        set_versioned_item(self.versioned_item_class, id_str)
        g.security.require_access(c.versioned_item, 'read')

        #c.menu_bar = self.Widgets.menu_bar
        rest_url = "{}/{}/{}/data".format(
            c.app.url,
            self.mount_point,
            c.versioned_item._id)

        return dict(rest_url=rest_url)

    @expose('json')
    def data(self, id_str):
        set_versioned_item(self.versioned_item_class, id_str)
        g.security.require_access(c.versioned_item, 'read')
        return c.versioned_item.dict()

    @expose()
    def download(self, id_str):
        set_versioned_item(self.versioned_item_class, id_str)
        g.security.require_access(c.versioned_item, 'read')

        if g.s3_serve_local:
            set_download_headers(os.path.basename(
                c.versioned_item.item_file.item_key))
            set_cache_headers(expires_in=1)
            return c.versioned_item.item_file.serve()
        else:
            redirect(c.versioned_item.item_file.item_key.get_s3_temp_url())

    @expose(TEMPLATE_DIR + 'browse.html')
    def get_all(self):
        g.security.require_access(c.app.config, 'read')
        table_columns = [{"sTitle": col["sTitle"]}
                         for col in self._table_columns]
        if g.security.has_access(c.app.config, 'write'):
            table_columns.append({"sTitle": "Actions", "bSortable": False})
        return {
            "data_url": '{}{}/list_data'.format(
                c.app.url,
                self.mount_point),
            "table_columns": table_columns,
            "sorting": [[0, "asc"],[1, "desc"]],
            "title": self.plural_item_name
        }

    @expose('json', render_params={"sanitize": False})
    @validate(DATATABLE_SCHEMA, error_handler=raise_400)
    def list_data(self, iDisplayStart=0, iDisplayLength=50, sSearch=None,
                  iSortingCols=0, sEcho=0, **kwargs):
        g.security.require_access(c.app.config, 'read')
        write_access = g.security.has_access(c.app.config, 'write')
        publish_access = g.security.has_access(c.app.config, 'publish')
        # assemble the query
        query_l = []
        if sSearch:
            query_l.append(sSearch)

        read_roles = ' OR '.join(g.security.get_user_read_roles())
        query_l.extend([
            'type_s:"{}"'.format(self.versioned_item_class.type_s),
            'app_config_id_s:"{}"'.format(str(c.app.config._id)),
            'read_roles:({})'.format(read_roles),
        ])
        query = ' AND '.join(query_l)
        columns = self._table_columns
        sort_l = [
            columns[int(kwargs['iSortCol_{}'.format(i)])]['solr_field'] +
            ' ' + kwargs['sSortDir_{}'.format(i)]
            for i in range(iSortingCols)]

        # run the search
        result = g.search(q=query, start=iDisplayStart, rows=iDisplayLength,
            sort=','.join(sort_l))

        # format the data
        data = []
        for item_doc in result.docs:
            # format data
            dt = _parse_solr_date(item_doc["mod_date_dt"])
            item_id = item_doc['id_s']

            is_scanned = True
            is_released = item_doc.get('released_b', False)
            if g.clamav_enabled:
                is_scanned = item_doc.get('is_scanned_b', False)
            row = [
                Markup('<a href="{}">{}</a>'.format(
                    item_doc["url_s"], item_doc.get("title_s",""))),
                item_doc.get('version_s'),
                is_released,
                dt.strftime('%Y-%m-%d %H:%M')
            ]
            buttons = []
            if write_access and not is_released:
                release_button = g.icon_button_widget.display(
                    label="Release",
                    icon='ico-check',
                    className='put-link',
                    href="{}release".format(item_doc["url_s"])
                )
                buttons.append(release_button)
            if publish_access and is_released:
                exchanges = g.exchange_manager.get_exchanges(c.app.config, self.versioned_item_class)
                for exchange, artifact_config in exchanges:
                    url = artifact_config["publish_url"]
                    if '?' in url:
                        url += '&artifact_id={}'.format(item_id)
                    else:
                        url += '?artifact_id={}'.format(item_id)
                    xcng_btn = g.icon_button_widget.display(
                        label='Share in {}'.format(exchange.config["name"]),
                        icon=artifact_config.get('publish_icon', 'ico-share'),
                        href=url
                    )
                    buttons.append(xcng_btn)

            if is_scanned and is_released:
                download_button = g.icon_button_widget.display(
                    label="Download",
                    icon='ico-download',
                    href="{}download".format(item_doc["url_s"])
                )
                buttons.append(download_button)

            if is_scanned:
                browse_button = g.icon_button_widget.display(
                    label="Browse Content",
                    icon='ico-folder_fill',
                    href="{}folders/".format(item_doc["url_s"])
                )
                buttons.append(browse_button)

            row.append(' '.join(buttons))
            data.append(row)

        response = {
            'iTotalRecords': result.hits,
            'iTotalDisplayRecords': result.hits,
            'sEcho': sEcho,
            'aaData': data
        }
        return response

    @expose('json')
    def post_delete(self, id_str, **kwargs):
        set_versioned_item(self.versioned_item_class, id_str)
        g.security.require_access(c.versioned_item, 'write')

        ret_dict = dict(success=False)
        #c.dataset.delete()

        return ret_dict
