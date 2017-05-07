import logging
from datetime import datetime

from bson import ObjectId
from markupsafe import Markup
from webob import exc
from pylons import app_globals as g, tmpl_context as c
from tg import expose, validate

from vulcanforge.common.controllers.base import BaseController
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.common.util.datatable import DATATABLE_SCHEMA
from vulcanforge.common.util.http import raise_400
from vulcanforge.project.model import Project, AppConfig
from vulcanforge.resources import Icon

from vulcanforge.exchange.model import ExchangeNode, ExchangeVisit
from vulcanforge.exchange.solr import exchange_access_filter

LOG = logging.getLogger(__name__)
SOLR_DATE_FMT = '%Y-%m-%dT%H:%M:%S.%fZ'
SOLR_DATE_FMT_2 = '%Y-%m-%dT%H:%M:%SZ'


class ExchangeArtifactController(BaseController):
    """
    Functionality related to a single artifact type within the Exchange.
    Includes viewing, publishing, editing, etc.

    """
    def __init__(self, view_cls, publish_cls, import_cls=None):
        self.publish = publish_cls()
        self.view = view_cls()
        if import_cls:
            self.importer = import_cls()


class ExchangeRootController(BaseController):
    """Provides generic search and sortable table interface for browsing the
    exchange

    """
    def __init__(self, exchange):
        super(ExchangeRootController, self).__init__()
        self._artifact_mounts = {}
        self.exchange = exchange

    def sidebar_menu(self):
        sidebar_menu = []
        sidebar_menu.append(
            SitemapEntry('Shared by')
        )
        sidebar_menu.append(
            SitemapEntry(
                'Other Projects',
                self.exchange.url(),
                ui_icon=Icon('','ico-list')))
        sidebar_menu.append(
            SitemapEntry(
                'My Projects',
                self.exchange.url() + "my_items",
                ui_icon=Icon('','ico-list')))

        return sidebar_menu

    def mount_artifact_controller(self, name, artifact_config, view_cls,
                                  publish_cls=None, import_cls=None):

        controller = ExchangeArtifactController(
            view_cls, publish_cls, import_cls)
        self._artifact_mounts[name] = {
            "controller": controller,
            "config": artifact_config
        }

    @expose()
    def _lookup(self, name, *remainder):
        if name in self._artifact_mounts:
            c.artifact_config = self._artifact_mounts[name]["config"]
            controller = self._artifact_mounts[name]["controller"]
            return controller, remainder
        raise exc.HTTPNotFound()


class DataTableRootController(ExchangeRootController):
    """Uses jQuery dataTables to display nodes in a sortable, searchable table

    """

    def _table_columns(self):
        return [
            {
                "sTitle": "Name",
                "solr_field": "title_s"
            },
            {
                "sTitle": "Publish Date",
                "solr_field": "mod_date_dt"
            },
            {
                "sTitle": "Revision",
                "solr_field": "revision_s"
            },
            {
                "sTitle": "Project",
                "solr_field": "project_name_s"
            },
            {
                "sTitle": "Tool",
                "solr_field": "tool_name_s"
            },
            {
                "sTitle": "Scope",
                "solr_field": "share_scope_s"
            },
            {
                "sTitle": "Contact",
                "solr_field": "author_display_name_s"
            }
        ]

    def _table_columns_with_actions(self):
        table_columns = self._table_columns()
        table_columns.append({
            "sTitle": "Actions",
            "bSortable": False
        })

        return table_columns

    def _get_data_from_node(self, node_doc,
                            has_project_read,
                            has_tool_read,
                            has_tool_publish,
                            populate_actions):

        if has_project_read:
            project_data = Markup('<a href="{}">{}</a>'.format(
                node_doc["project_url_s"], node_doc["project_name_s"]))
        else:
            project_data = '--'
        if has_tool_read:
            tool_data = Markup('<a href="{}">{}</a>'.format(
                node_doc["tool_url_s"], node_doc["tool_label_s"]))
        else:
            tool_data = '--'

        try:
            dt = datetime.strptime(node_doc["mod_date_dt"], SOLR_DATE_FMT)
        except:
            try:
                dt = datetime.strptime(node_doc["mod_date_dt"], SOLR_DATE_FMT_2)
            except:
                pass

        row = [
            Markup('<a href="{}">{}</a>'.format(
                node_doc["url_s"], node_doc["title_s"])),
            dt.strftime('%Y-%m-%d %H:%M'),
            node_doc["revision_s"],
            project_data,
            tool_data,
            node_doc["share_scope_s"],
            Markup('<a href="{}">{}</a>'.format(
                "/u/" + node_doc.get("author_username_s", ""), node_doc.get("author_display_name_s", "")))
        ]

        if populate_actions:
            node_id = node_doc.get("id").split("ExchangeNode#")[1]
            node = ExchangeNode.query.get(_id=ObjectId(node_id))
            buttons = []
            if node is not None:
                if has_tool_publish:
                    edit_button = g.icon_button_widget.display(
                        label="Edit",
                        icon='ico-edit',
                        href=node.edit_url())
                    buttons.append(edit_button)
                    unpublish_button = g.icon_button_widget.display(
                        label="Unpublish",
                        icon='ico-undo',
                        href='',
                        action="$vf.unpublishNode(\'"+ node.delete_url() +"\'); return false;")
                    buttons.append(unpublish_button)

                history_button = g.icon_button_widget.display(
                    label="History",
                    icon='ico-history',
                    href=node.history_url())
                buttons.append(history_button)

                if g.security.has_access(node.artifact, 'read'):
                    artifact_button = g.icon_button_widget.display(
                        label="View Original",
                        icon='ico-eye',
                        href=node.cur_artifact.url() + '?node_id={}'.format(node._id))
                    buttons.append(artifact_button)

            row.append(' '.join(buttons))

        return row

    @expose('exchange/browse.html')
    def index(self, **kwargs):
        # Browsing objects that have been shared with me
        return {
            "data_url": '{}data.json'.format(c.exchange.url()),
            "xcng_name": c.exchange.config["name"],
            "table_columns": [{"sTitle": col["sTitle"], "bSortable": col.get("bSortable", True)}
                              for col in self._table_columns()],
            "sorting": [[1, "desc"]],
        }

    @expose('exchange/browse.html')
    def my_items(self, **kwargs):
        # Browsing objects that have been shared with me
        return {
            "data_url": '{}my_data.json'.format(c.exchange.url()),
            "xcng_name": c.exchange.config["name"],
            "table_columns": [{"sTitle": col["sTitle"], "bSortable": col.get("bSortable", True)}
                              for col in self._table_columns_with_actions()],
            "sorting": [[1, "desc"]]
        }

    @expose('json', render_params={"sanitize": False})
    @validate(DATATABLE_SCHEMA, error_handler=raise_400)
    def my_data(self, **kwargs):
        kwargs['my_items'] = True
        return self.data(**kwargs)

    @expose('json', render_params={"sanitize": False})
    @validate(DATATABLE_SCHEMA, error_handler=raise_400)
    def data(self, iDisplayStart=0, iDisplayLength=20, sSearch=None,
             iSortingCols=0, sEcho=0, **kwargs):

        # assemble the query
        query_l = []
        if sSearch:
            query_l.append(sSearch)

        project_id_s = ' OR '.join(map(str, [p._id for p in c.user.my_projects()]))
        populate_actions = False
        if kwargs.has_key("my_items"):
            # only retrieve objects that are shared by the user's project's
            # in other words filter by project ids
            project_filter = "project_id_s:({})".format(project_id_s)
            populate_actions = True
        else:
            # The inverse of the above
            project_filter = "-project_id_s:({})".format(project_id_s)

        query_l.extend([
            'NOT deleted_b:true', # Make sure deleted items are not listed
            'type_s:"{}"'.format(c.exchange.config["node"].type_s),
            'exchange_uri_s:"{}"'.format(c.exchange.config["uri"]),
            exchange_access_filter(),
            project_filter
        ])
        query = ' AND '.join(query_l)
        columns = self._table_columns()
        sort_l = [
            columns[int(kwargs['iSortCol_{}'.format(i)])]['solr_field'] +
            ' ' + kwargs['sSortDir_{}'.format(i)]
            for i in range(iSortingCols)]

        # run the search
        result = g.search(q=query, start=iDisplayStart, rows=iDisplayLength, sort=','.join(sort_l))

        # format the data
        data = []
        project_cache = {}
        tool_cache = {}
        for node_doc in result.docs:
            # determine project read access
            shortname = node_doc["project_shortname_s"]
            if shortname in project_cache:
                project = project_cache[shortname]
            else:
                project = Project.by_shortname(shortname)
                project_cache[shortname] = project

            if project is None:
                continue

            has_project_read = g.security.has_access(project, 'read')

            # determine tool read access
            if has_project_read:
                ac_id = node_doc["app_config_id_s"]
                if ac_id in tool_cache:
                    ac = tool_cache[ac_id]
                else:
                    ac = AppConfig.query.get(_id=ObjectId(ac_id))
                    tool_cache[ac_id] = ac
                has_tool_read = g.security.has_access(ac, 'read')
                has_tool_publish = g.security.has_access(ac, 'publish')
            else:
                has_tool_read = False
                has_tool_publish = False

            # format data
            row = self._get_data_from_node(
                node_doc, has_project_read, has_tool_read, has_tool_publish, populate_actions)
            data.append(row)

        response = {
            'iTotalRecords': result.hits,
            'iTotalDisplayRecords': len(result.docs),
            'sEcho': sEcho,
            'aaData': data
        }
        return response


class TaxonomicRootController(ExchangeRootController):
    """Browse the exchange based on taxonomy"""
    pass


class GlobalExchangeController(BaseController):

    @expose()
    def _lookup(self, name, *remainder):
        xcng = g.exchange_manager.get_exchange_by_uri(name)
        if xcng:
            c.exchange = xcng
            controller = xcng.config['root_controller']
            if hasattr(controller, 'sidebar_menu'):
                c.custom_sidebar_menu = controller.sidebar_menu()

            if not c.user.is_anonymous:
                ExchangeVisit.upsert(c.user._id, c.exchange.config["uri"])

            return controller, remainder
        raise exc.HTTPNotFound
