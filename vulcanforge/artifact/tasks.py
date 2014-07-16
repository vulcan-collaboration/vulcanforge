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


def _convert_value_to_doc(value):
    """
    Takes a dictionary representing a SOLR document, modifies and returns it in
    a format that matches what SOLR gives back when searching that document.
    This is used when querying after adding items to confirm that SOLR indeed
    added the item as expected.
    """
    if isinstance(value, dict):  # walk dictionaries
        for key in value.keys():
            if key == 'text' or not value[key] and not (value[key] is False or value[key] == 0):
                del value[key]
                continue
            value[key] = _convert_value_to_doc(value[key])
    elif hasattr(value, '__iter__'):  # convert iterables
        value = [_convert_value_to_doc(item) for item in value]
    elif isinstance(value, bson.ObjectId):
        value = '{}'.format(value)
    elif isinstance(value, datetime):
        value = value.isoformat()[:23].rstrip('0') + 'Z'
    elif isinstance(value, basestring):
        value = value.replace('\r\n', '\n').replace('\r', '\n')
    return value


@task
def add_artifacts(ref_ids, update_solr=True, update_refs=True, mod_dates=None,
                  repost_attempt_count=0):
    """
    Add the referenced artifacts to SOLR and compute artifact's outgoing
    shortlinks

    Temporary optional keyword argument `mod_dates` is a dictionary of
    ref_id: mod_date

    """
    from vulcanforge.artifact.model import ArtifactReference
    exceptions = []
    if repost_attempt_count > 0:
        LOG.info('add_artifacts repost attempt {} for {}'.format(
            repost_attempt_count, ref_ids))
    else:
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
            solr_result = g.solr.add(
                solr_docs, waitFlush=True, waitSearcher=True)

        # confirm indexes were received
        for submitted_doc in solr_docs:
            ref_id = submitted_doc['id']
            result = g.solr.search(q='id:{}'.format(ref_id))
            try:
                actual_doc = result.docs[0]
            except IndexError:
                LOG.warn('index not found after submission: {}'.format(ref_id))
                ids_to_repost.add(ref_id)
                continue
            submitted_doc = _convert_value_to_doc(submitted_doc)
            diffs = []
            for k in set(submitted_doc.keys()).union(actual_doc.keys()):
                s_val = submitted_doc.get(k, '<MISSING>')
                a_val = actual_doc.get(k, '<MISSING>')
                if s_val != a_val:
                    diffs.append('`{}` differs:  {} != {}'.format(k, a_val,
                                                                  s_val))
            if len(diffs) > 0:
                LOG.warn('index mismatch after submission: {};  '
                         'DIFF:\n\t{};  '.format(ref_id, '\n\t'.join(diffs)) +
                         '\nResult: {}'.format(solr_result))
                ids_to_repost.add(ref_id)

        # resubmit any artifacts for indexing that failed
        # limit number of retries to prevent endless loops
        if ids_to_repost:
            if repost_attempt_count < 2:
                sleep(1)
                add_artifacts.post(
                    list(ids_to_repost),
                    repost_attempt_count=repost_attempt_count + 1)
            else:
                LOG.warn('giving up on repost for {}'.format(ids_to_repost))

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
