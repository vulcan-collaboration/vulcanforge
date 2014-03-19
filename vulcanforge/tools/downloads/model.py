# -*- coding: utf-8 -*-

"""
models

@summary: models

@author: U{tannern<tannern@gmail.com>}
"""
import os
from ming.odm import FieldProperty

from pylons import app_globals as g, tmpl_context as c

from vulcanforge.common.model.session import visualizable_artifact_session
from vulcanforge.artifact.model import Artifact, VisualizableArtifact


class ForgeDownloadsAbstractItem(Artifact):

    type_s = 'ForgeDownloadsAbstractItem'
    item_key = FieldProperty(str)
    container_key = FieldProperty(str, if_missing=None)
    filename = FieldProperty(str, if_missing='')
    filesize = FieldProperty(int, if_missing=None)

    def index(self, *args, **kwargs):
        return False

    def url(self):
        return self.app_config.url() + 'content' + self.item_key


class ForgeDownloadsFile(ForgeDownloadsAbstractItem, VisualizableArtifact):

    class __mongometa__:
        name = 'forgedownloads_file'
        session = visualizable_artifact_session
        indexes = [
            'mod_date',
            ('app_config_id', 'item_key'),
            ('app_config_id', 'container_key')
        ]

    type_s = 'ForgeDownloadsFile'

    def raw_url(self):
        return '/rest' + self.url()

    def shorthand_id(self):
        return self.item_key

    def url_for_visualizer(self):
        return '/rest' + self.url()

    @classmethod
    def upsert(cls, file_obj, container_key='/', filename=''):
        item_key = container_key + filename
        file_obj.seek(0, 2)
        filesize = file_obj.tell()
        file_obj.seek(0)
        item = cls.query.get(
            app_config_id=c.app.config._id,
            item_key=item_key
        )
        if item is None:
            item = cls(
                app_config_id=c.app.config._id,
                item_key=item_key,
                container_key=container_key,
                filename=filename,
                filesize=filesize
            )
        else:
            item.filesize = filesize

        key = g.get_s3_key('', item)
        key.set_contents_from_file(file_obj)

    def get_key(self):
        return g.get_s3_key('', self)

    def delete(self):
        g.delete_s3_key(self.get_key())
        super(ForgeDownloadsFile, self).delete()

    def read(self):
        return self.get_key().read()

    def get_content_to_folder(self, path):
        filename = os.path.basename(self.filename)
        full_path = os.path.join(path, filename)
        with open(full_path, 'w') as fp:
            self.get_key().get_contents_to_file(fp)
        return filename


class ForgeDownloadsDirectory(ForgeDownloadsAbstractItem):

    class __mongometa__:
        name = 'forgedownloads_directory'
        indexes = [
            'mod_date',
            ('app_config_id', 'item_key'),
            ('app_config_id', 'container_key')
        ]

    type_s = 'ForgeDownloadsDirectory'

    def child_resources(self):
        file_resources = ForgeDownloadsFile.query.find({
            'app_config_id': self.app_config_id,
            'container_key': self.item_key
        }).all()
        folder_resources = ForgeDownloadsDirectory.query.find({
            'app_config_id': self.app_config_id,
            'container_key': self.item_key
        }).all()
        return file_resources + folder_resources

    def get_entries(self):
        entries = self.child_resources()
        entries.append(self)
        return entries

    def delete(self):
        file_resources = ForgeDownloadsFile.query.find({
            'app_config_id': self.app_config_id,
            'container_key': self.item_key
        }).all()
        for file_resource in file_resources:
            file_resource.delete()

        folder_resources = ForgeDownloadsDirectory.query.find({
            'app_config_id': self.app_config_id,
            'container_key': self.item_key
        }).all()
        for folder_resource in folder_resources:
            folder_resource.delete()

        super(ForgeDownloadsDirectory, self).delete()
