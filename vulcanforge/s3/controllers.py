import logging

from paste.util.converters import asbool
from pylons import app_globals as g
from tg import expose

from vulcanforge.common.controllers import BaseController, BaseRestController
from vulcanforge.common.helpers import urlquote
from vulcanforge.common.util.controller import get_remainder_path

LOG = logging.getLogger(__name__)


class BucketController(BaseRestController):
    def __init__(self, bucket):
        self.bucket = bucket
        super(BaseRestController, self).__init__()

    @expose()
    def get_one(self, *args, **kwargs):
        force_local = asbool(kwargs.get('force_local', False))
        keyname = get_remainder_path(map(urlquote, args))
        if not g.s3_serve_local and not force_local:
            redirect()
        g.s3_auth.require_access(keyname, method="GET")
        LOG.debug('S3 Proxy GET Request to %s', keyname)

    @expose()
    def post(self, *args, **kwargs):
        keyname = get_remainder_path(map(urlquote, args))
        g.s3_auth.require_access(keyname, method="POST")
        LOG.debug('S3 Proxy POST Request to %s', keyname)

    @expose()
    def put(self, *args, **kwargs):
        keyname = get_remainder_path(map(urlquote, args))
        g.s3_auth.require_access(keyname, method="PUT")
        LOG.debug('S3 Proxy PUT Request to %s', keyname)

    @expose()
    def post_delete(self, *args, **kwargs):
        keyname = get_remainder_path(map(urlquote, args))
        g.s3_auth.require_access(keyname, method="DELETE")
        LOG.debug('S3 Proxy DELETE Request to %s', keyname)


class S3ProxyController(BaseController):

    def __init__(self):
        setattr(self, g.s3_bucket.name, BucketController(g.s3_bucket))
