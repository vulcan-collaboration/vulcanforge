import logging
from boto.s3.key import Key

from bson import ObjectId
from webob import exc
from pylons import app_globals as g
from tg import expose, redirect, config, response

from vulcanforge.common.controllers import BaseController, BaseRestController
from vulcanforge.common.helpers import urlquote, urlunquote
from vulcanforge.common.util.controller import get_remainder_path
from vulcanforge.common.util.filesystem import guess_mime_type

from vulcanforge.exchange.model import ExchangeNode

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
        Get the contents of a key.

        """
        keyname = get_remainder_path(map(urlunquote, args))

        if 'node_id' in kwargs:
            node_id = kwargs.pop('node_id')
            node = ExchangeNode.query.get(_id=ObjectId(node_id))
            if not node:
                raise exc.HTTPNotFound
            artifact_keyname = urlunquote(g.make_s3_keyname('', node.artifact))
            if artifact_keyname in keyname:
                g.security.require_access(node, 'read')
            else:
                raise exc.HTTPUnauthorized
        else:
            g.s3_auth.require_access(self.bucket.name + keyname, method="GET")

        LOG.debug('S3 Proxy GET Request to %s', keyname)

        not_found = False
        resp = g.s3.make_request("GET", self.bucket, urlquote(keyname))
        if resp.status != 200:
            not_found = True

            # FIX:
            # Somewhat of a hack but needed because of special characters in
            # URLs
            if '#' in keyname:
                parts = keyname.split('#')
                part_2_rev = urlquote(parts[1])
                rev_keyname = "#".join([parts[0], part_2_rev])

                resp = g.s3.make_request("GET", self.bucket, urlquote(rev_keyname))
                if resp.status == 200:
                    not_found = False

        if not_found:
            # Try again with the
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
