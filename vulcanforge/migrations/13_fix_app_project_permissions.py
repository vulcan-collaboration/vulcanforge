from ming.odm import ThreadLocalODMSession

from vulcanforge.migration.base import BaseMigration
from vulcanforge.project.model import AppConfig


class FixAppProjectPermissions(BaseMigration):
    tool_permissions = {
        "home": "read",
        "admin": "admin"
    }

    def run(self):
        cur = AppConfig.query.find({
            "tool_name": {"$in": self.tool_permissions.keys()}})
        for ac in cur:
            ac.acl = []
            ac.visible_to_role = 'project.{}'.format(
                self.tool_permissions[ac.tool_name])
        ThreadLocalODMSession.flush_all()
