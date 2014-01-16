import logging
from boto.s3.key import Key

from webob import exc
from paste.util.converters import asbool
from pylons import app_globals as g
from tg import expose, redirect, config, response

from vulcanforge.common.controllers import BaseController, BaseRestController
from vulcanforge.common.helpers import urlquote, urlunquote
from vulcanforge.common.util.controller import get_remainder_path
from vulcanforge.common.util.filesystem import guess_mime_type

LOG = logging.getLogger(__name__)


class BucketController(BaseRestController):
    def __init__(self, bucket):
        self.bucket = bucket
        port = bucket.connection.port
        self._base_url = '{protocol}://{host}{port_str}/'.format(
            protocol=bucket.connection.protocol,
            host=bucket.connection.host,
            port_str=':{}'.format(port) if port not in (80, 443) else '',
        )
        super(BaseRestController, self).__init__()

    @expose()
    def get_one(self, *args, **kwargs):
        """
        Get the contents of a key. If force_local=true, serve through this
        controller, otherwise it will redirect to a direct swift url if that
        service is available.

        """
        force_local = True  # TODO: work out content-disposition in direct reqs
        keyname = get_remainder_path(map(urlunquote, args))
        if not g.s3_serve_local and not force_local:
            # redirect to remote
            remote_url = '{base_url}{prefix}/{bucket}{key}'.format(
                base_url=self._base_url,
                prefix=config.get('swift.auth.url_prefix', 'swiftvf'),
                bucket=self.bucket.name,
                key=keyname
            )
            redirect(remote_url)
        g.s3_auth.require_access(self.bucket.name + keyname, method="GET")
        LOG.debug('S3 Proxy GET Request to %s', keyname)
        resp = g.s3.make_request("GET", self.bucket, urlquote(keyname))
        if resp.status != 200:
            raise exc.HTTPNotFound(keyname)
        headers = dict(resp.getheaders())
        content_type = headers.get('content-type', Key.DefaultContentType)
        if content_type == Key.DefaultContentType:
            headers['content-type'] = guess_mime_type(keyname).encode('utf-8')
        for header, val in headers.iteritems():
            response.headers[header] = val
        return resp.read()

    # @expose()  DISABLED FOR NOW
    def post(self, *args, **kwargs):
        keyname = get_remainder_path(map(urlquote, args))
        g.s3_auth.require_access(self.bucket.name + keyname, method="POST")
        LOG.debug('S3 Proxy POST Request to %s', keyname)

    # @expose()  DISABLED FOR NOW
    def put(self, *args, **kwargs):
        keyname = get_remainder_path(map(urlquote, args))
        g.s3_auth.require_access(self.bucket.name + keyname, method="PUT")
        LOG.debug('S3 Proxy PUT Request to %s', keyname)

    # @expose()  DISABLED FOR NOW
    def post_delete(self, *args, **kwargs):
        keyname = get_remainder_path(map(urlquote, args))
        g.s3_auth.require_access(self.bucket.name + keyname, method="DELETE")
        LOG.debug('S3 Proxy DELETE Request to %s', keyname)


class S3ProxyController(BaseController):

    def __init__(self):
        setattr(self, g.s3_bucket.name, BucketController(g.s3_bucket))
