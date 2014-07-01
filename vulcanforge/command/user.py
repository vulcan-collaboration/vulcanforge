from base64 import b64encode
from datetime import datetime, timedelta
from hashlib import sha256
from os import urandom
import os

from ming.odm import session
from vulcanforge.auth.model import User, AuthGlobals
from vulcanforge.auth.tasks import (
    reset_ldap_users,
    register_ldap,
    upload_ssh_ldap
)
from vulcanforge.taskd import MonQTask

from .base import Command


class UserCommandError(Exception):
    pass


class CreateUserCommand(Command):

    min_args = 5
    max_args = 5

    usage = "ini_file display_name username email password"
    summary = "Create a user manually"

    parser = Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()

        display_name = self.args[1]
        username = self.args[2]
        email = self.args[3]
        password = self.args[4]

        user_doc = {
            'display_name': display_name,
            'username': username,
            'password': password,
        }
        user = User.register(user_doc)
        user.claim_address(email, confirmed=True)
        user.set_pref('email_address', email)


class ExpireUsersCommand(Command):
    min_args = 1
    max_args = 1

    usage = 'ini_file'
    summary = "Disable Users that have not logged in in x months"

    parser = Command.standard_parser(verbose=True)

    def command(self):
        from tg import config
        self.basic_setup()

        lifetime = timedelta(
            days=30 * int(config.get('auth.user.inactivity_period', 6)))
        epoch = datetime.utcnow() - lifetime
        User.query.update(
            {
                'username': {'$nin': ['*anonymous', 'root']},
                'last_login': {'$lt': epoch}
            },
            {'$set': {'disabled': True}},
            multi=True
        )
        session(User).flush()


class EnableUserCommand(Command):
    min_args = 2
    max_args = 2

    usage = 'ini_file username'
    summary = 'Enable user by username'

    parser = Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()

        username = self.args[1]
        user = User.by_username(username)
        if not user:
            raise UserCommandError('User not found')
        if not user.disabled:
            raise UserCommandError('User is already enabled')
        user.disabled = False
        session(User).flush()


class DisableUserCommand(Command):
    min_args = 2
    max_args = 2

    usage = 'ini_file username'
    summary = 'Disable user by username'

    parser = Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()

        username = self.args[1]
        user = User.by_username(username)
        if not user:
            raise UserCommandError('User not found')
        if user.disabled:
            raise UserCommandError('User is already disabled')
        user.delete_account()
        session(User).flush()


class ExpirePasswordsCommand(Command):

    min_args = 1
    max_args = 1

    usage = "ini_file"
    summary = "Expire old passwords"

    parser = Command.standard_parser(verbose=True)

    def command(self):
        from tg import config
        self.basic_setup()
        # determine password lifetime epoch
        months = int(config.get('auth.pw.lifetime.months', 6))
        weeks = int(config.get('auth.pw.lifetime.weeks', 0))
        days = int(config.get('auth.pw.lifetime.days', 0))
        hours = int(config.get('auth.pw.lifetime.hours', 0))
        minutes = int(config.get('auth.pw.lifetime.minutes', 0))
        lifetime = timedelta(
            days=30 * months + 7 * weeks + days,
            hours=hours,
            minutes=minutes
        )
        epoch = datetime.utcnow() - lifetime
        # find users that have expired passwords that have not been reset
        users = User.query.find({
            'username': {'$nin': ['*anonymous', 'root']},
            '$or': [
                {'password_set_at': {'$lte': epoch}},
                {'password_set_at': {'$exists': False}},
            ]
        })
        # assign temporary passwords for these users
        print 'found {} users with expired passwords ({!r})'.format(
            users.count(), epoch)
        for user in users.all():
            if user.needs_password_reset:
                print 'already expired: {!r}'.format(user.username)
                continue
            print 'expiring: {!r}'.format(user.username)
            temp_pw = b64encode(urandom(32))
            user.set_password(temp_pw, as_admin=True, set_time=False)
            user.password_set_at = datetime.utcnow() - timedelta(days=365)
            user.needs_password_reset = True
        User.query.session.flush()


class ResetPasswordHistoryCommand(Command):
    min_args = 2
    max_args = 2

    usage = "ini_file username"
    summary = "Erase a user's old passwords and mark their password as 180" \
              " days old"

    parser = Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()

        username = self.args[1]

        user = User.by_username(username)
        if not user:
            raise Exception("No User found for username {!r}".format(username))

        user.old_password_hashes = []
        user.password_set_at = datetime.utcnow() - timedelta(days=180)
        user.needs_password_reset = False
        user.query.session.flush()
        user.query.session.close()
        print "password history reset for user {!r}".format(username)


class RefreshUsersCommand(Command):
    min_args = 1
    max_args = 1

    usage = "ini_file"
    summary = "Re-create LDAP database and chroot user folders (if supported)"

    parser = Command.standard_parser(verbose=True)

    REPO_LINK = "/git"
    HAS_CHROOT = os.path.islink(REPO_LINK)

    def reset_LDAP(self, config):
        "Removes all users from LDAP database"
        import ldap
        try:
            try:
                con = ldap.initialize(config['auth.ldap.server'])
                con.bind_s(config['auth.ldap.admin_dn'],
                           config['auth.ldap.admin_password'])
                results = con.search_s(config['auth.ldap.suffix'],
                                       ldap.SCOPE_SUBTREE,
                                       "cn=*", ["uid", "uidNumber"])
                for dn_u, rdict in results:
                    if rdict['uid'] != 'john' and rdict['uidNumber'] != '1000':
                        con.delete_s(dn_u)
            except Exception, e:
                print "Exception reseting LDAP database: {}".format(e)
                raise
        finally:
            try:
                con.unbind_s()
            except Exception, e:
                pass
        # reset uids
        ag = AuthGlobals.upsert()
        ag.next_uid = 10000
        session(AuthGlobals).flush()

    def random_password(self):
        "Generates and returns a random password"
        password = urandom(32).encode('hex')
        salt = urandom(4).encode('hex')
        hashpass = sha256(salt + password.encode('utf-8')).digest()
        return 'sha256' + salt + b64encode(hashpass)

    def add_LDAP_user(self, user, config):
        """add user to LDAP database"""
        import ldap
        pw = (self.random_password() if user.needs_password_reset
              else user.old_password_hashes[-1])
        pw = pw.encode('utf-8')
        uid = str(AuthGlobals.get_next_uid())
        uname = user.username.encode('utf-8')
        display_name = user.display_name.encode('utf-8')
        dn_u = 'uid=%s,%s' % (uname, config['auth.ldap.suffix'])
        try:
            try:
                con = ldap.initialize(config['auth.ldap.server'])
                con.bind_s(config['auth.ldap.admin_dn'],
                           config['auth.ldap.admin_password'])
                ldif_u = ldap.modlist.addModlist(dict(
                    uid=uname,
                    userPassword=pw,
                    objectClass=['account', 'posixAccount'],
                    cn=display_name,
                    uidNumber=uid,
                    gidNumber='10001',
                    homeDirectory='/home/' + uname,
                    loginShell='/bin/bash',
                    gecos=uname,
                    description='SCM user account'))
                try:
                    con.add_s(dn_u, ldif_u)
                except ldap.ALREADY_EXISTS:
                    msg = 'Trying to create existing user {}'
                    print msg.format(user.username)
            except Exception, e:
                msg = "Exception adding user {} to LDAP database: {}"
                print msg.format(user.username, e)
                raise
        finally:
            try:
                con.unbind_s()
            except Exception, e:
                pass

    def reset_chroot(self):
        """Remove existing user home folders in chroot (if supported)"""
        try:
            if self.HAS_CHROOT:
                task = reset_ldap_users.post()
                MonQTask.wait_for_tasks(query={
                    '_id': task._id, 'state': {'$in': ['ready', 'busy']}
                }, timeout=120000)
        except Exception, e:
            print "Exception reseting chroot home folders."
            raise

    def command(self):
        """
        Re-create LDAP database and chroot user folders (if supported.)

        Use of asynchronous tasks for chroot user home folder operations
        reflects the fact that only Taskd is orchestrated for chroot access.

        """
        from tg import config
        self.basic_setup()

        # reset LDAP database and chroot home folders (if supported)
        self.reset_LDAP(config)
        self.reset_chroot()

        # exclude these users from the command
        special_users = ['*anonymous', 'root']

        # add users to LDAP and asynchronously create chroot user home folder
        count = 0
        users = User.query.find({'username': {'$nin': special_users}}).all()
        task = None
        for user in users:
            self.add_LDAP_user(user, config)
            if self.HAS_CHROOT:
                task = register_ldap.post(user.username)
            count += 1
        print "Refreshed {} users.".format(count)

        # wait for last task to complete
        if task:
            MonQTask.wait_for_tasks(query={
                '_id': task._id, 'state': {'$in': ['ready', 'busy']}
            }, timeout=240000)

        # asynchronously upload user public keys
        count = 0
        if self.HAS_CHROOT:
            for user in users:
                public_key = getattr(user, 'public_key', None)
                if public_key:
                    upload_ssh_ldap.post(user.username, public_key)
                    count += 1
        print "Uploaded {} public keys.".format(count)
