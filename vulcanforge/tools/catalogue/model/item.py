import logging
import re

from datetime import datetime
from pylons import tmpl_context as c, app_globals as g
from ming import schema, DESCENDING
from ming.odm import FieldProperty, ForeignIdProperty
from ming.utils import LazyProperty
from boto.exception import S3ResponseError

from vulcanforge.artifact.model import Artifact
from vulcanforge.auth.model import User
from vulcanforge.exchange.model import ExchangeableArtifact
from vulcanforge.taskd import model_task
from vulcanforge.common.model.session import artifact_orm_session
from vulcanforge.common.model.file import FileArtifact
from vulcanforge.common.exceptions import (
    AJAXForbidden,
    AJAXBadRequest,
    AJAXFound
)

LOG = logging.getLogger(__name__)

URL_SAFE_REGEX = re.compile("^[0-9a-zA-Z\$\-\_\.\+\!\*\'\(\)\, ]+$")

# Regex to check semantic versioning syntax
# The following examples should pass:
# 11.22.33
# 11.22.33-alpha.13
VERSION_REGEX = re.compile("^\d+\.\d+\.\d+(?:\-[\w\.]+)*$")


class VersionedItemFile(FileArtifact):
    class __mongometa__:
        session = artifact_orm_session
        name = 'versioned_item_file'
        indexes = FileArtifact.__mongometa__.indexes + []

    type_s = 'VersionedItemFile'
    mount_point = FieldProperty(str)
    item_master_id = FieldProperty(schema.ObjectId)

    # This tells us what container_keys this file is present in and what the
    # container path is within that version
    container_keys = FieldProperty(schema.Anything, if_missing={})

    _temp_item_key = None

    def s3_key_prefix(self):
        return '/'.join(
            [self.mount_point,
            str(self.item_master_id),
            str(self._id)]
        )

    @classmethod
    def insert(cls, versioned_item, container_key='/', **kw):
        item_file = cls(**kw)

        if not container_key.startswith('/'):
            container_key = '/' + container_key
        if not container_key.endswith('/'):
            container_key += '/'

        item_file.mount_point = versioned_item.mount_point
        item_file.item_master_id = versioned_item.master_id
        item_file.container_keys = {versioned_item.version_escaped:[container_key]}

        return item_file

    def url(self):
        return ""

    @property
    def title_s(self):
        return 'File {}'.format(self.filename)

    def temp_item_key(self, container_key=None):
        if self._temp_item_key is None and container_key is not None:
            self._temp_item_key = container_key + self.filename

        return self._temp_item_key

    @model_task
    def hard_delete(self):
        before = datetime.now()
        try:
            if self.upload_completed:
                g.delete_s3_key(self.get_key())
            else:
                self.multipart.cancel_upload()
        except S3ResponseError as s3e:
            LOG.info("Failed to delete {} from s3: {}".format(
                self.item_key,
                s3e.reason
            ))
        else:
            LOG.info("Deleted {} from s3 in {}s".format(
                self.item_key,
                str(datetime.now() - before)
            ))
        Artifact.delete(self)

    def delete(self, versioned_item, container_key):
        container_keys_in_version = self.container_keys.get(
            versioned_item.version_escaped, [])

        try:
            container_keys_in_version.remove(container_key)
        except:
            pass
        if not container_keys_in_version:
            self.container_keys.pop(versioned_item.version_escaped, None)
            if not self.container_keys:
                self.hard_delete.post()
        else:
            self.container_keys[
                versioned_item.version_escaped] = container_keys_in_version

    def move(self, versioned_item, from_folder, to_folder):
        container_keys_in_version = self.container_keys.get(
            versioned_item.version_escaped, [])
        try:
            container_keys_in_version.remove(from_folder)
        except:
            pass
        if not to_folder in container_keys_in_version:
            container_keys_in_version.append(to_folder)
        self.container_keys[
            versioned_item.version_escaped] = container_keys_in_version


class VersionedItemFolder(Artifact):
    class __mongometa__:
        session = artifact_orm_session
        name = 'versioned_item_folder'
        indexes = Artifact.__mongometa__.indexes + []

    type_s = 'VersionedItemFolder'
    versioned_item_id = FieldProperty(schema.ObjectId)

    container_key = FieldProperty(str, if_missing=None)
    mount_point = FieldProperty(str)
    item_key = FieldProperty(str)
    folder_name = FieldProperty(str, if_missing='')
    creator_id = ForeignIdProperty(User, if_missing=None)

    def __init__(self, versioned_item, container, folder_name, **kw):
        super(Artifact, self).__init__(**kw)

        if container:
            container_key = container
            if not container_key.startswith('/'):
                container_key = '/' + container_key
            if not container_key.endswith('/'):
                container_key += '/'
        else:
            container_key = ""

        folder_name = folder_name.strip('/')

        existing_folder = self.query.get(
            versioned_item_id=versioned_item._id,
            mount_point=versioned_item.mount_point,
            container_key=container_key,
            folder_name=folder_name
        )
        if existing_folder:
            raise AJAXFound('folder already exists')

        self.container_key = container_key
        self.mount_point = versioned_item.mount_point
        if container_key and folder_name:
            self.item_key = container_key + folder_name + '/'
        else:
            # Root folder case
            self.item_key = "/"
        self.folder_name = folder_name
        self.versioned_item_id = versioned_item._id
        self.app_config_id = versioned_item.app_config_id

        if self.creator_id is None:
            self.creator_id = c.user._id

    def url(self):
        return ""

    def delete(self, versioned_item):
        entries = self.child_resources(versioned_item)
        for entry in entries:
            if isinstance(entry, VersionedItemFolder):
                entry.delete(versioned_item)
            elif isinstance(entry, VersionedItemFile):
                entry.delete(versioned_item, self.item_key)
        super(Artifact, self).delete()

    def child_resources(self, versioned_item):
        container_keys_versioned = 'container_keys.{}'.format(
            versioned_item.version_escaped)

        file_resources = VersionedItemFile.query.find({
            'app_config_id': self.app_config_id,
            'item_master_id': versioned_item.master_id,
            container_keys_versioned: {'$in': [self.item_key]}
        }).all()
        for fr in file_resources:
            fr.temp_item_key(self.item_key)
        folder_resources = self.query.find({
            'app_config_id': self.app_config_id,
            'versioned_item_id': self.versioned_item_id,
            'container_key': self.item_key,
        }).all()
        return file_resources + folder_resources

    def get_entries(self, versioned_item):
        entries = self.child_resources(versioned_item)
        entries.append(self)
        return entries


class VersionedItem(ExchangeableArtifact):
    class __mongometa__:
        session = artifact_orm_session
        name = 'versioned_item'
        indexes = [('master_id', 'version')]

    mount_point = "versioned_item"
    has_file_content = True

    type_s = "Versioned Item"
    master_id = FieldProperty(schema.ObjectId, index=True, if_missing=None)
    # Name uniqueness is enforced within an app instance
    name = FieldProperty(str)

    # Must adhere to semantic versioning rules, see http://semver.org/
    # Basically X.Y.Z where X, Y, and Z are non-negative integers
    version = FieldProperty(str)

    description = FieldProperty(str, if_missing='')

    author_id = FieldProperty(schema.ObjectId, if_missing=None)
    deleted = FieldProperty(bool, if_missing=False)

    # Once set to true it makes the item and its content unchangable
    released = FieldProperty(bool, if_missing=False)
    release_date = FieldProperty(datetime, if_missing=None)

    def index(self, text_objects=None, **kwargs):
        """
        """
        if not text_objects:
            text_objects = [self.description]
        index = dict(
            name_s=self.name,
            id_s=self._id,
            master_id_s=self.master_id,
            version_s=self.version,
            description_s=self.description,
            released_b=self.released,
            deleted_b=self.deleted
        )
        index.update(**kwargs)
        return ExchangeableArtifact.index(self, text_objects, **index)

    @classmethod
    def meta_file_extensions(cls):
        raise NotImplementedError()

    @classmethod
    def extract_name_version(cls, meta_file):
        raise NotImplementedError()

    @classmethod
    def upsert(cls, name, version, description, meta_file, *args, **kwargs):
        # If name and version are not provided extract them from the meta_file
        if (not name or not version) and meta_file is not None:
            name, version = cls.extract_name_version(meta_file)

        # Validate that name is URL Safe
        if not URL_SAFE_REGEX.match(name):
            raise AJAXBadRequest('Name contains unsupported characters')

        # Validate version
        if not VERSION_REGEX.match(version):
            raise AJAXBadRequest('Version does not follow semantic versioning '
                                 'guidelines: A.B.C-some_string')

        # Retrieve a version to determine if we have any
        existing_version = cls.query.get(
            app_config_id=c.app.config._id,
            name=name,
            version=version)

        if existing_version:
            # Verify that the existing version is not yet released
            if existing_version.released:
                raise AJAXForbidden(
                    "This version is already released, you cannot alter it.")
            version_object = existing_version
        else:
            version_object = cls(
                app_config_id=c.app.config._id,
                name=name,
                version=version,
                **kwargs
            )
            existing_version = cls.query.get(
                app_config_id=c.app.config._id, name=name)

            if existing_version:
                version_object.master_id = existing_version.master_id
            else:
                version_object.master_id = version_object._id

            if cls.has_file_content:
                root_dir = VersionedItemFolder(
                    version_object,
                    '',
                    ''
                )
                root_dir.flush_self()

        version_object.mod_date = datetime.utcnow()
        version_object.author_id = c.user._id
        version_object.description = description
        version_object.update_meta(meta_file)

        return version_object

    @LazyProperty
    def version_escaped(self):
        return self.version.replace('.','_')

    def update_meta(self, meta_file):
        raise NotImplementedError()

    def release(self, compile_zip=False):
        self.released = True
        self.release_date = datetime.utcnow()

        if compile_zip:
            pass

    def dict(self):
        manifest_dict = dict(
            id=str(self._id),
            master_id=str(self.master_id),
            name=self.name,
            version=self.version,
            description=self.description,
            url=self.url(),
            mod_date=self.mod_date,
            released=self.released,
            release_date=self.release_date,
            deleted=self.deleted
        )

        return manifest_dict

    @property
    def title_s(self):
        return self.name

    def url(self):
        return "{}{}/{}/".format(
            self.app_config.url(),
            self.mount_point,
            str(self._id)
        )

    def content_url(self):
        return "{}folders/".format(
            self.url()
        )

    def download_url(self):
        return "{}download".format(
            self.url()
        )

    ##################################
    # File / Folder Aspect
    ##################################

    @property
    def filesize(self):
        return 0
