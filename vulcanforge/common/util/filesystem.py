import logging
import io
import os
import shutil
import tempfile
import re
import errno
import mimetypes
from contextlib import contextmanager
import zipfile
import hashlib

LOG = logging.getLogger(__name__)
SANITIZE_PATH_REGEX = re.compile(r'(?<=:)[\\/]|[\\/]+')


def sanitize_path(path):
    """
    Sanitizes paths.

        /path           --> /path
        /path/          --> /path/
        \path\          --> /path/
        \/path\/        --> /path/
        \\path\\        --> /path/
        http://path/    --> http://path/
        C:\\path\       --> C://path/

    * doctests are only accurate on systems where os.path.sep == '/'

    >>> sanitize_path('/path')
    '/path'
    >>> sanitize_path('/path/')
    '/path/'

    # '\' escaped for  doctests is '\\\\'
    >>> sanitize_path('\\\\path')
    '/path'
    >>> sanitize_path('\\\\path\\\\')
    '/path/'

    # '\\' escaped for  doctests is '\\\\\\\\'
    >>> sanitize_path('\\\\\\\\path')
    '/path'
    >>> sanitize_path('\\\\\\\\path\\\\\\\\')
    '/path/'

    >>> sanitize_path('\\\\/path')
    '/path'
    >>> sanitize_path('\\\\/path\\\\/')
    '/path/'
    """
    return SANITIZE_PATH_REGEX.sub(os.path.sep, path)


def guess_mime_type(filename):
    """
    Guess MIME type based on filename.
    Applies heuristics, tweaks, and defaults in centralized manner.

    """
    # Consider changing to strict=False
    content_type = mimetypes.guess_type(filename, strict=True)
    if content_type[0]:
        content_type = content_type[0]
    else:
        content_type = 'application/octet-stream'
    return content_type


def import_object(path):
    """e.g. path.to.module:Classname"""
    modulename, classname = str(path).rsplit(':', 1)
    module = __import__(modulename, fromlist=[classname])
    return getattr(module, classname)


def module_resource_path(path):
    """e.g. path.to.module:path/to/file"""
    if ':' in str(path):
        modulename, resource_path = str(path).rsplit(':', 1)
        module = __import__(modulename)
        module_dir = os.path.dirname(module.__file__)
        return os.path.join(module_dir, resource_path)


@contextmanager
def temporary_file(text=False, **kw):
    """Create a temporary file, then delete it when finished"""
    fd, fname = tempfile.mkstemp(text=text, **kw)
    mode = 'w+' if text else 'wb+'
    fp = os.fdopen(fd, mode)
    try:
        yield (fp, fname)
    finally:
        if not fp.closed:
            fp.close()
        os.remove(fname)


@contextmanager
def temporary_dir(**kw):
    dname = tempfile.mkdtemp(**kw)
    try:
        yield dname
    finally:
        func = lambda *args, **kw: LOG.error(
            'error deleting temporary dir {}'.format(dname))
        shutil.rmtree(
            dname,
            onerror=func
        )


@contextmanager
def temporary_zip_extract(fp, zip_module=zipfile.ZipFile, **kw):
    with temporary_dir(**kw) as dirname:
        with zip_module(fp) as zp:
            safe_extract_zip(zp, dirname)
        yield dirname


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def safe_extract_zip(zip_file, target_folder):
    """
    extract the contents of a zipfile.ZipFile object safely by skipping files
    with unsafe path components:

    skips these kinds of names:
        /a
        ../a
        a/../../a
    """
    unsafe_filename_pattern = re.compile(ur'^/|(?:^|/)\.\.(?:$|/)')
    safe_names = [entry for entry in zip_file.namelist() if
                  not unsafe_filename_pattern.search(entry)]
    zip_file.extractall(target_folder, safe_names)


def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if not s1:
        return len(s2)

    previous_row = xrange(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # j+1 instead of j bc previous_row is one character longer
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def md5_signature(file_obj):
    file_obj.seek(0, 2)
    filesize = file_obj.tell()
    file_obj.seek(0, 0)

    if filesize < 64000:
        md5 = hashlib.md5()
        md5.update(file_obj.read())
        return md5.hexdigest()
    else:
        md5 = hashlib.md5()
        md5.update(file_obj.read(32000))
        file_obj.seek(-32000, 2)
        md5.update(file_obj.read(32000))
        return md5.hexdigest()


SEEK_SET = getattr(io, 'SEEK_SET', 0)
SEEK_CUR = getattr(io, 'SEEK_CUR', 1)
SEEK_END = getattr(io, 'SEEK_END', 2)


class FileChunkIO(io.FileIO):
    """
    A class that allows you reading only a chunk of a file.
    """
    def __init__(self, file_pointer, mode='r', offset=0, bytes=None,
                 *args, **kwargs):
        """
        Open a file chunk. The mode can only be 'r' for reading. Offset
        is the amount of bytes that the chunks starts after the real file's
        first byte. Bytes defines the amount of bytes the chunk has, which you
        can set to None to include the last byte of the real file.
        """
        if not mode.startswith('r'):
            raise ValueError("Mode string must begin with 'r'")
        self.file_pointer = file_pointer
        self.offset = offset
        self.bytes = bytes
        self.seek(0)

    def seek(self, offset, whence=SEEK_SET):
        """
        Move to a new chunk position.
        """
        if whence == SEEK_SET:
            self.file_pointer.seek(self.offset + offset)
        elif whence == SEEK_CUR:
            self.seek(self.tell() + offset)
        elif whence == SEEK_END:
            self.seek(self.bytes + offset)

    def tell(self):
        """
        Current file position.
        """
        return self.file_pointer.tell() - self.offset

    def read(self, n=-1):
        """
        Read and return at most n bytes.
        """
        if n >= 0:
            max_n = self.bytes - self.tell()
            n = min([n, max_n])
            return self.file_pointer.read(n)
        else:
            return self.readall()

    def readall(self):
        """
        Read all data from the chunk.
        """
        return self.read(self.bytes - self.tell())

    def readinto(self, b):
        """
        Same as RawIOBase.readinto().
        """
        data = self.read(len(b))
        n = len(data)
        try:
            b[:n] = data
        except TypeError as err:
            import array
            if not isinstance(b, array.array):
                raise err
            b[:n] = array.array(b'b', data)
        return n

    @property
    def closed(self):
        return self.file_pointer.closed

    def close(self):
        # We really do not want to close the underlying file
        pass
