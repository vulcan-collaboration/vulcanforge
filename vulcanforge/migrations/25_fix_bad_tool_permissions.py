import logging

from pylons import app_globals as g
from ming.odm.odmsession import ThreadLocalODMSession

from vulcanforge.migration.base import BaseMigration
from vulcanforge.project.model import AppConfig, ProjectRole


LOG = logging.getLogger(__name__)


class FixBadToolPermissionGrants(BaseMigration):

    def _iter_app_configs(self):
        cursor = AppConfig.query.find()

        for app_config in cursor:
            if app_config.project:
                yield app_config

    def _fix_grants(self, app_config):
        for grant in app_config.acl:
            pr = ProjectRole.query.get(_id=grant.role_id)
            if pr and pr.project_id != app_config.project._id:
                if pr.name != 'Admin':
                    msg = "Unexpected bad grant in "
                    msg += "project {} tool {} role {}."
                    LOG.warn(msg.format(app_config.project.shortname,
                                        app_config.options['mount_point'],
                                        grant['permission']))
                else:
                    nr = app_config.project.named_roles
                    role = [x for x in nr if x.name == 'Admin']
                    admin_role_id = role[0]._id if role else None
                    if admin_role_id:
                        grant.role_id = admin_role_id

    def run(self):
        self.write_output('Fixing bad tool permission grants...')

        map(self._fix_grants, self._iter_app_configs())
        ThreadLocalODMSession.flush_all()

        self.write_output('Finished fixing bad tool permission grants.')
