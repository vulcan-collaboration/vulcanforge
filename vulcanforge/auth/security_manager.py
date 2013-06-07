"""
This module provides the security predicates used in decorating various models.
"""
import logging
from collections import defaultdict
from itertools import chain
import re

from webob import exc
from pylons import tmpl_context as c, request, app_globals as g
from tg import config
from tg.controllers.util import redirect
from tg.flash import flash
from bson import ObjectId
from ming.utils import LazyProperty
from vulcanforge.artifact.model import Shortlink
from vulcanforge.auth.model import  User
from vulcanforge.auth.schema import ACE
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.model import Project, ProjectRole

LOG = logging.getLogger(__name__)
FORBIDDEN_MSG = """
You don't have permission to do that.
You must ask a project administrator for rights to perform this task.
Please click the back button to return to the previous page.
"""


class SecurityManager(object):

    def __init__(self):
        self.RoleCache = RoleCache

    @property
    def credentials(self):
        return Credentials.get()

    def _get_project_from_obj(self, obj):
        if isinstance(obj, Neighborhood):
            project = obj.neighborhood_project
            if project is None:
                LOG.error('Neighborhood project missing for %s', obj)
                return None
        elif isinstance(obj, Project):
            project = obj.root_project
        elif hasattr(obj, 'project'):
            project = obj.project
        elif hasattr(obj, 'app_config'):
            project = obj.app_config.project
        else:
            project = c.project.root_project
        return project

    def role_has_permission(self, role_id, obj, permission, use_parent=True):
        """
        :param role_id: id of role
        :param obj: anything with an acl
        :param permission: str
        :return:
            True -- Role has permission
            False -- Role is denied permission
            None -- undetermined
        """
        result = None
        for ace in obj.acl:
            if ACE.match(ace, role_id, permission):
                result = ace.access == ACE.ALLOW
                break
        if result is None and use_parent and\
           hasattr(obj, 'parent_security_context')\
        and obj.parent_security_context():
            result = self.role_has_permission(
                role_id,
                obj.parent_security_context(),
                permission,
                use_parent=True
            )
        return result

    def roles_with_permission(self, obj, permission, project=None):
        """Returns most encompassing roles that have the given permission"""
        if project is None:
            project = self._get_project_from_obj(obj)
            if project is None:
                return []

        # try for special roles
        role_anon = ProjectRole.anonymous(project)._id
        if self.role_has_permission(role_anon, obj, permission):
            return ['anonymous']
        role_auth = ProjectRole.authenticated(project)._id
        if self.role_has_permission(role_auth, obj, permission):
            return ['authenticated']

        # named roles that have access
        pr_roles = ProjectRole.fundamental_fulfillers(
            ProjectRole.base_named(project),
            lambda r: self.role_has_permission(r._id, obj, permission)
        )

        if not pr_roles:
            # no roles specified, defaults to parent
            parent = hasattr(obj, 'parent_security_context') and\
                     obj.parent_security_context()
            if parent:
                return self.roles_with_permission(
                    parent, permission, project=project)

        roles = [str(role._id) for role in pr_roles]

        if not isinstance(obj, Neighborhood):
            roles.extend(
                self.roles_with_permission(project.neighborhood, 'admin'))
            if permission == 'read':
                roles.extend(
                    self.roles_with_permission(
                        project.neighborhood, 'overseer')
                )

        return roles

    def any_role_has_permission(self, roles, obj, permission, user=None,
                                project=None):
        """
        determines whether any of the roles have permission

        The advantage of using this rather than just looping role_has_permission is
        that it performs a breadth-wide search across the roles, rather than
        climbing the obj's security heirarchy for each role

        """
        if user is None:
            user = c.user
        if project is None:
            project = self._get_project_from_obj(obj)

        chainable_roles = []
        for rid in roles:
            result = self.role_has_permission(
                rid, obj, permission, use_parent=False)
            if result:
                return result
            elif result is None:
                # access neither allowed or denied for this role -- may chain to
                # parent context
                chainable_roles.append(rid)

        # try parent obj if possible
        if chainable_roles and hasattr(obj, 'parent_security_context') and\
           obj.parent_security_context():
            return self.any_role_has_permission(
                chainable_roles,
                obj.parent_security_context(),
                permission,
                user=user,
                project=project
            )
        else:
            return False

    def has_access(self, obj, permission, user=None, project=None, roles=None):
        """
        Return whether the given user has the permission name on the given object.

        - First, all the roles for a user in the given project context are
        computed.

        - Next, for each role, the given object's ACL is examined linearly. If an
        ACE is found which matches the permission and user, and that ACE ALLOWs
        access, then the function returns True and access is permitted. If the ACE
        DENYs access, then that role is removed from further consideration.

        - If the obj is not a Neighborhood and the given user has the 'admin'
          permission on the current neighborhood, then the function returns True
          and access is allowed.

        - If none of the ACEs on the object ALLOW access, and there are no more
        roles to be considered, then the function returns False and access is
        denied.

        - Processing continues using the remaining roles and the
          obj.parent_security_context(). If the parent_security_context is None,
          then the function returns False and access is denied.

        The effect of this processing is that if *any* role for the user is ALLOWed
        access via a linear traversal of the ACLs, then access is allowed. All of
        the users roles must either be explicitly DENYed or processing terminate
        with no matches to DENY access to the resource.

        """
        # get user
        if user is None:
            user = c.user
        if not user:
            raise RuntimeError(
                'c.user %s should always be >= M.User.anonymous()' % c.user
            )

        # get project
        if project is None:
            project = self._get_project_from_obj(obj)
            if project is None:
                return False

        # get roles
        if roles is None:
            cred = self.credentials
            roles = cred.user_roles(
                user_id=user._id, project_id=project._id).reaching_ids

        # determine permissions for this obj
        result = self.any_role_has_permission(
            roles, obj, permission, user=user, project=project
        )

        if not result and not isinstance(obj, Neighborhood):
            result = self.has_access(project.neighborhood, 'admin', user=user)
            if not result and permission == 'read':
                result = self.has_access(
                    project.neighborhood, 'overseer', user=user)

        return result

    def raise_forbidden(self, message=FORBIDDEN_MSG):
        if c.user != User.anonymous():
            request.environ['error_message'] = message
            raise exc.HTTPForbidden(detail=message)
        else:
            raise exc.HTTPUnauthorized()

    def require(self, predicate, message=None):
        """
        Example: require(has_access(c.app, 'read'))

        :param callable predicate: truth function to call
        :param str message: message to show upon failure
        :raises: HTTPForbidden or HTTPUnauthorized

        """
        if not predicate():
            self.raise_forbidden(message)

    def require_access(self, obj, permission, **kwargs):
        if not self.has_access(obj, permission, **kwargs):
            self.raise_forbidden(
                message='%s access required' % permission.capitalize())

    def require_authenticated(self):
        """:raises: HTTPUnauthorized if current user is anonymous"""
        if c.user == User.anonymous():
            raise exc.HTTPUnauthorized()

    def require_anonymous(self):
        """
        Redirect to the user's dashboard and flash a message. For controller
        methods that should only be seen by anonymous users.

        """
        if c.user != User.anonymous():
            flash("You must first log out to view the requested page.")
            return redirect('/dashboard/')

    def simple_grant(self, acl, role_id, permission):
        for ace in acl:
            if ace.role_id == role_id and ace.permission == permission:
                return
        acl.append(ACE.allow(role_id, permission))

    def simple_revoke(self, acl, role_id, permission):
        remove = []
        for i, ace in enumerate(acl):
            if ace.role_id == role_id and ace.permission == permission:
                remove.append(i)
        for i in reversed(remove):
            acl.pop(i)

    def get_user_read_roles(self, user=None):
        if user is None:
            user = c.user
        read_roles = ['anonymous']
        if user and user != user.anonymous():
            read_roles.append('authenticated')
            reaching_role_ids = self.credentials.user_roles(
                user_id=user._id).reaching_ids
            read_roles = read_roles + map(str, reaching_role_ids)
        return read_roles


class Credentials(object):
    """Role graph logic & caching"""

    def __init__(self):
        self.clear()

    @classmethod
    def get(cls):
        import vulcanforge.auth
        return vulcanforge.auth.credentials

    def clear(self):
        """clear cache"""
        self.users = {}
        self.projects = {}

    def load_user_roles(self, user_id, *project_ids):
        """Load the credentials with all user roles for a set of projects"""
        # Don't reload roles
        project_ids = [pid for pid in project_ids
                       if self.users.get((user_id, pid)) is None]
        if not project_ids:
            return
        if user_id is None:
            q = ProjectRole.query.find(
                dict(project_id={'$in': project_ids}, name='*anonymous'))
        else:
            q0 = ProjectRole.query.find({
                'project_id': {'$in': list(project_ids)},
                'name': {'$in': ['*anonymous', '*authenticated']}
            })
            q1 = ProjectRole.query.find(dict(
                project_id={'$in': list(project_ids)},
                user_id=user_id
            ))
            q = chain(q0, q1)
        roles_by_project = dict((pid, []) for pid in project_ids)
        for role in q:
            roles_by_project[role.project_id].append(role)
        for pid, roles in roles_by_project.iteritems():
            self.users[user_id, pid] = g.security.RoleCache(self, roles)

    def load_project_roles(self, *project_ids):
        """Load the credentials with all user roles for a set of projects"""
        # Don't reload roles
        project_ids = [pid for pid in project_ids
                       if self.projects.get(pid) is None]
        if not project_ids:
            return
        q = ProjectRole.query.find({'project_id': {'$in': project_ids}})
        roles_by_project = {pid: [] for pid in project_ids}
        for role in q:
            roles_by_project[role.project_id].append(role)
        for pid, roles in roles_by_project.iteritems():
            self.projects[pid] = g.security.RoleCache(self, roles)

    def project_roles(self, project_id):
        """
        :returns: a RoleCache of ProjectRoles for project_id
        """
        roles = self.projects.get(project_id)
        if roles is None:
            self.load_project_roles(project_id)
            roles = self.projects[project_id]
        return roles

    def user_roles(self, user_id, project_id=None):
        """
        :returns: a RoleCache of ProjectRoles for given user_id and project_id,
        *anonymous and *authenticated checked as appropriate

        """
        roles = self.users.get((user_id, project_id))
        if roles is None:
            if project_id is None:
                if user_id is None:
                    q = []
                else:
                    q = ProjectRole.query.find(dict(user_id=user_id))
                roles = g.security.RoleCache(self, q)
            else:
                self.load_user_roles(user_id, project_id)
                roles = self.users.get((user_id, project_id))
            self.users[user_id, project_id] = roles
        return roles

    def user_has_any_role(self, user_id, project_id, role_ids):
        user_roles = self.user_roles(user_id=user_id, project_id=project_id)
        return bool(set(role_ids) & user_roles.reaching_ids_set)

    def users_with_named_role(self, project_id, name):
        """ returns in sorted order """
        roles = self.project_roles(project_id)
        return sorted(
            g.security.RoleCache(self, roles.find(name=name)).users_that_reach,
            key=lambda u: u.username
        )

    def userids_with_named_role(self, project_id, name):
        roles = self.project_roles(project_id)
        return g.security.RoleCache(
            self, roles.find(name=name)).userids_that_reach


class RoleCache(object):

    def __init__(self, cred, q):
        self.cred = cred
        self.q = q

    def find(self, **kw):
        tests = kw.items()

        def _iter():
            for r in self:
                for k, v in tests:
                    val = getattr(r, k)
                    if callable(v):
                        if not v(val):
                            break
                    elif v != val:
                        break
                else:
                    yield r

        return RoleCache(self.cred, _iter())

    def get(self, **kw):
        for x in self.find(**kw):
            return x
        return None

    def __iter__(self):
        return self.index.itervalues()

    def __len__(self):
        return len(self.index)

    @LazyProperty
    def index(self):
        return dict((r._id, r) for r in self.q)

    @LazyProperty
    def named(self):
        return RoleCache(self.cred, (
            r for r in self
            if r.name and not r.name.startswith('*')))

    @LazyProperty
    def reverse_index(self):
        rev_index = defaultdict(list)
        for r in self:
            for rr_id in r.roles:
                rev_index[rr_id].append(r)
        return rev_index

    @LazyProperty
    def roles_that_reach(self):
        def _iter():
            visited = set()
            to_visit = list(self)
            while to_visit:
                r = to_visit.pop(0)
                if r in visited:
                    continue
                visited.add(r)
                yield r
                pr_rindex = self.cred.project_roles(r.project_id).reverse_index
                to_visit += pr_rindex[r._id]
        return RoleCache(self.cred, _iter())

    @LazyProperty
    def users_that_reach(self):
        return [r.user for r in self.roles_that_reach if r.user]

    @LazyProperty
    def userids_that_reach(self):
        return [r.user_id for r in self.roles_that_reach]

    @LazyProperty
    def reaching_roles(self):
        def _iter():
            to_visit = self.index.items()
            visited = set()
            while to_visit:
                (rid, role) = to_visit.pop()
                if rid in visited:
                    continue
                yield role
                pr_index = self.cred.project_roles(role.project_id).index
                for i in pr_index[rid].roles:
                    if i in pr_index:
                        to_visit.append((i, pr_index[i]))
        return RoleCache(self.cred, _iter())

    @LazyProperty
    def reaching_ids(self):
        return [r._id for r in self.reaching_roles]

    @LazyProperty
    def reaching_ids_set(self):
        return set(self.reaching_ids)


class SwiftAuthorizer(object):
    """
    Handles authorization for swift. Parses the requested key and determines
    whether the user has access to the resource.

    """
    def __init__(self):
        full_prefix = u'^(?P<bucket_name>[a-z0-9\-]+)/{s3_prefix}'.format(
            s3_prefix=config.get('s3.app_prefix', 'Forge'))
        self.key_parsers = {
            'deny': [],
            'allow': [
                {
                    "regex": re.compile(full_prefix + ur'/Visualizer/'),
                    "func": lambda *args: True
                }, {
                    "regex": re.compile(
                        full_prefix + ur'''
                        /Project/(?P<project>[^/]+)/(?P<filename>.*)
                        ''', re.VERBOSE),
                    "func": self.project_access
                }, {
                    "regex": re.compile(
                        full_prefix + ur'''
                        /Neighborhood/(?P<neighborhood>[^/]+)/(?P<filename>.*)
                        ''', re.VERBOSE),
                    "func": self.neighborhood_access
                }, {
                    "regex": re.compile(
                        full_prefix + ur'''
                        /User/(?P<user_id>[^/]+)/(?P<filename>.*)
                        ''', re.VERBOSE),
                    "func": self.user_access,
                    "allow_methods": "GET, PUT, POST"
                }, {
                    "regex": re.compile(
                        full_prefix + ur'''
                        /(?P<project>[^/]+)/(?P<app>[^/]+)
                        /(?P<shortlink_path>.*)  # shorthand_id#key
                        ''', re.VERBOSE),
                    "func": self.artifact_access
                }
            ]
        }
        super(SwiftAuthorizer, self).__init__()

    def neighborhood_access(self, match, user, keyname, method):
        prefix = match.group('neighborhood')
        LOG.info('checking permission on neighborh2ood %s', prefix)
        neighborhood = Neighborhood.by_prefix(prefix)
        if neighborhood:
            return g.security.has_access(neighborhood, 'read', user=user)
        return False

    def project_access(self, match, user, keyname, method):
        shortname = match.group('project')
        LOG.info('checking permission on project %s', shortname)
        project = Project.query.get(shortname=shortname)
        if project:
            return g.security.has_access(project, 'read', user=user)
        return False

    def user_access(self, match, user, keyname, method):
        LOG.info('checking permission on user %s', match.group('user_id'))
        user_id = ObjectId(match.group('user_id'))
        if user._id == user_id:
            return True

        user_nbhd = Neighborhood.get_user_neighborhood()
        swift_admin_ids = g.security.credentials.userids_with_named_role(
            user_nbhd.neighborhood_project._id, 'SwiftAdmin')
        result = user._id in swift_admin_ids
        LOG.info('user is a swift admin: %s', result)
        return result

    def artifact_access(self, match, user, keyname, method):
        # find shortlink for artifact
        has_permission = False
        shorthand_id, key = match.group('shortlink_path').rsplit('#', 1)
        link = u'[{}:{}:{}]'.format(
            match.group('project'), match.group('app'), shorthand_id)
        LOG.info('attempting to match shortlink %s', link)
        shortlink = Shortlink.lookup(link)

        if shortlink:
            # load artifact and check acl
            artifact = shortlink.ref.artifact
            if method.upper() == "GET":
                permission = 'read'
            else:
                permission = artifact.app_config.reference_opts['create_perm']
            LOG.info('checking permission on artifact %s', artifact.index_id())
            has_permission = g.security.has_access(
                artifact, permission, user=user)
        else:
            # check acl of app instead
            project = Project.query.get(
                shortname=match.group('project'))
            if project:
                ac = project.app_config(match.group('app'))
                if ac:
                    LOG.info('checking permission on appconfig %s', str(ac))
                    if method.upper() == "GET":
                        permission = 'read'
                    else:
                        permission = ac.reference_opts['create_perm']
                    has_permission = g.security.has_access(
                        ac, permission, user=user)

        return has_permission

    def has_access(self, keyname, method="GET", user=None):
        # deny regexes
        for regex in self.key_parsers['deny']:
            if regex.match(keyname):
                LOG.info('denying %s automagically', keyname)
                return False

        if user is None:
            user = c.user

        # allow regexes (only GET for now)
        for parser in self.key_parsers['allow']:
            m = parser["regex"].match(keyname)
            if m:
                if 'bucket_name' in m.groups() and\
                   m.group('bucket_name') != g.s3_bucket.name:
                    LOG.warn('Wrong s3 bucket name in %s', keyname)
                    return False
                if method.upper() not in parser.get("allow_methods", ["GET"]):
                    LOG.info('invalid method %s', method)
                    return False
                return parser["func"](m, user, keyname, method)

        return False
