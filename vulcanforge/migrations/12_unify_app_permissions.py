import logging

from ming.odm.odmsession import ThreadLocalODMSession
from vulcanforge.auth.schema import ACL, ACE
from vulcanforge.migration.base import BaseMigration
from vulcanforge.project.model import AppConfig, Project

LOG = logging.getLogger(__name__)


class RemoveMarkdownLineOrientatedProcessor(BaseMigration):
    """WARNING: this migration is NOT idempotent. DO NOT RUN TWICE"""

    def run(self):
        # only runs on wiki pages and tickets

        # Change old permission names to new ones
        for app_config in AppConfig.query.find().all():
            # downloads permission: configure -> admin
            if app_config.tool_name == 'downloads':
                for ace in app_config.acl:
                    if ace.permission == 'configure':
                        ace.permission = 'admin'

            # discussions permission: configure -> write
            elif app_config.tool_name == 'discussion':
                for ace in app_config.acl:
                    if ace.permission == 'configure':
                        ace.permission = 'write'

            # discussions permission: configure, admin -> admin
            #                       create, edit, delete -> write
            elif app_config.tool_name == 'wiki':
                new_acl = []
                admin_role_id_set = set()
                write_role_id_set = set()
                for ace in app_config.acl:
                    if ace.permission in ('configure', 'admin'):
                        admin_role_id_set.add(ace.role_id)
                    elif ace.permission in ('create', 'edit', 'delete'):
                        write_role_id_set.add(ace.role_id)
                    else:
                        new_acl.append(ace)

                for admin_role_id in admin_role_id_set:
                    new_ace = ACE.allow(admin_role_id, 'admin')
                    new_acl.append(new_ace)

                for write_role_id in write_role_id_set:
                    new_ace = ACE.allow(write_role_id, 'write')
                    new_acl.append(new_ace)

                app_config.acl = new_acl

        ThreadLocalODMSession.flush_all()

        # Updating the project permissions: update, create -> write
        for project in Project.query.find().all():
            new_acl = []
            write_role_id_set = set()
            for ace in project.acl:
                if ace.permission in ('create', 'update'):
                    write_role_id_set.add(ace.role_id)
                else:
                    new_acl.append(ace)

            for write_role_id in write_role_id_set:
                new_ace = ACE.allow(write_role_id, 'write')
                new_acl.append(new_ace)

            project.acl = new_acl