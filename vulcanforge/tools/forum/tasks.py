import logging

from pylons import tmpl_context as c

from vulcanforge.taskd import task
from .model import Forum, ForumThread

LOG = logging.getLogger(__name__)


@task
def calc_forum_stats(shortname):
    forum = Forum.query.get(
        shortname=shortname, app_config_id=c.app.config._id)
    if forum is None:
        LOG.error("Error looking up forum: %r", shortname)
        return
    forum.update_stats()

@task
def calc_thread_stats(thread_id):
    thread = ForumThread.query.get(_id=thread_id)
    if thread is None:
        LOG.error("Error looking up thread: %r", thread_id)
    thread.update_stats()
