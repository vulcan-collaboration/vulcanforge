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
            if project.neighborhood.name == "Users":
                continue  # skip user projects
            if project.get_app_configs_by_kind('chat').count():
                continue  # skip already installed
            yield project

    def _install_tool(self, project):
        with g.context_manager.push(project_id=project._id):
            project.install_app('chat')

    def run(self):

        map(self._install_tool, self._iter_projects())

        ThreadLocalODMSession.flush_all()
