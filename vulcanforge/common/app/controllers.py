
from bson import ObjectId
from formencode import validators
from pylons import tmpl_context as c, app_globals as g
from tg import redirect, flash, request
from tg.decorators import expose, without_trailing_slash, validate

from vulcanforge.common.controllers.base import BaseController
from vulcanforge.common.controllers.decorators import require_post, vardec
from vulcanforge.common.tasks.index import reindex_tool
from vulcanforge.auth.schema import ACE, ACL
from vulcanforge.tools.admin.widgets import ToolPermissionCard

TEMPLATE_DIR = 'jinja:vulcanforge:common/templates/'


class DefaultAdminController(BaseController):

    reindex_on_aclmod = True

    def __init__(self, app):
        self.app = app

    def _check_security(self):
        g.security.require_access(self.app, 'admin')

    @expose()
    def index(self, **kw):
        return redirect('permissions')

    @expose(TEMPLATE_DIR + 'app_admin_permissions.html')
    @without_trailing_slash
    def permissions(self):
        c.card = ToolPermissionCard()
        permissions = dict((p, []) for p in self.app.permissions)
        for ace in self.app.config.acl:
            if ace.access == ACE.ALLOW:
                try:
                    permissions[ace.permission].append(ace.role_id)
                except KeyError:
                    # old, unknown permission
                    pass
        return dict(
            app=self.app,
            allow_config=g.security.has_access(c.project, 'admin'),
            permission_description=self.app.permissions,
            permissions=permissions)

    @expose(TEMPLATE_DIR + 'app_admin_options.html')
    def options(self):
        return dict(
            app=self.app,
            allow_config=g.security.has_access(self.app, 'admin'))

    @expose()
    @require_post()
    def configure(self, **kw):
        with g.context_manager.push(c, app=self.app):
            g.security.require_access(self.app, 'admin')
            is_admin = self.app.config.tool_name == 'admin'
            if kw.pop('delete', False):
                if is_admin:
                    flash('Cannot delete the admin tool, sorry....')
                    redirect('.')
                c.project.uninstall_app(self.app.config.options.mount_point)
                redirect('..')
            for k, v in kw.iteritems():
                self.app.config.options[k] = v
            if is_admin:
                # possibly moving admin mount point
                redirect('/'
                         + c.project._id
                         + self.app.config.options.mount_point
                         + '/'
                         + self.app.config.options.mount_point
                         + '/')
            else:
                redirect('../' + self.app.config.options.mount_point + '/')

    @without_trailing_slash
    @expose()
    @vardec
    @require_post()
    def update(self, card=None, **kw):
        old_acl = self.app.config.acl
        self.app.config.acl = []
        for args in card:
            perm = args['id']
            new_group_ids = args.get('new', [])
            group_ids = args.get('value', [])
            if isinstance(new_group_ids, basestring):
                new_group_ids = [new_group_ids]
            if isinstance(group_ids, basestring):
                group_ids = [group_ids]
            role_ids = map(ObjectId, group_ids + new_group_ids)
            for r in role_ids:
                ACL.upsert(self.app.config.acl, ACE.allow(r, perm))

        if self.reindex_on_aclmod and\
           self._read_aces_changed(old_acl, self.app.config.acl):
            reindex_tool.post(self.app.config._id)
        redirect(request.referer or 'index')

    def _read_aces_changed(self, old_acl, new_acl):
        old_read_aces = [item for item in old_acl if item.permission == 'read']
        new_read_aces = [item for item in new_acl if item.permission == 'read']
        diff_list = [item for item in old_read_aces
                     if not item in new_read_aces]
        diff_list2 = [item for item in new_read_aces
                      if not item in old_read_aces]
        return diff_list or diff_list2


class DefaultSearchController(BaseController):

    def _check_security(self):
        g.security.require_access(c.app, 'read')

    def search(self, tool_q=None, history=False, limit=25, page=0, **kw):
        search_uri = c.app.url + 'search/search_results'
        return dict(
            q=tool_q,
            search_uri=search_uri,
            limit=limit,
            page=page
        )

    def _get_complete_query(self, tool_q):
        return tool_q + ' AND %s' % (
            ' AND '.join((
                'project_id_s:%s' % c.app.config.project_id,
                'mount_point_s:%s' % c.app.config.options.mount_point
                ))
            )

    @expose('json')
    @validate(dict(tool_q=validators.UnicodeString(if_empty=''),
        history=validators.StringBool(if_empty=False),
        limit=validators.Int(if_empty=25),
        startPos=validators.Int(if_empty=0),
        page=validators.Int(if_empty=0)))
    def search_results(self, tool_q='', history=False, limit=25, startPos=0,
                       page=None, **kw):
        # local tool search
        results_list = []
        complete_q = self._get_complete_query(tool_q)
        params = dict(
            q=complete_q,
            rows=limit,
            start=startPos,
            fl="*,score",
            fq='is_history_b:%s' % history
        )
        results = g.search(**params)
        if results:
            count = results.hits
            max_params = params.copy()
            max_params.update(dict(
                rows=1,
                start=0,
                fl="score"
            ))
            max_score = g.search(**max_params).docs[0]['score']
            for doc in results.docs:
                doc['rel_score'] = 10. * doc['score'] / max_score
                results_list.append(doc)
        else:
            count = 0
        return dict(q=tool_q, history=history, results=results_list,
            count=count, limit=limit, page=page)
