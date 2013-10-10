# -*- coding: utf-8 -*-

import os
from contextlib import contextmanager
from cStringIO import StringIO

import Image
from pylons import app_globals as g
from ming import schema as S
from ming.odm import FieldProperty
from ming.odm.declarative import MappedClass
from ming.utils import LazyProperty

from .session import project_orm_session
from vulcanforge.common.util import set_download_headers, set_cache_headers
from vulcanforge.common.util.filesystem import guess_mime_type, temporary_file


SUPPORTED_BY_PIL = {
    'image/jpg',
    'image/jpeg',
    'image/pjpeg',
    'image/png',
    'image/x-png',
    'image/gif'
}


class File(MappedClass):
    """Metadata and convenience utils for a file stored in S3"""

    class __mongometa__:
        session = project_orm_session
        name = 'fs'
        indexes = ['filename']

    _id = FieldProperty(S.ObjectId)
    filename = FieldProperty(str, if_missing='unknown')
    keyname = FieldProperty(str, if_missing=None)
    content_type = FieldProperty(str)
    bucket_name = FieldProperty(str, if_missing=None)
    is_thumb = FieldProperty(bool, if_missing=False)
    length = FieldProperty(int, if_missing=None)

    artifact = None  # hack cuz of the way the s3 stuff is set up

    THUMB_URL_POSTFIX = '/thumb'

    def __init__(self, **kw):
        super(File, self).__init__(**kw)
        if self.content_type is None:
            self.content_type = guess_mime_type(self.filename)
        if self.keyname is None:
            self.keyname = self.default_keyname

    @LazyProperty
    def size(self):
        return self.key.size

    @property
    def default_keyname(self):
        keyname = self.filename
        if self.is_thumb:
            keyname += '/thumb'
        return keyname

    @classmethod
    def from_stream(cls, filename, stream, **kw):
        obj = cls(filename=filename, **kw)
        obj.set_contents_from_file(stream)
        return obj

    @classmethod
    def from_path(cls, path, **kw):
        filename = os.path.basename(path)
        obj = cls(filename=filename, **kw)
        obj.set_contents_from_filename(path)
        return obj

    @classmethod
    def from_data(cls, filename, data, **kw):
        obj = cls(filename=filename, **kw)
        obj.set_contents_from_string(data)
        return obj

    @classmethod
    def remove(cls, spec):
        for fobj in cls.query.find(spec):
            fobj.delete()

    def get_thumb_query_params(self):
        return {
            'filename': self.filename,
            'is_thumb': True
        }

    def get_thumb(self):
        if self.is_thumb:
            return None
        thumb_query_params = self.get_thumb_query_params()
        return self.__class__.query.get(**thumb_query_params)

    def get_extension(self):
        name_parts = self.filename.rsplit('.', 1)
        if len(name_parts) > 1:
            return name_parts[-1]
        return None

    @property
    def _s3_headers(self):
        return {'content_type': self.content_type}

    def _update_metadata(self):
        """
        Should be called after each write to the file to update local
        metadata from swift key.
        """
        self.length = self.key.size
        FileReference.upsert_from_file_instance(self)

    def set_contents_from_file(self, file_pointer, headers=None, **kw):
        if headers is None:
            headers = {}
        headers.update(self._s3_headers)
        self.key.set_contents_from_file(file_pointer, headers=headers, **kw)
        self._update_metadata()

    def set_contents_from_filename(self, filename, headers=None, **kw):
        if headers is None:
            headers = {}
        headers.update(self._s3_headers)
        self.key.set_contents_from_filename(filename, headers=headers, **kw)
        self._update_metadata()

    def set_contents_from_string(self, content_string, headers=None, **kw):
        if headers is None:
            headers = {}
        headers.update(self._s3_headers)
        self.key.set_contents_from_string(content_string, headers=headers, **kw)
        self._update_metadata()

    def get_key(self, **kw):
        if not self.bucket_name or self.bucket_name == g.s3_bucket.name:
            bucket = g.s3_bucket
        else:
            bucket = g.s3.get_bucket(self.bucket_name)
        return g.get_s3_key(
            self.keyname, artifact=self.artifact, bucket=bucket, **kw)

    @LazyProperty
    def key(self):
        return self.get_key()

    def delete(self):
        key = self.get_key(insert_if_missing=False)
        if key:
            FileReference.delete_for_key_name(key.name)
            key.delete()
        super(File, self).delete()

    def remote_url(self):
        return g.swift_auth_url(self.keyname, self.bucket_name, self.artifact)

    def local_url(self):
        raise NotImplementedError('local_url')

    def url(self, absolute=False):
        if g.s3_serve_local:
            url = self.local_url()
            if absolute:
                url = g.url(url)
            if self.is_thumb and self.THUMB_URL_POSTFIX:
                url += self.THUMB_URL_POSTFIX
            return url
        else:
            return self.remote_url()

    def read(self):
        return self.key.read()

    @contextmanager
    def wfile(self, **kw):
        with temporary_file(**kw) as (fp, fname):
            yield fp
            fp.seek(0)
            self.set_contents_from_file(fp)

    def serve(self, *args, **kwargs):
        """
        Sets the response headers and serves as a wsgi iter

        NOTE: it is generally better to provide a url directly to the s3 key
        (via the url method) than serving via this method

        """
        set_download_headers(self.filename, str(self.content_type))
        # enable caching
        set_cache_headers(self._id.generation_time)
        in_memory_file = StringIO()
        in_memory_file.write(self.key.read())
        return in_memory_file.getvalue()

    @staticmethod
    def file_is_image(filename=None, content_type=None):
        if content_type is None:
            content_type = guess_mime_type(filename)
        if content_type.lower() in SUPPORTED_BY_PIL:
            return True
        return False

    @classmethod
    def save_thumbnail(cls, filename, image, content_type, thumbnail_size=None,
                       thumbnail_meta=None, square=False, keyname=None):
        format = image.format
        height = image.size[0]
        width = image.size[1]
        if square and height != width:
            sz = max(width, height)
            if 'transparency' in image.info:
                new_image = Image.new('RGBA', (sz,sz))
            else:
                new_image = Image.new('RGB', (sz,sz), 'white')
            if height < width:
                # image is wider than tall, so center horizontally
                new_image.paste(image, ((width - height) / 2, 0))
            elif height > width:
                # image is taller than wide, so center vertically
                new_image.paste(image, (0, (height - width) / 2))
            image = new_image

        if thumbnail_size:
            image.thumbnail(thumbnail_size, Image.ANTIALIAS)

        thumbnail_meta = thumbnail_meta or {}
        thumbnail = cls(
            filename=filename,
            keyname=keyname,
            content_type=content_type,
            is_thumb=True,
            **thumbnail_meta)
        with thumbnail.wfile() as fp_w:
            if 'transparency' in image.info:
                image.save(
                    fp_w, format, transparency=image.info['transparency'])
            else:
                image.save(fp_w, format)

        return thumbnail

    @classmethod
    def save_image(cls, filename, fp, content_type=None, thumbnail_size=None,
                   thumbnail_meta=None, square=False, save_original=False,
                   original_meta=None):
        if not cls.file_is_image(filename, content_type):
            return None, None

        image = Image.open(fp)
        format = image.format
        if save_original:
            original_meta = original_meta or {}
            original = cls(
                filename=filename, content_type=content_type, **original_meta)
            with original.wfile() as fp_w:
                if 'transparency' in image.info:
                    image.save(
                        fp_w, format, transparency=image.info['transparency'])
                else:
                    image.save(fp_w, format)
        else:
            original = None

        thumbnail = cls.save_thumbnail(
            filename,
            image,
            content_type,
            thumbnail_size,
            thumbnail_meta,
            square)

        return original, thumbnail

    def is_image(self):
        return (self.content_type
                and self.content_type.lower() in SUPPORTED_BY_PIL)


class FileReference(MappedClass):
    """
    Persists a single collection mapping of S3 keys to File (and File subclass)
    documents.

    Intended for use going from keys to `File` objects.

    Creation of `FileReference` documents is triggered in the `File` class
    automatically.

    ## Usage:

        >>> my_s3_key = "Allura/something/something/something..."
        >>> FileReference.get_file_from_key_name(my_s3_key)
        <TicketAttachment ...>

    """
    class __mongometa__:
        session = project_orm_session
        name = 'file_reference'
        indexes = ['key_name']

    _id = FieldProperty(S.ObjectId)
    key_name = FieldProperty(S.String)
    file_class_name = FieldProperty(S.String)
    file_id = FieldProperty(S.ObjectId)

    def __repr__(self):
        keys = self.query.mapper.property_index.keys()
        return "<{} {}>".format(
            self.__class__.__name__,
            ' '.join(['{}={!r}'.format(k, getattr(self, k)) for k in keys])
        )

    @classmethod
    def upsert_from_file_instance(cls, file_instance):
        """
        Create/update FileReference document for the file instance.

        @param file_instance: instance of `File` to be referenced, subclasses
            of `File` are supported.
        @type file_instance: File
        """
        query = {
            'key_name': file_instance.key.name
        }
        update = {
            '$set': {
                'file_class_name': file_instance.__class__.__name__,
                'file_id': file_instance._id
            }
        }
        cls.query.update(query, update, upsert=True)

    @classmethod
    def get_file_from_key_name(cls, key_name):
        """
        @param key_name: full key name to look up
        @return: File instance (or subclass of File) for key
        """
        instance = cls.query.get(key_name=key_name)
        if instance is None:
            return None
        return instance.get_file()

    @classmethod
    def delete_for_key_name(cls, key_name):
        cls.query.remove({'key_name': key_name})

    def get_file(self):
        """
        @return: File instance (or subclass of File) for key
        """
        mapper = self.query.mapper.by_classname(self.file_class_name)
        return mapper.mapped_class.query.get(_id=self.file_id)
