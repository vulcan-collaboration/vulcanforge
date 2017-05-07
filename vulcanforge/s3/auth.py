import re
import urllib
import logging

from bson import ObjectId
from pylons import app_globals as g, tmpl_context as c
from tg import config

from vulcanforge.artifact.model import Shortlink
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.s3.model import FileReference

LOG = logging.getLogger(__name__)


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
        project_cls = user.registration_neighborhood().project_cls
        project = project_cls.by_shortname(shortname)
        if project:
            return g.security.has_access(project, 'read', user=user)
        return False

    def user_access(self, match, user, keyname, method):
        LOG.info('checking permission on user %s', match.group('user_id'))
        user_id = ObjectId(match.group('user_id'))
        if user._id == user_id:
            return True

    def _get_artifact_from_match(self, match):
        shorthand_id, key = match.group('shortlink_path').rsplit('#', 1)
        link = u'[{}:{}:{}]'.format(
            match.group('project'), match.group('app'), shorthand_id)
        LOG.info('attempting to match shortlink %s', link)
        shortlink = Shortlink.lookup(link)

        if shortlink:
            # load artifact and check acl
            return g.artifact.get_artifact_by_index_id(shortlink.ref_id)

    def artifact_access(self, match, user, keyname, method):
        # find shortlink for artifact
        has_permission = False
        bucket_name = match.group('bucket_name')
        keyname_witouth_bucket = keyname.split(bucket_name, 1)[-1].lstrip('/')

        # FIX:
        # Somewhat of a hack but needed because of special characters in URLs
        if '#' in keyname_witouth_bucket:
            parts = keyname_witouth_bucket.split('#')
            part_2_rev = urllib.quote(parts[1])
            rev_keyname = urllib.quote("#".join([parts[0], part_2_rev]))
        else:
            rev_keyname = urllib.quote(keyname_witouth_bucket)

        forge_file = FileReference.get_file_from_key_name(
            rev_keyname)
        if forge_file:
            artifact = forge_file.artifact
        else:
            artifact = self._get_artifact_from_match(match)

        if artifact:
            if method.upper() == "GET":
                permission = 'read'
            else:
                permission = artifact.app_config.reference_opts['create_perm']
            has_permission = g.security.has_access(
                artifact, permission, user=user)
            LOG.info('has_permission:%s for artifact %s', str(has_permission),
                     artifact.index_id())

        # Fallback: if we cannot find the artifact but can identify the app
        with g.context_manager.push(match.group('project'), match.group('app')):
            if c.app:
                if method.upper() == "GET":
                    permission = 'read'
                else:
                    permission = c.app.config.reference_opts['create_perm']
                has_permission = g.security.has_access(
                    c.app.config, permission, user=user)

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
            match = parser["regex"].match(keyname)
            if not match:
                continue
            if 'bucket_name' in match.groups() and \
                    match.group('bucket_name') != g.s3_bucket.name:
                LOG.warn('Wrong s3 bucket name in %s', keyname)
                return False
            if method.upper() not in parser.get("allow_methods", ["GET"]):
                LOG.info('invalid method %s', method)
                return False
            return parser["func"](match, user, keyname, method)

        return False

    def require_access(self, keyname, method="GET", user=None):
        if not self.has_access(keyname, method=method, user=user):
            g.security.raise_forbidden()
