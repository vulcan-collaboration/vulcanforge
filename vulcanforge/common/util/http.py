from datetime import datetime, timedelta

from BeautifulSoup import UnicodeDammit
from webob import exc
import pylons
from tg import response
from vulcanforge.common.helpers import urlquote

from vulcanforge.common.util.filesystem import guess_mime_type

RFC_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'


def raise_404(*args, **kwargs):
    raise exc.HTTPNotFound()


def raise_400(*args, **kwargs):
    raise exc.HTTPBadRequest()


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


def set_download_headers(filename, content_type=None, set_ctype=True,
                         set_disposition=True, file_pointer=None):
    if set_disposition:
        safe_name = filename.encode('utf-8')
        disposition = 'attachment;filename="{}"'.format(safe_name)
        response.headers['Content-Disposition'] = disposition
    if set_ctype:
        if not content_type:
            content_type = guess_mime_type(filename).encode('utf-8')
        response.headers['Content-Type'] = ''
        response.content_type = content_type
        if content_type == 'application/xml' and file_pointer:
            encoding = UnicodeDammit(file_pointer.read()).originalEncoding
            response.headers['Content-Encoding'] = encoding
