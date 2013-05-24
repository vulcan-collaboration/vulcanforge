# -*- coding: utf-8 -*-

"""
app

@summary: app

@author: U{tannern<tannern@gmail.com>}
"""

from ming.odm import session
from pylons import app_globals as g, tmpl_context as c
from tg import expose, redirect, flash
from tg.decorators import with_trailing_slash, without_trailing_slash

from vulcanforge.common.controllers.decorators import require_post
from vulcanforge.common.app import (
    Application,
    DefaultAdminController
)
from vulcanforge.common.types import SitemapEntry
from .controllers import (
    ForgeDownloadsRootController,
    ForgeDownloadsRestController)
from vulcanforge.tools.downloads import model as FDM
from .version import VERSION


class ForgeDownloadsApp(Application):
    __version__ = VERSION
    permissions = ['read', 'write', 'configure']
    status = 'alpha'
    tool_label = 'Downloads'
    default_mount_label = 'Downloads'
    default_mount_point = 'downloads'
    static_folder = "ForgeDownloads"
    reference_opts = dict(Application.reference_opts, can_reference=True)
    admin_description = "Offer things for download with the Downloads tool!"
    installable = False
    icons = {
        24: 'images/downloads_24.png',
        32: 'images/downloads_32.png',
        48: 'images/downloads_48.png'
    }
    default_acl = {
        'Admin': permissions,
        'Developer': ['read', 'write'],
        'Member': ['read'],
        '*authenticated': ['read']
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = ForgeDownloadsRootController()
        self.api_root = ForgeDownloadsRestController()
        self.admin = ForgeDownloadsAdminController(self)

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
        if self.permissions and g.security.has_access(self, 'configure'):

            links.extend([
                SitemapEntry(
                    'Options', admin_url + 'options', className='admin_modal'),
                SitemapEntry(
                    'Permissions',
                    admin_url + 'permissions',
                    className='nav_child')
            ])
        return links


class ForgeDownloadsAdminController(DefaultAdminController):

    def __init__(self, app):
        self.app = app

    def _check_security(self):
        g.security.require_access(self.app, 'configure')

    @with_trailing_slash
    def index(self, **kw):
        redirect('home')
