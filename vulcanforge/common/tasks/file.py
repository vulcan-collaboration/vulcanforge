# -*- coding: utf-8 -*-

import logging

from datetime import datetime
from boto.exception import S3ResponseError

from pylons import app_globals as g

from vulcanforge.taskd import task

LOG = logging.getLogger(__name__)


@task
def delete_content_from_s3(file_id):
    from vulcanforge.common.model.file import FileArtifact
    before = datetime.now()

    file_artifact = FileArtifact.query.get(_id=file_id)
    if file_artifact is not None:
        try:
            if file_artifact.upload_completed:
                g.delete_s3_key(file_artifact.get_key())
            else:
                file_artifact.multipart.cancel_upload()
        except S3ResponseError, s3e:
            LOG.info("Failed to delete {} from s3: {}".format(
                file_artifact.item_key,
                s3e.reason
            ))
        else:
            LOG.info("Deleted {} from s3 in {}s".format(
                file_artifact.item_key,
                str(datetime.now() - before)
            ))