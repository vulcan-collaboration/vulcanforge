import re

from vulcanforge.auth.model import User
from vulcanforge.migration.base import BaseMigration


class MigrateMongoPasswords(BaseMigration):

    def run(self):
        user_count = 0
        pw_re = re.compile('^sha256')
        for user in User.query.find({"disabled": False, "password": pw_re}):
            if user.is_real_user() and user.old_password_hashes:
                user.password = user.old_password_hashes[-1]
                user_count += 1
        self.write_output('Fixed {} passwords'.format(user_count))
