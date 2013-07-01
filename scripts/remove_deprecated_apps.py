import re

from ming.odm import ThreadLocalODMSession
from pylons import app_globals as g

from vulcanforge.artifact.model import ArtifactReference, Shortlink
from vulcanforge.discussion.model import Discussion
from vulcanforge.project.model import AppConfig


def remove_deprecated_ac(ac):
    g.solr.delete(q='app_config_id_s:"{}"'.format(ac._id))
    d_cur = Discussion.query.find({"app_config_id": ac._id})
    for d in d_cur:
        d.delete()
    ArtifactReference.query.remove({
        'artifact_reference.app_config_id': ac._id})
    Shortlink.query.remove({'app_config_id': ac._id})
    ac.delete()
    ThreadLocalODMSession.flush_all()


def remove_all_deprecated():
    cur = AppConfig.query.find({
        'tool_name': {
            "$nin": [re.compile(ep, re.I) for ep in g.tool_manager.tools]
        }
    })
    for ac in cur:
        remove_deprecated_ac(ac)


if __name__ == '__main__':
    remove_all_deprecated()
