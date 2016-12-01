import pymongo
import re

from bson import ObjectId
from markupsafe import Markup
from formencode import validators
from pylons import tmpl_context as c, app_globals as g
from tg import redirect, flash, request
from tg.decorators import expose, without_trailing_slash, with_trailing_slash, validate

from vulcanforge.common.controllers.base import BaseController
from vulcanforge.common.controllers.decorators import require_post, vardec
from vulcanforge.common.tasks.index import reindex_tool
from vulcanforge.common.util.datatable import DATATABLE_SCHEMA
from vulcanforge.common.util.http import raise_400
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.auth.schema import ACE, ACL
from vulcanforge.tools.admin.widgets import ToolPermissionCard

from vulcanforge.artifact.model import LogEntry

TEMPLATE_DIR = 'jinja:vulcanforge:common/templates/'
URL_REGEX = re.compile("http\w?://[\w\.\-]+:?\d*(?:/rest)?")

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
        permissions = dict((p, []) for p in self.app.permissions())
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
            permission_description=self.app.permissions(),
            permissions=permissions)

    @expose(TEMPLATE_DIR + 'app_admin_options.html')
    def options(self):
        return dict(
            app=self.app,
            allow_config=g.security.has_access(self.app, 'admin'))

    @expose()
    @require_post()
    def configure(self, **kw):
        with g.context_manager.push(app_config_id=self.app.config._id):
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


class DefaultLogController(BaseController):

    mount_point = "log"

    _log_table_columns = [
        {
            "sTitle": "Access time",
            "mongo_field": "timestamp"
        },
        {
            "sTitle": "User",
            "mongo_field": "display_name"
        },
        {
            "sTitle": "URL",
            "mongo_field": "url"
        },
        {
            "sTitle": "Access type",
            "mongo_field": "access_type"
        },
        {
            "sTitle": "Access denied",
            "mongo_field": "access_denied"
        }
    ]

    def __init__(self, url_prefix_to_ignore=""):
        self.url_prefix_to_ignore = url_prefix_to_ignore

    def _short_url(self, url_str):
        short_str = re.sub(URL_REGEX, "", url_str)
        if hasattr(c, 'app'):
            if short_str.startswith(c.app.url):
                short_str = short_str.replace(c.app.url, "", 1)
        if self.url_prefix_to_ignore and short_str.startswith(short_str):
            return short_str.replace(self.url_prefix_to_ignore, "", 1)

        return short_str

    def _check_security(self):
        g.security.require_access(c.app, 'read')

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'access_log.html')
    def access_log(self):
        g.security.require_access(c.project, 'read')

        #AccessLogChecked.upsert(c.user._id, c.app.config._id, c.project._id)

        data_url = "{}{}/log_data".format(c.app.config.url(), self.mount_point)
        return dict(
            data_url=data_url,
            title="{} - Access Log".format(c.app.config.tool_name),
            header="{} - Access Log".format(c.app.config.tool_name),
            show_access_type=True
        )

    @expose('json', render_params={"sanitize": False})
    @validate(DATATABLE_SCHEMA, error_handler=raise_400)
    def log_data(self, iDisplayStart=0, iDisplayLength=None, sSearch=None,
                 iSortingCols=0, sEcho=0, **kwargs):
        g.security.require_access(c.project, 'read')

        # assemble the query
        db, coll = pymongo_db_collection(LogEntry)

        query_dict = {'project_id': c.project._id, "app_config_id": c.app.config._id}
        total = coll.find(query_dict).count()
        pipeline = [
            {'$match': query_dict}
        ]
        if iSortingCols > 0:
            sort_column = int(kwargs['iSortCol_0'])
            sort_dir_str = kwargs['sSortDir_0']
            field_name = self._log_table_columns[sort_column]['mongo_field']
            sort_dir = pymongo.ASCENDING
            if sort_dir_str.lower() == 'desc':
                sort_dir = pymongo.DESCENDING
            pipeline.append({'$sort': {field_name: sort_dir}})
        pipeline.append({'$skip' : iDisplayStart})
        pipeline.append({'$limit' : iDisplayLength})

        aggregate = coll.aggregate(pipeline)

        # format the data
        data = []
        for log_entry in aggregate['result']:
            url = log_entry.get('url','')
            short_url = self._short_url(url)
            row = [
                log_entry['timestamp'].strftime('%m/%d/%Y %H:%M:%S UTC'),
                Markup('<a href="/u/{}">{}</a>'.format(
                    log_entry['username'], log_entry['display_name'])),
                Markup('<a href="{}">{}</a>'.format(
                    url, short_url)),
                log_entry.get('access_type', ''),
                log_entry.get('access_denied', False)
            ]

            data.append(row)

        response = {
            'iTotalRecords': total,
            'iTotalDisplayRecords': total,
            'sEcho': sEcho,
            'aaData': data
        }
        return response
