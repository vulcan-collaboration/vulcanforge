import sys
import logging
from contextlib import contextmanager

from pylons import app_globals as g
from ming.odm import session

from vulcanforge.common.exceptions import CompoundError
from vulcanforge.common.model.session import (
    artifact_orm_session,
    main_orm_session
)
from vulcanforge.taskd import task
from vulcanforge.common.util.model import (
    build_model_inheritance_graph,
    dfs
)

LOG = logging.getLogger(__name__)


@task
def unindex_tool(app_config_id=None):
    from vulcanforge.artifact.model import ArtifactReference, Shortlink
    from vulcanforge.project.model import AppConfig
    if app_config_id is None:
        LOG.error("unindex_tool() requires an app_config_id")
        return
    appConfig = AppConfig.query.get(_id=app_config_id)
    LOG.info("Unindexing tool: %s.%s", appConfig.project.shortname,
             appConfig.tool_name)
    g.solr.delete(q='project_id_s:%s AND mount_point_s=%s' % (
        appConfig.project._id, appConfig.options.mount_point
    ))
    ArtifactReference.query.remove({
        'artifact_reference.app_config_id': appConfig._id
    })
    Shortlink.query.remove({
        'app_config_id': appConfig._id
    })


@task
def reindex_tool(app_config_id=None):
    from vulcanforge.artifact.tasks import add_artifacts
    from vulcanforge.artifact.model import (
        Artifact,
        ArtifactReference,
        Shortlink
    )
    from vulcanforge.project.model import AppConfig
    if app_config_id is None:
        LOG.error("reindex_tool() requires an app_config_id")
        return

    appConfig = AppConfig.query.get(_id=app_config_id)
    unindex_tool(app_config_id)
    graph = build_model_inheritance_graph()
    LOG.info("Reindexing tool: %s.%s", appConfig.project.shortname,
        appConfig.tool_name)

    # Traverse the inheritance graph, finding all artifacts that
    # belong to this project
    for _, a_cls in dfs(Artifact, graph):
        if not session(a_cls):
            continue
        LOG.info('  %s', a_cls)
        ref_ids = []
        # Create artifact references and shortlinks
        for a in a_cls.query.find({'app_config_id': appConfig._id}):
            try:
                ArtifactReference.from_artifact(a)
                Shortlink.from_artifact(a)
            except Exception:
                LOG.exception('Making ArtifactReference/Shortlink from %s', a)
                continue
            ref_ids.append(a.index_id())
        main_orm_session.flush()
        artifact_orm_session.clear()
        try:
            add_artifacts(ref_ids)
        except CompoundError, err:
            LOG.exception('Error indexing artifacts:\n%r', err)
            LOG.error('%s', err.format_error())
        main_orm_session.flush()
        main_orm_session.clear()


@task
def commit():
    g.solr.commit()


@contextmanager
def _indexing_disabled(session):
    session.disable_artifact_index = session.skip_mod_date = True
    try:
        yield session
    finally:
        session.disable_artifact_index = session.skip_mod_date = False


@task
def add_global_objs(ref_ids):
    """
    Add records to SOLR
    """
    from vulcanforge.common.model.index import GlobalObjectReference
    exceptions = []

    global_docs = []
    for ref_id in ref_ids:
        try:
            ref = GlobalObjectReference.query.get(_id=ref_id)
            if ref is None:
                LOG.info('skipping ref_id %s: no reference found', ref_id)
                continue
            global_obj = ref.object
            if global_obj is None:
                LOG.info('skipping ref_id %s: no object found', ref_id)
                continue
            else:
                global_obj_index = global_obj.index()
            if global_obj_index is not None:
                global_docs.append(global_obj_index)
        except Exception:
            LOG.error('Error indexing object %s', ref_id)
            exceptions.append(sys.exc_info())

    if global_docs:
        g.solr.add(global_docs)

    if len(exceptions) == 1:
        raise exceptions[0][0], exceptions[0][1], exceptions[0][2]
    if exceptions:
        raise CompoundError(*exceptions)


@task
def del_global_objs(ref_ids):
    from vulcanforge.common.model.index import GlobalObjectReference
    LOG.info('del_global_objs')
    for ref_id in ref_ids:
        g.solr.delete(id=ref_id)
    GlobalObjectReference.query.remove(dict(_id={'$in': ref_ids}))
