from pylons import app_globals as g
from ming.odm.odmsession import ThreadLocalODMSession
from vulcanforge.migration.base import BaseMigration
from vulcanforge.project.model import Project


class InstallChatTool(BaseMigration):

    def _iter_projects(self):
        cursor = Project.query.find({
            'shortname': {'$ne': '--init--'}
        })
        for project in cursor:
            if project.neighborhood.name != "Users":
                continue  # skip non-user projects
            if project.get_app_configs_by_kind('chat').count() == 0:
                continue  # skip not installed
            yield project

    def _uninstall_tool(self, project):
        try:
            with g.context_manager.push(project_id=project._id):
                project.uninstall_app('chat')
        except:
            self.log.warn('Could not uninstall chat for %s', project.shortname)

    def run(self):

        map(self._uninstall_tool, self._iter_projects())

        ThreadLocalODMSession.flush_all()
