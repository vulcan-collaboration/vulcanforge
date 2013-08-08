import re
import posixpath
import mimetypes
import logging
from datetime import datetime
import urlparse
import zipfile
import itertools
from collections import OrderedDict
import os

from pylons import app_globals as g, tmpl_context as c
import simplejson
import pymongo
from ming.odm.declarative import MappedClass
from ming.odm.property import FieldProperty
from ming.schema import ObjectId
from ming.utils import LazyProperty
from boto.exception import S3ResponseError

from vulcanforge.common.helpers import urlquote
from vulcanforge.common.model.session import main_orm_session
from vulcanforge.auth.model import User
from vulcanforge.visualize.exceptions import VisualizerError

LOG = logging.getLogger(__name__)

VISUALIZER_PREFIX = 'Visualizer/'


class SimpleCache(OrderedDict):

    def __init__(self, size, *args, **kwargs):
        self.size = size if size is not None else self.default_size
        super(SimpleCache, self).__init__(*args, **kwargs)

    def __setitem__(self, key, value, PREV=0, NEXT=1,
                    dict_setitem=dict.__setitem__):
        # make sure it goes to back
        if key in self:
            del self[key]
        else:
            while self.__len__() >= self.size:
                self.popitem(False)
        super(SimpleCache, self).__setitem__(key, value, PREV=PREV, NEXT=NEXT,
                                             dict_setitem=dict_setitem)

    def accessitem(self, key):
        """get item and move to back of delete queue"""
        self[key] = value = self[key]
        return value


class Visualizer(MappedClass):

    class __mongometa__:
        name = 'visualizer'
        session = main_orm_session
        indexes = ['extensions', ('extensions', 'active')]

        def before_save(data):
            data['modified_date'] = datetime.utcnow()
            if not data['shortname']:
                data['shortname'] = Visualizer.strip_name(data['name'])

    _id = FieldProperty(ObjectId)
    creator_id = FieldProperty(ObjectId, if_missing=lambda: c.user._id)
    created_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    modified_date = FieldProperty(datetime, if_missing=datetime.utcnow)

    bucket_name = FieldProperty(str, if_missing=None)
    bundle_content = FieldProperty([str], if_missing=[])

    active = FieldProperty(bool, if_missing=False)
    priority = FieldProperty(int, if_missing=0)
    # see vulcanforge.visualize.widgets for widget name options
    widget = FieldProperty(str, if_missing='iframe')
    thumb = FieldProperty(str, if_missing='')

    name = FieldProperty(str)
    shortname = FieldProperty(str, unique=True)
    mime_types = FieldProperty([str])
    extensions = FieldProperty([str])
    entry_point = FieldProperty(str, if_missing='index.html')
    teaser_entry_point = FieldProperty(str)
    description = FieldProperty(str, if_missing='')
    icon = FieldProperty(str)

    no_upload_extensions = [
        re.compile('\.git/'),
        re.compile('\.svn/'),
        re.compile('__MACOSX/'),
        re.compile('\.DS_Store'),
        re.compile('^/'),
        re.compile('^\.\.'),
    ]
    # attrs editable by manifest file
    _editable_attrs = (
        'name',
        'mime_types',
        'entry_point',
        'description',
        'extensions',
        'shortname',
        'teaser_entry_point',
        'icon'
        )

    _additional_text_extensions = {
        '.ini',
        '.gitignore',
        '.svnignore',
        'README'
    }

    # extension cache
    cache = SimpleCache(10)

    def __init__(self, extensions=['*'], **kwargs):
        super(Visualizer, self).__init__(extensions=extensions, **kwargs)

    def guess_type(self, name):
        """Guess the mime type and encoding of a given filename"""
        content_type, encoding = mimetypes.guess_type(name)
        if content_type is None or not content_type.startswith('text/'):
            fn, ext = os.path.splitext(name)
            ext = ext or fn
            if ext in self._additional_text_extensions:
                content_type, encoding = 'text/plain', None
            if content_type is None:
                content_type, encoding = 'application/octet-stream', None
        return content_type, encoding

    @property
    def creator(self):
        if self.creator_id:
            return User.query.get(_id=self.creator_id)

    @LazyProperty
    def key_prefix(self):
        return urlquote(VISUALIZER_PREFIX + str(self._id) + '#')

    @LazyProperty
    def icon_url(self):
        try:
            if self.icon and self.bundle_content:  # must be in s3
                key = self.get_s3_key(self.icon, insert_if_missing=False)
                if key:
                    return key.generate_url(3600 * 24 * 2)
        except S3ResponseError:
            pass
        return self.icon

    def get_s3_key(self, key_postfix, **kw):
        key_name = self.key_prefix + urlquote(key_postfix)
        return g.get_s3_key(key_name, **kw)

    def delete_s3_keys(self):
        for key in g.get_s3_keys(self.key_prefix):
            g.delete_s3_key(key)

    def _iter_zip(self, zip_handle):
        return itertools.ifilter(
            lambda n: not any(r.search(n) for r in self.no_upload_extensions),
            zip_handle.namelist())

    def update_from_archive(self, archive_fp):
        with zipfile.ZipFile(archive_fp) as zip_handle:
            # get root
            for filename in self._iter_zip(zip_handle):
                if os.path.basename(filename) == 'manifest.json':
                    root = os.path.dirname(filename)
                    break
            else:
                raise VisualizerError("No Manifest File found")

            # parse manifest
            with zip_handle.open(filename) as manifest_fp:
                self.update_from_manifest_file(manifest_fp)

            # append files
            for filename in itertools.ifilter(
                lambda f: f.startswith(root + '/') if root else True,
                self._iter_zip(zip_handle)):
                relative_path = os.path.relpath(filename, root)
                if relative_path != '.':
                    self.bundle_content.append(relative_path)
                    k = self.get_s3_key(relative_path)
                    if not os.path.isdir(filename):
                        k.set_contents_from_string(
                            zip_handle.open(filename).read()
                        )

    def update_from_manifest_file(self, manifest_fp):
        manifest = simplejson.load(manifest_fp)
        self.update_from_manifest(manifest)

    def update_from_manifest(self, manifest):
        """@param manifest dict"""
        for k, v in manifest.iteritems():
            if k in self._editable_attrs:
                setattr(self, k, v)
            else:
                LOG.warn('manifest.json contains ignored key: %s = %s', k, v)
        if not self.extensions:
            self.extensions = ['*']
        if self.shortname is None:
            self.shortname = self.strip_name(self.name)
        self.cache.clear()

    @staticmethod
    def strip_name(name):
        """Used to autocreate the shortname"""
        stripped = name.lower()\
        .replace('visualizer', '').strip()\
        .replace(' ', '_')
        return stripped

    @classmethod
    def get_for_resource(cls, resource_url, mtype=None, cache=False,
                         context=None):
        """
        Get visualizers given a resource file.

        resource - must have a name or filename attribute or url method
        mime_type - can force method to use your mimetype instead of trying to
        figure it
        context - for specifying the context. Not currently used.
        """

        # get extension(s)
        extensions = []
        base = base_path = urlparse.urlsplit(resource_url).path.lower()
        remainder = ''
        ext = ''
        while True:
            base, ext = posixpath.splitext(base)
            if not ext:
                break
            if base in cls._additional_text_extensions or \
               ext in cls._additional_text_extensions:
                mtype = 'text/plain'
                break
            while ext in mimetypes.suffix_map:
                base, ext = posixpath.splitext(
                    base + mimetypes.suffix_map[ext])
            if ext in mimetypes.encodings_map:
                base, ext = posixpath.splitext(base)
            extensions.append(ext + remainder)
            remainder = ext + remainder

        # see if ext is cached (CHANGE IF USING MORE THAN EXTENSION)
        if cache and ext in cls.cache:
            return cls.cache.accessitem(ext)

        # find matching visualizers
        results = cls.query.find({
            "extensions": {
                "$in": extensions + ['*']
            },
            "active": True
        }).sort('priority', pymongo.DESCENDING)

        if results is None:
            return []

        # find mimetype
        if mtype is None:
            mtype = mimetypes.guess_type(base_path)[0]

        # get visualizers
        if mtype is None:
            # couldnt determine mime type, see if we can match an explicit
            # attachment (no * allowed)
            visualizers = [
            v for v in results
            if any(ext in v.extensions for ext in extensions)
            ]
        else:
            # match mimetype
            visualizers = []
            for result in results:
                if result.mime_types == []:
                    visualizers.append(result)
                for pattern in result.mime_types:
                    if re.search(pattern, mtype) is not None:
                        visualizers.append(result)

        # cache the result
        if cache:
            cls.cache[ext] = visualizers

        return visualizers
