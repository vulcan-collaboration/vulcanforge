import logging

from pylons import tmpl_context as c, app_globals as g
from vulcanforge.artifact.model import ArtifactReference
from vulcanforge.artifact.tasks import add_artifacts

from vulcanforge.taskd import task

LOG = logging.getLogger(__name__)


@task
def add_tickets(ref_ids, **kw):
    add_artifacts(ref_ids, **kw)
    ac_ids = set()
    for ref_id in ref_ids:
        aref = ArtifactReference.query.get(_id=ref_id)
        if aref:
            ac_ids.add(aref.artifact_reference['app_config_id'])
        else:
            LOG.warn(
                'No ArtifactReference object for ticket {}'.format(ref_id))
    for app_config_id in ac_ids:
        with g.context_manager.push(app_config_id=app_config_id):
            refresh_search_counts()


@task
def refresh_search_counts():
    """
    Refresh the search bin counts that appear in the sidebar

    """
    c.app.globals.refresh_counts()
    c.app.globals.query.session.flush()
