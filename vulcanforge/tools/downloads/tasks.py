# -*- coding: utf-8 -*-

import logging

from datetime import datetime
from boto.exception import S3ResponseError

from pylons import app_globals as g

from vulcanforge.taskd import task

LOG = logging.getLogger(__name__)


@task
def delete_content_from_s3(file_id):
    from vulcanforge.tools.downloads import model as DM
    before = datetime.now()

    downloads_file = DM.ForgeDownloadsFile.query.get(_id=file_id)
    if downloads_file is not None:
        try:
            if downloads_file.upload_completed:
                g.delete_s3_key(downloads_file.get_key())
            else:
                downloads_file.multipart.cancel_upload()
        except S3ResponseError as s3e:
            downloads_file.extra_info['s3_delete_error'] = {
                'status': s3e.status,
                'reason': s3e.reason
            }
            LOG.info("Failed to delete {} from s3: {}".format(
                downloads_file.item_key,
                s3e.reason
            ))
        else:
            LOG.info("Deleted {} from s3 in {}s".format(
                downloads_file.item_key,
                str(datetime.now() - before)
            ))
