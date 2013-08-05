from vulcanforge.auth.model import User
from vulcanforge.common.model.globals import ForgeGlobals
from vulcanforge.migration.base import BaseMigration


class FixFakeOSID(BaseMigration):
    def run(self):
        anon = User.anonymous()
        anon.os_id = None

        root = User.by_username('root')
        if root:
            root.os_id = 0

        admin = User.by_username('admin')
        if admin:
            admin.os_id = ForgeGlobals.inc_user_counter()
