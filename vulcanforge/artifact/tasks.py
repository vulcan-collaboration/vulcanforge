# -*- coding: utf-8 -*-

import logging
import sys
from pylons import app_globals as g

from vulcanforge.common.exceptions import ForgeError, CompoundError
from vulcanforge.common.model.session import artifact_orm_session
from vulcanforge.common.tasks.index import LOG, _indexing_disabled
from vulcanforge.search.solr import solarize
from vulcanforge.taskd import task


LOG = logging.getLogger(__name__)


@task
def process_artifact(processor_name, context, index_id, verbose=False):
    from vulcanforge.artifact.model import ArtifactReference
    from vulcanforge.artifact.model import ArtifactProcessor
    aref = ArtifactReference.query.get(_id=index_id)
    if not aref or not aref.artifact:
        raise ForgeError('artifact with index_id {} not found'.format(
            index_id))
    ArtifactProcessor.process(
        processor_name, aref.artifact, context, verbose=verbose)


@task
def add_artifacts(ref_ids, update_solr=True, update_refs=True):
    """
    Add the referenced artifacts to SOLR and compute artifact's outgoing
    shortlinks

    """
    from vulcanforge.artifact.model import (
        ArtifactReference,
        find_shortlink_refs
    )
    exceptions = []
    LOG.info('add artifacts')
    with _indexing_disabled(artifact_orm_session._get()):
        allura_docs = []
        for ref_id in ref_ids:
            try:
                ref = ArtifactReference.query.get(_id=ref_id)
                if ref is None:
                    LOG.info('no reference found for %s' % str(ref_id))
                    continue
                artifact = ref.artifact
                if update_solr:
                    s = solarize(artifact)
                    if s is not None:
                        allura_docs.append(s)
                        parent = artifact.index_parent()
                        if parent:
                            allura_docs.append(solarize(parent))
                    else:
                        LOG.info('no solarization found for %s', str(ref_id))
                if update_refs:
                    if artifact.link_content:
                        l_ref_ids = find_shortlink_refs(
                            artifact.link_content, upsert=True)
                        for link_ref_id in l_ref_ids:
                            if link_ref_id:
                                ref.upsert_reference(link_ref_id)
            except Exception:
                LOG.error('Error indexing artifact %s', ref_id)
                exceptions.append(sys.exc_info())
        if allura_docs:
            g.solr.add(allura_docs)

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
