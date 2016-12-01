import os
import re
import urllib
import logging
from datetime import datetime
from random import randint
from hashlib import sha1, sha256
from base64 import b64encode, b64decode
from paste.deploy.converters import asint

from webob import exc
from tg import config, response, request
from pylons import app_globals as g, tmpl_context as c
from ming.utils import LazyProperty
from vulcanforge.common.util import get_client_ip, cryptographic_nonce
from vulcanforge.project.model import ProjectRole

try:
    import ldap
    from ldap import modlist
except ImportError:
    ldap = modlist = None

from vulcanforge.auth.model import User, AuthGlobals
from vulcanforge.auth.tasks import (
    register_ldap,
    upload_ssh_ldap
)
from vulcanforge.auth.exceptions import PasswordAlreadyUsedError

LOG = logging.getLogger(__name__)


class PasswordLengthError(Exception):
    """Password too long"""
    pass


class BaseAuthenticationProvider(object):
    """
    An interface to provide authentication services for VulcanForge.

    To use a new provider, specify a new auth_provider in your .ini file:

    auth_provider = path/to/provider:MyAuthProvider

    """
    PWRE = re.compile(r'^(?P<method>\{SSHA(?P<saltlen>\d+)?\}).*')

    def __init__(self):
        self.saltlen = asint(config.get('auth.saltlength', 32))
        self.maxpwlen = asint(config.get('auth.pw.max_length', 512))

    @property
    def session(self):
        return request.environ['beaker.session']

    @LazyProperty
    def user_cls(self):
        return User

    def authenticate_request(self):
        try:
            user = self.user_cls.query.get(_id=self.session.get('userid'))
        except KeyError:
            # Old session does not have the accessed_time in it
            del request.environ['HTTP_COOKIE']
            self.logout()
            return self.user_cls.anonymous()
        if user is None:
            return self.user_cls.anonymous()
        # immediate effect of disabling user
        if getattr(user, 'disabled', False):
            del request.environ['HTTP_COOKIE']
            self.logout()
            return self.user_cls.anonymous()
        return user

    def register_user(self, user_doc, neighborhood=None):
        """
        Register a user.

        """
        raise NotImplementedError('register_user')

    def delete_user(self, username):
        """
        Delete a user. If you're wondering whether you should use this
        method, the answer is no.

        """
        raise NotImplementedError("delete_user")

    def _login(self):
        """
        Authorize a user, usually using self.request.params['username'] and
        ['password']

        :rtype: :class:`User <vulcanforge.auth.model.User>`
        :raises: HTTPUnauthorized if user not found, or credentials are not
            valid

        """
        raise NotImplementedError('_login')

    def login(self, user=None):
        try:
            if user is None:
                user = self._login()
            if user.disabled:
                raise exc.HTTPUnauthorized('User is disabled')
            user.last_login = datetime.utcnow()
            client_ip = get_client_ip()
            if client_ip:
                ip_key = client_ip.replace(".", "_")
                if ip_key in user.login_clients:
                    last, count = user.login_clients.pop(ip_key)
                    new_value = [user.last_login, count + 1]
                    user.login_clients.update({ip_key: new_value})
                else:
                    user.login_clients.update({ip_key: [user.last_login, 1]})
            self.session['userid'] = user._id
            self.session.save()
            g.store_event('login', user=user)
            return user
        except exc.HTTPUnauthorized:
            self.logout()
            raise

    def logout(self):
        self.session['userid'] = None
        self.session.delete()

    def set_password(self, user, old_password, new_password, as_admin=False):
        """
        Set a user's password.

        :param user: a :class:`User <vulcanforge.auth.model.User>`
        :rtype: None
        :raises: HTTPUnauthorized if old_password is not valid
        """
        raise NotImplementedError('set_password')

    def _encode_password(self, password, salt=None, method=None):
        if salt is None:
            salt = os.urandom(self.saltlen)
        elif len(salt) == 4:
            method = "{SSHA}"
        if method is None:
            method = '{SSHA%d}' % len(salt)
        h = sha1(password)
        h.update(salt)
        return method + b64encode(h.digest() + salt)

    def get_salt(self, encoded):
        parsed = self.PWRE.match(encoded).groupdict()
        saltlen = int(parsed.get("saltlen") or 4)
        decoded = b64decode(encoded[len(parsed["method"]):])
        return decoded[-saltlen:]

    def assert_password_unused(self, password, user):
        for old_pw in user.old_password_hashes:
            compare_with = self._encode_password(
                password.encode('utf-8'),
                salt=self.get_salt(old_pw))
            if compare_with == old_pw:
                raise PasswordAlreadyUsedError(
                    "This password has been used before")

    def upload_sshkey(self, username, pubkey):
        """
        Upload an SSH Key.  This is saved in mongo either way, so providers do
        not necessarily need to implement this.

        :rtype: None
        :raises: AssertionError with user message, upon any error
        """
        pass


class LocalAuthenticationProvider(BaseAuthenticationProvider):
    """
    Stores user passwords on the User model, in mongo.  Uses per-user salt and
    SHA-256 encryption.

    """

    def register_user(self, user_doc, neighborhood=None):
        user_cls = neighborhood.user_cls if neighborhood else self.user_cls
        u = user_cls(**user_doc)
        if 'password' in user_doc:
            u.set_password(user_doc['password'])
        return u

    def delete_user(self, username):
        deleted = False
        u = self.user_cls.by_username(username)
        if u:
            deleted = True
            up = u.private_project()
            if up:
                up.delete()
            ProjectRole.query.remove({"user_id": u._id})
            u.delete()
        return deleted

    def _login(self):
        user = self.user_cls.by_username(request.params['username'])
        if not self.validate_password(user, request.params['password']):
            raise exc.HTTPUnauthorized()
        return user

    def validate_password(self, user, password):
        if user is None:
            return False
        if not user.password:
            return False
        check = self._encode_password(password, self.get_salt(user.password))
        if check != user.password:
            return False
        return True

    def set_password(self, user, old_password, new_password, as_admin=False):
        self.assert_password_unused(new_password, user)
        user.password = self._encode_password(new_password)
        user.store_old_password_hash(user.password)


class LdapAuthenticationProvider(BaseAuthenticationProvider):
    def register_user(self, user_doc, neighborhood=None):
        password = user_doc.pop('password').encode('utf-8')
        encoded = self._encode_password(password)
        user_cls = neighborhood.user_cls if neighborhood else self.user_cls
        result = user_cls(**user_doc)
        con = ldap.initialize(config['auth.ldap.server'])
        dn_u = 'uid=%s,%s' % (user_doc['username'], config['auth.ldap.suffix'])
        uid = str(AuthGlobals.get_next_uid())
        con.bind_s(
            config['auth.ldap.admin_dn'],
            config['auth.ldap.admin_password'])
        uname = user_doc['username'].encode('utf-8')
        display_name = user_doc['display_name'].encode('utf-8') or u"None"
        ldif_u = modlist.addModlist(dict(
            uid=uname,
            userPassword=encoded,
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
            LOG.exception('Trying to create existing user %s', uname)
            raise
        con.unbind_s()
        register_ldap.post(user_doc['username'])
        result.store_old_password_hash(encoded)
        return result

    def delete_user(self, username):
        deleted = False
        u = self.user_cls.by_username(username)
        if u:
            deleted = True
            up = u.private_project()
            ProjectRole.query.remove({"user_id": u._id})
            if up:
                up.delete()
            u.delete()
        con = ldap.initialize(config['auth.ldap.server'])
        dn_u = 'uid=%s,%s' % (username, config['auth.ldap.suffix'])
        con.bind_s(
            config['auth.ldap.admin_dn'],
            config['auth.ldap.admin_password']
        )
        try:
            con.delete_s(dn_u)
        except ldap.NO_SUCH_OBJECT:
            LOG.debug('Failed to delete %s from ldap', username)
        else:
            deleted = True
        return deleted

    def upload_sshkey(self, username, pubkey):
        upload_ssh_ldap.post(username, pubkey)

    def set_password(self, user, old_password, new_password, as_admin=False):
        try:
            uid = 'uid=%s,%s' % (user.username, config['auth.ldap.suffix'])
            if as_admin:
                dn = config['auth.ldap.admin_dn']
                pw = config['auth.ldap.admin_password']
            else:
                dn = uid
                pw = old_password.encode('utf-8')
            self.assert_password_unused(new_password, user)
            encoded = self._encode_password(new_password.encode('utf-8'))
            con = ldap.initialize(config['auth.ldap.server'])
            con.bind_s(dn, pw)
            con.modify_s(
                uid, [(ldap.MOD_REPLACE, 'userPassword', encoded)])
            con.unbind_s()
            user.store_old_password_hash(encoded)
        except ldap.INVALID_CREDENTIALS:
            raise exc.HTTPUnauthorized()

    def validate_password(self, user, password):
        if not password:
            return False
        dn = 'uid=%s,%s' % (user.username, config['auth.ldap.suffix'])
        con = ldap.initialize(config['auth.ldap.server'])
        try:
            con.bind_s(dn, password)
        except ldap.INVALID_CREDENTIALS:
            return False
        else:
            return True
        finally:
            con.unbind_s()

    def _login(self):
        user = self.user_cls.query.get(username=request.params['username'])
        if user is None:
            raise exc.HTTPUnauthorized()
        if not self.validate_password(user, request.params['password']):
            raise exc.HTTPUnauthorized()
        return user
