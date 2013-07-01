from ming.odm import session
from pylons import app_globals as g

from vulcanforge.common.exceptions import CompoundError
from vulcanforge.common.model.session import (
    main_orm_session,
    artifact_orm_session
)
from vulcanforge.common.tasks.index import LOG, add_global_objs
from vulcanforge.common.util.model import chunked_find
from vulcanforge.artifact.tasks import add_artifacts
from vulcanforge.taskd import task


@task
def unindex_project(project_id=None):
    from vulcanforge.artifact.model import ArtifactReference, Shortlink
    from vulcanforge.project.model import Project, AppConfig
    if project_id is None:
        LOG.error("unindex_project() requires a project id")
        return
    project = Project.query.get(_id=project_id)
    LOG.info("Unindexing project: %s", project.shortname)
    g.solr.delete(q='shortname_s:"{}" AND neighborhood_id_s:{}'.format(
        project.shortname,
        project.neighborhood_id
    ))
    ArtifactReference.query.remove({
        'artifact_reference.project_id': project._id
    })
    Shortlink.query.remove({'project_id': project._id})


@task
def reindex_project(project_id):
    from vulcanforge.common.model.index import GlobalObjectReference
    from vulcanforge.artifact.model import (
        ArtifactReference,
        Shortlink
    )
    from vulcanforge.artifact.util import iter_artifact_classes
    from vulcanforge.neighborhood.marketplace.model import ProjectAdvertisement
    from vulcanforge.project.model import Project, AppConfig
    project = Project.query.get(_id=project_id)
    unindex_project(project_id)
    LOG.info("Reindexing project: %s", project)
    app_config_ids = []
    for ac in project.app_configs:
        ac.clean_acl()
        app_config_ids.append(ac._id)
    session(AppConfig).flush()

    # Traverse the inheritance graph, finding all artifacts that
    # belong to this project
    for a_cls in iter_artifact_classes():
        LOG.info('  %s', a_cls)
        ref_ids = []
        # Create artifact references and shortlinks
        try:
            artifacts = a_cls.query.find({
                'app_config_id': {'$in': app_config_ids}
            })
            for a in artifacts:
                try:
                    ArtifactReference.from_artifact(a)
                    Shortlink.from_artifact(a)
                except:
                    LOG.exception(
                        'Making ArtifactReference/Shortlink from %s', a)
                else:
                    ref_ids.append(a.index_id())
        except:
            LOG.exception('Error querying %s', a_cls)
        main_orm_session.flush()
        artifact_orm_session.clear()
        try:
            add_artifacts(ref_ids)
        except CompoundError, err:
            LOG.exception('Error indexing artifacts:')
            LOG.error('%s', err.format_error())
        except Exception:
            LOG.exception('Error indexing artifacts:')
        main_orm_session.flush()
        main_orm_session.clear()

    # Marketplace posts must also be indexed
    global_ref_ids = []
    for ad in ProjectAdvertisement.query.find({'project_id': project._id}):
        if ad.indexable():
            GlobalObjectReference.from_object(ad)
            global_ref_ids.append(ad.index_id())

    sesh = session(GlobalObjectReference)
    sesh.flush()
    sesh.clear()
    LOG.info('indexing {} project marketplace ads'.format(len(global_ref_ids)))
    try:
        add_global_objs(global_ref_ids)
    except Exception:
        LOG.exception('Error indexing global')


@task
def update_project_indexes(project_id=None):
    from vulcanforge.artifact.model import ArtifactReference
    from vulcanforge.neighborhood.marketplace.model import ProjectAdvertisement
    from vulcanforge.project.model import Project, AppConfig
    if project_id is None:
        LOG.error('update_project_indexes() requires a project id')
        return
    project = Project.query.get(_id=project_id)
    LOG.info("Updating project indexes: %s", project)

    # update marketplace posts
    ad_query_params = {
        'project_id': project_id,
    }
    ad_cursor = ProjectAdvertisement.query.find(ad_query_params)
    ad_ref_ids = [ad.index_id() for ad in ad_cursor if ad.indexable()]
    try:
        add_global_objs(ad_ref_ids)
    except Exception:
        LOG.exception("Error indexing globals for project")

    # build list of app_configs
    app_config_ids = []
    for ac in project.app_configs:
        ac.clean_acl()
        app_config_ids.append(ac._id)
    session(AppConfig).flush_all()

    # update artifact references
    ref_query_params = {
        'artifact_reference.app_config_id': {
            '$in': app_config_ids,
        },
    }
    for ref_cursor in chunked_find(ArtifactReference, ref_query_params):
        ref_ids = [r._id for r in ref_cursor]
        try:
            add_artifacts(ref_ids)
        except CompoundError, err:
            LOG.exception('Error indexing artifacts:')
            LOG.error('%s', err.format_error())
        except Exception:
            LOG.exception('Error indexing artifacts:')
        main_orm_session.clear()
