import logging

from pylons import app_globals as g
from ming.odm.odmsession import ThreadLocalODMSession

from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.home.project_main import ProjectHomeApp
from vulcanforge.project.model import AppConfig


LOG = logging.getLogger(__name__)


class SetHomeToolAcl(BaseMigration):

    def _iter_app_configs(self):
        cursor = AppConfig.query.find({'tool_name':'home'})

        for app_config in cursor:
            if not app_config.acl and app_config.project is not None:
                yield app_config

    def _set_acl(self, app_config):
        with g.context_manager.push(project_id=app_config.project._id):
            app = app_config.instantiate()
            app.set_acl(ProjectHomeApp.default_acl())

    def run(self):
        self.write_output('Setting ACL on Home tools ...')

        map(self._set_acl, self._iter_app_configs())
        ThreadLocalODMSession.flush_all()

        self.write_output('Finished setting ACL.')
