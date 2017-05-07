"""
@group ISIS - Vanderbilt University
@author Gabor Pap

"""

import bson
import logging

from pylons import tmpl_context as c, request, app_globals as g
from ming import schema
from ming.base import Object
from ming.odm import (
    mapper,
    FieldProperty,
    ForeignIdProperty,
    RelationProperty
)

from vulcanforge.auth.schema import ACE, ACL, EVERYONE
from vulcanforge.common.exceptions import ForgeError
from vulcanforge.project.model import Project

LOG = logging.getLogger(__name__)


class ExchangeACE(ACE):
    """
    Access Control Entry that allows one to defer access control logic to a
    project, or check for membership in a project.

     e.g. Users have access to object X if they have access to Project Y

     NOTE: this relies on the nonexistence of explicit DENYs on the
     Project ACL. If there are explicit deny's it will cause errors.

    """
    def _make_fields(self, permissions):
        fields = super(ExchangeACE, self)._make_fields(permissions)
        fields.update({
            'project_id': schema.ObjectId(if_missing=None),
            'project_permission': schema.String(),
            'member_project_id': schema.ObjectId(if_missing=None)
        })
        return fields

    @classmethod
    def match(cls, ace, role_id, permission):
        matches = ACE.match(ace, role_id, permission)
        if matches:
            if getattr(ace, 'project_id', None):
                project = Project.query_get(_id=ace.project_id)
                if project:
                    for p_ace in project.acl:
                        if ACE.match(p_ace, role_id, ace.project_permission):
                            if p_ace.access == ACE.DENY:
                                raise ForgeError(
                                    'Explicit DENY on Project %s caused '
                                    'Access Control Error in Exchange',
                                    project.shortname)
                            matches = True
                            break
                    else:
                        matches = False
            elif getattr(ace, 'member_project_id', None):
                role_ids = [
                    role._id for role in
                    g.security.credentials.project_roles(
                        ace.member_project_id).named]
                matches = bson.ObjectId(role_id) in role_ids
                if not matches:
                    user = c.user
                    if user:
                        project = Project.by_id(ace.member_project_id)
                        if project:
                            pstatus = project.get_membership_status(user)
                            matches = pstatus == 'member'
                        else:
                            matches = False
                    else:
                        matches = False
        return matches

    @classmethod
    def allow_project(cls, project_id, permission, project_permission='read'):
        return Object(
            access=cls.ALLOW,
            project_id=project_id,
            permission=permission,
            project_permission=project_permission,
            role_id=EVERYONE)

    @classmethod
    def allow_project_members(cls, project_id, permission):
        return Object(
            access=cls.ALLOW,
            permission=permission,
            member_project_id=project_id,
            role_id=EVERYONE
        )


class ExchangeACL(ACL):
    entry_cls = ExchangeACE

