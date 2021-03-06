# -*- coding: utf-8 -*-

"""
app

@summary: app

@author: U{tannern<tannern@gmail.com>}
"""

import datetime

from bson import ObjectId
from ming.odm import session
from pylons import app_globals as g, tmpl_context as c
from tg import redirect
from tg.decorators import with_trailing_slash

from vulcanforge.common.app import (
    Application,
    DefaultAdminController
)
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.visualize.exchange import (
    VisualizableRenderer,
    VisualizableExchangeViewController
)
from vulcanforge.resources import Icon

from .controllers import (
    ForgeDownloadsRootController,
    ForgeDownloadsRestController)
from vulcanforge.tools.downloads import model as FDM
from vulcanforge.common.util.counts import get_info
from .version import VERSION


class ForgeDownloadsApp(Application):
    __version__ = VERSION
    has_chat = False
    status = 'production'
    tool_label = 'Downloads'
    default_mount_label = 'Downloads'
    default_mount_point = 'downloads'
    static_folder = "ForgeDownloads"
    reference_opts = dict(Application.reference_opts, can_reference=True)
    admin_description = "Store, share, and organize files with a simple, " \
                        "yet elegant, drag-and-drop interface."
    icons = {
        24: '{ep_name}/images/downloads_24.png',
        32: '{ep_name}/images/downloads_32.png',
        48: '{ep_name}/images/downloads_48.png'
    }
    artifacts = {
        "file": {
            "model": FDM.ForgeDownloadsFile,
            "renderer": VisualizableRenderer,
            "exchange_controller": VisualizableExchangeViewController
        }
    }
    admin_actions = {
        "Browse Files": {
            "url": "",
            "permission": "read"
        }
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = ForgeDownloadsRootController()
        self.api_root = ForgeDownloadsRestController()
        self.admin = ForgeDownloadsAdminController(self)

    @classmethod
    def artifact_counts_by_kind(cls, app_configs, app_visits, tool_name,
                                trefs=[]):
        db, coll = FDM.ForgeDownloadsFile.get_pymongo_db_and_collection()
        size_item = "filesize"
        return get_info(coll, app_configs, app_visits, tool_name, size_item,
                        trefs=trefs)

    def install(self, *args, **kwargs):
        super(ForgeDownloadsApp, self).install(*args, **kwargs)
        self._mk_root_dir()

    def uninstall(self, *args, **kwargs):
        self._rm_root_dir()
        super(ForgeDownloadsApp, self).uninstall(*args, **kwargs)

    def _mk_root_dir(self):
        root_dir = FDM.ForgeDownloadsDirectory(
            app_config_id=self.config._id,
            item_key='/'
        )
        session(FDM.ForgeDownloadsDirectory).flush(root_dir)

    def _rm_root_dir(self):
        root_dir = FDM.ForgeDownloadsDirectory.query.get(
            app_config_id=self.config._id,
            item_key='/'
        )
        for key in g.get_s3_keys('/', artifact=root_dir):
            g.delete_s3_key(key)
        query_params = {'app_config_id': self.config._id}
        FDM.ForgeDownloadsDirectory.query.remove(query_params)
        FDM.ForgeDownloadsFile.query.remove(query_params)

    def admin_menu(self):
        admin_url = c.project.url() + 'admin/' + \
            self.config.options.mount_point + '/'
        links = []
        permissions = self.permissions()
        if permissions and g.security.has_access(self, 'admin'):
            links.extend([
                SitemapEntry(
                    'Permissions',
                    admin_url + 'permissions',
                    className='nav_child')
            ])
        return links

    def artifact_counts(self, since=None):
        ts = (since if isinstance(since, datetime.datetime)
              else self.config._id.generation_time)
        ts = ObjectId.from_datetime(ts)
        base_query = {"app_config_id": self.config._id, "deleted": False}
        match = {"$match": base_query}
        let = {"$let": {"vars": {"app_visit": ts, "creation": '$_id'},
                        "in": {"$gt": ["$$creation", "$$app_visit"]}}}
        group = {"$group": {"_id": None, "all": {"$sum": 1},
                            "total": {"$sum": "$filesize"},
                            "new": {"$sum": {"$cond": [let, 1, 0]}}}}
        db, file_coll = FDM.ForgeDownloadsFile.get_pymongo_db_and_collection()
        agr = list(file_coll.aggregate([match, group]))
        result = agr.pop() if agr else dict(all=0, new=0, total=0)
        resp = dict(all=result['all'], new=result['new'],
                    total_size=result['total'])
        return resp

    def sidebar_menu(self):
        sidebarMenu = []

        if g.security.has_access(c.app, 'read'):
            sidebarMenu.append(
                SitemapEntry(
                    'Browse',
                    c.app.url + 'content/',
                    ui_icon=Icon('','ico-folder_fill')))
            sidebarMenu.append(
                SitemapEntry(
                    'Access Log',
                    c.app.url + 'log/access_log',
                    ui_icon=Icon('','ico-list')))


        return sidebarMenu


class ForgeDownloadsAdminController(DefaultAdminController):

    def __init__(self, app):
        self.app = app

    @with_trailing_slash
    def index(self, **kw):
        redirect('home')
