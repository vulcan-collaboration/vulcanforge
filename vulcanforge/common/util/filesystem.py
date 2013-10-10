import logging
import os
import shutil
import tempfile
import re
import errno
import mimetypes
from contextlib import contextmanager
import zipfile

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


@contextmanager
def temporary_file(text=False, **kw):
    """Create a temporary file, then delete it when finished"""
    fd, fname = tempfile.mkstemp(text=text, **kw)
    mode = 'w+' if text else 'wb+'
    fp = os.fdopen(fd, mode)
    try:
        yield (fp, fname)
    finally:
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
def temporary_zip_extract(fp, **kw):
    with temporary_dir(**kw) as dirname:
        with zipfile.ZipFile(fp) as zp:
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
    name_list = [entry for entry in zip_file.namelist() if
                 not entry.startswith('/') and not entry.startswith('..')]
    zip_file.extractall(target_folder, name_list)


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
