# -*- coding: utf-8 -*-
from datetime import datetime

import logging
import sys
from time import sleep
import bson
from pylons import app_globals as g

from vulcanforge.common.exceptions import ForgeError, CompoundError
from vulcanforge.common.helpers import unescape_unicode
from vulcanforge.common.model.session import artifact_orm_session
from vulcanforge.common.tasks.index import _indexing_disabled
from vulcanforge.search.solr import solarize
from vulcanforge.taskd import task

LOG = logging.getLogger(__name__)


@task
def add_artifacts(ref_ids, update_solr=True, update_refs=True, mod_dates=None):
    """
    Add the referenced artifacts to SOLR and compute artifact's outgoing
    shortlinks

    Temporary optional keyword argument `mod_dates` is a dictionary of
    ref_id: mod_date

    """
    from vulcanforge.artifact.model import ArtifactReference
    exceptions = []
    LOG.info('add artifacts {}'.format(ref_ids))
    with _indexing_disabled(artifact_orm_session._get()):
        solr_docs = []
        ids_to_repost = set()
        for ref_id in ref_ids:
            try:
                ref = ArtifactReference.query.get(_id=ref_id)
                if ref is None:
                    LOG.info('no reference found for %s' % str(ref_id))
                    continue
                artifact = ref.artifact
                if mod_dates:
                    mod_date = mod_dates.get(ref_id, None)
                    if mod_date > artifact.mod_date:
                        LOG.warn("mod_date mismatch for {} expected {} but got "
                                 "{}".format(ref_id, mod_date,
                                             artifact.mod_date))
                        ids_to_repost.add(ref_id)
                        continue
                if update_solr:
                    s = solarize(artifact)
                    if s:
                        solr_docs.append(s)
                        parent = artifact.index_parent()
                        if parent:
                            parent_doc = solarize(parent)
                            if parent_doc:
                                solr_docs.append(parent_doc)
                    else:
                        LOG.info('no solarization found for %s', str(ref_id))
                if update_refs:
                    if artifact.link_content:
                        l_ref_ids = g.artifact.find_shortlink_refs(
                            unescape_unicode(artifact.link_content),
                            upsert=True)
                        for link_ref_id in l_ref_ids:
                            if link_ref_id:
                                ref.upsert_reference(link_ref_id)
            except Exception:
                LOG.error('Error indexing artifact %s', ref_id)
                exceptions.append(sys.exc_info())

        if solr_docs:
            g.solr.add(solr_docs, waitFlush=True, waitSearcher=True)

    if len(exceptions) == 1:
        raise exceptions[0][0], exceptions[0][1], exceptions[0][2]
    if exceptions:
        raise CompoundError(*exceptions)


@task
def del_artifacts(deleted_specs):
    from vulcanforge.artifact.model import ArtifactReference, Shortlink
    update_docs, exceptions, ref_ids = [], [], []
    for delete_spec in deleted_specs:
        ref_ids.append(delete_spec['ref_id'])
        try:
            g.solr.delete(id=delete_spec['ref_id'])
            ref = ArtifactReference.query.get(_id=delete_spec['ref_id'])
            if ref is None:
                LOG.info('no reference found for %s', delete_spec['ref_id'])
                continue
            if delete_spec.get('index_parent_ref_id') and \
            delete_spec['index_parent_ref_id'] != delete_spec['ref_id']:
                parent_ref = ArtifactReference.query.get(
                    _id=delete_spec['index_parent_ref_id'])
                if parent_ref and parent_ref.artifact:
                    update_docs.append(solarize(parent_ref.artifact))
        except Exception:
            LOG.error('Error indexing artifact %s', delete_spec['ref_id'])
            exceptions.append(sys.exc_info())
    if update_docs:
        g.solr.add(update_docs)
    ArtifactReference.query.remove(dict(_id={'$in': ref_ids}))
    Shortlink.query.remove(dict(ref_id={'$in': ref_ids}))
    if len(exceptions) == 1:
        raise exceptions[0][0], exceptions[0][1], exceptions[0][2]
    if exceptions:
        raise CompoundError(*exceptions)
