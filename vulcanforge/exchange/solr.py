import logging

from pylons import app_globals as g, tmpl_context as c

LOG = logging.getLogger(__name__)


def _get_user_read_roles():
    read_roles = []
    if c.user and not c.user.is_anonymous:
        read_roles.append('authenticated')
        reaching_role_ids = g.security.credentials.user_roles(
            user_id=c.user._id).reaching_ids
        read_roles = read_roles + map(str, reaching_role_ids)

    return read_roles


def exchange_access_filter():
    read_roles = _get_user_read_roles()
    read_roles_joined = ' OR '.join(read_roles)
    access_filter = '((share_scope_s:("neighborhood" OR "project") AND ' \
                    'read_roles:({})) OR share_scope_s:"public")'.format(
                        read_roles_joined)

    return access_filter
