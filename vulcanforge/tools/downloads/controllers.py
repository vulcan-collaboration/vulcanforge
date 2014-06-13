# -*- coding: utf-8 -*-

"""
controllers

@summary: controllers

@author: U{tannern<tannern@gmail.com>} 
"""
import urllib
import os
import logging
import cgi
from cStringIO import StringIO

from paste.deploy.converters import asbool
from tg import expose, request, flash, override_template, redirect
from tg.controllers import RestController, TGController
from pylons import app_globals as g, tmpl_context as c

from vulcanforge.common import helpers as h
from vulcanforge.common.controllers import BaseController, BaseTGController
from vulcanforge.common.helpers import urlquote
from vulcanforge.common.util.http import (
    set_cache_headers,
    set_download_headers
)
from vulcanforge.common import exceptions as exc
from vulcanforge.artifact.widgets import RelatedArtifactsWidget
from vulcanforge.visualize.model import VisualizerConfig
from vulcanforge.tools.downloads import model as FDM

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:tools/downloads/templates/'


def _get_resource_path(resource_url=None):
    if resource_url is None:
        resource_url = request.url
    controller_path = c.app.config.url() + 'content'
    return urllib.unquote(resource_url.split(controller_path)[1]).split('?')[0]


class FileController(BaseTGController):

    class Widgets(BaseTGController.Widgets):
        related_artifacts = RelatedArtifactsWidget()

    @expose(TEMPLATE_DIR + 'file.html')
    def _default(self, *args, **kwargs):
        file_path = _get_resource_path()
        fd_file = FDM.ForgeDownloadsFile.query.get(item_key=file_path)
        if fd_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')

        c.related_artifacts_widget = self.Widgets.related_artifacts
        rendered_file = g.visualize_artifact(fd_file).full_render(
            on_unvisualizable=lambda fd: redirect(fd_file.raw_url()))

        return dict(
            hide_sidebar=True,
            fd_file=fd_file,
            editable=g.security.has_access(c.app, 'write'),
            rendered_file=rendered_file)


class TreeController(TGController):

    class Widgets(BaseTGController.Widgets):
        related_artifacts = RelatedArtifactsWidget()

    @expose(TEMPLATE_DIR + 'tree.html')
    def _default(self, *args, **kwargs):
        folder_path = _get_resource_path()

        fd_folder = FDM.ForgeDownloadsDirectory.query.get(item_key=folder_path)
        if fd_folder is None:
            raise exc.AJAXNotFound('The requested folder does not exist.')

        content_root_path = c.app.url+'content'
        c.related_artifacts_widget = self.Widgets.related_artifacts
        return dict(
            hide_sidebar=True,
            fd_folder=fd_folder,
            editable=g.security.has_access(c.app, 'write'),
            content_root_path=content_root_path)


class ContentController(TGController):

    @expose()
    def _lookup(self, next=None, *rest):
        path_last = request.url.split('/')[-1]
        if next is None:
            params = list(rest)
        else:
            params = [next] + list(rest)

        if next is not None and path_last.find(os.extsep) >= 0:
            return FileController(), params

        return TreeController(), params


class ForgeDownloadsRootController(BaseController):

    content = ContentController()

    def _check_security(self):
        g.security.require_access(c.app.config, "read")

    @expose()
    def index(self):
        redirect('./content/')


class ContentRestController(RestController):

    @expose('json')
    def post(self, file=None, folder=None, path='/', *args, **kwargs):
        g.security.require_access(c.app, 'write')

        if file is not None:
            FDM.ForgeDownloadsFile.upsert(
                file.file,
                container_key=path,
                filename=file.filename
            )

            flash('Added %s' % file.filename, 'success')
        elif folder is not None:
            folder_name = folder.strip('/')
            item_key = path + folder_name + '/'
            folder_object = FDM.ForgeDownloadsDirectory.query.get(
                app_config_id=c.app.config._id,
                item_key=item_key
            )
            if folder_object is not None:
                raise exc.AJAXMethodNotAllowed('Folder already exists')

            FDM.ForgeDownloadsDirectory(
                container_key=path,
                item_key=item_key,
                filename=folder_name
            )
            flash('Added %s' % folder_name, 'success')

    def _get_file_or_404(self):
        path = _get_resource_path()
        downloaded_file = FDM.ForgeDownloadsFile.query.get(
            app_config_id=c.app.config._id,
            item_key=path
        )

        if downloaded_file is None:
            raise exc.AJAXNotFound('The requested file does not exist.')

        return downloaded_file

    def _file(self, *args, **kwargs):
        escape = asbool(kwargs.get('escape', False))

        downloaded_file = self._get_file_or_404()
        key = g.get_s3_key('', downloaded_file)

        set_download_headers(os.path.basename(downloaded_file.item_key))
        set_cache_headers(expires_in=1)

        def iter_contents():
            for chunk in key:
                if escape:
                    yield cgi.escape(chunk)
                else:
                    yield chunk

        return iter_contents()

    def _folder(self, *args, **kwargs):
        """
        Create a specially formatted dictionary for the filebrowser widget
        """
        path = _get_resource_path()

        folder_object = FDM.ForgeDownloadsDirectory.query.get(
            app_config_id=c.app.config._id,
            item_key=path
        )
        if folder_object is None:
            raise exc.AJAXNotFound('The requested folder does not exist.')

        data = {}
        entries = folder_object.get_entries()

        for entry in entries:
            path = entry.item_key
            href = "/rest{}content{}".format(
                c.app.config.url(),
                urlquote(path)
            )
            data[path] = {
                "name": h.really_unicode(entry.filename),
                "path": h.really_unicode(path),
                "href": href,
                "downloadURL": href,
                "modified": entry.mod_date.isoformat(),
                "extra": {}
            }
            if isinstance(entry, FDM.ForgeDownloadsDirectory):
                data[path]['type'] = 'DIR'
            else:
                data[path]['type'] = 'FILE'
                data[path]['artifact'] = {
                    'reference_id': entry.index_id(),
                    'type': entry.type_s
                }

            icon_url = g.visualize_url(path).get_icon_url()
            if icon_url:
                data[path]['extra']['iconURL'] = icon_url

            if entry.filesize is not None:
                data[path]['extra']['size'] = h.pretty_print_file_size(
                    entry.filesize)

        return data

    @expose('json')
    def get_one(self, *args, **kwargs):
        g.security.require_access(c.app, 'read')
        if request.url.endswith('/'):
            return self._folder(*args)
        else:
            return self._file(*args, **kwargs)

    @expose('json')
    def post_delete(self, *args, **kwargs):
        """

        @param property_id:
        @param kwargs:
        @return:
        """
        g.security.require_access(c.app, 'write')
        path = _get_resource_path()

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
                item_key=path
            )
            if file_object is None:
                raise exc.AJAXNotFound('The requested folder does not exist.')
            file_object.delete()
            file_name = file_object.filename

        ret_dict = dict(success=True)
        flash('Deleted %s %s' % (file_type, file_name), 'success')
        return ret_dict


class ForgeDownloadsRestController(TGController):
    content = ContentRestController()
