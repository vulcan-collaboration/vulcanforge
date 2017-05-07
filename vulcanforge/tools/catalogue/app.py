# -*- coding: utf-8 -*-

"""
app

@summary: app

@author: U{papszi<gabor.pap@vanderbilt.edu>}
"""

from pylons import app_globals as g, tmpl_context as c

from vulcanforge.common.app import (
    Application,
)
from vulcanforge.common.tool import SitemapEntry


class CatalogueApp(Application):
    has_chat = False
    status = 'production'
    tool_label = 'Catalogue'
    default_mount_label = 'Catalogue'
    default_mount_point = 'catalogue'
    reference_opts = dict(Application.reference_opts, can_reference=True)
    admin_description = "Abstract App to serve as base for versioned sharable" \
                        "objects with files"
    icons = {
        24: '{ep_name}/images/downloads_24.png',
        32: '{ep_name}/images/downloads_32.png',
        48: '{ep_name}/images/downloads_48.png'
    }
    # artifacts = {
    #     "file": {
    #         "model": FDM.ForgeDownloadsFile,
    #         "renderer": VisualizableRenderer,
    #         "exchange_controller": VisualizableExchangeViewController
    #     }
    # }
    # admin_actions = {
    #     "Browse Files": {
    #         "url": "",
    #         "permission": "read"
    #     }
    # }

    def __init__(self, project, config):
        Application.__init__(self, project, config)

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

    def sidebar_menu(self):
        sidebarMenu = []

        return sidebarMenu
