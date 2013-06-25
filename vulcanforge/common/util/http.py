from datetime import datetime, timedelta

from BeautifulSoup import UnicodeDammit
from paste.httpheaders import CACHE_CONTROL, EXPIRES
import pylons
from tg import response

from vulcanforge.common.util.filesystem import guess_mime_type

RFC_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'


def set_cache_headers(last_modified=None, expires_in=365):
    response.headers['Cache-Control'] = ', '.join((
        'public', 'max-age=31536000', 'must-revalidate'
    ))
    if last_modified:
        response.headers['Last-Modified'] = str(
            last_modified.strftime(RFC_FORMAT))
    else:
        response.headers.pop('Last-Modified', None)
    expire_dt = datetime.now() + timedelta(expires_in)
    response.headers['Expires'] = str(expire_dt.strftime(RFC_FORMAT))
    response.headers.pop('Pragma', None)
    response.conditional_response = True


def get_client_ip(request=None):
    if request is None:
        request = pylons.request
    try:
        ip = request.environ.get("X_FORWARDED_FOR") or\
            request.environ.get("HTTP_X_FORWARDED_FOR") or\
            request.environ.get("REMOTE_ADDR")
    except TypeError:  # no request global registered
        ip = None
    return ip


def set_download_headers(filename=None, content_type=None, set_ctype=True,
                         file_pointer=None):
    response.headers.add(
        'Content-Disposition',
        'attachment;filename=' + filename.encode('utf-8').replace(' ', '_'))
    if set_ctype:
        if not content_type:
            content_type = guess_mime_type(filename).encode('utf-8')
        response.headers['Content-Type'] = ''
        response.content_type = content_type
        if content_type == 'application/xml' and file_pointer:
            response.headers['Content-Encoding'] =\
            UnicodeDammit(file_pointer.read()).originalEncoding


def cache_forever():
    headers = [
        (k, v) for k, v in response.headers.items()
        if k.lower() not in ('pragma', 'cache-control')]
    delta = CACHE_CONTROL.apply(
        headers,
        public=True,
        max_age=60 * 60 * 24 * 365)
    EXPIRES.update(headers, delta=delta)
    response.headers.pop('cache-control', None)
    response.headers.pop('pragma', None)
    response.headers.update(headers)
