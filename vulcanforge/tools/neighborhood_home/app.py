# -*- coding: utf-8 -*-

"""
app

@summary: app

@author: U{tannern<tannern@gmail.com>}
"""
import logging

from pylons import app_globals as g
from vulcanforge.common.app import Application
from .controllers.root import (
    NeighborhoodHomeRootController,
    NeighborhoodHomeRestController
)
from vulcanforge.common.types import SitemapEntry
from vulcanforge.resources import Icon

LOG = logging.getLogger(__name__)
__all__ = ['NeighborhoodHomeApp']


class NeighborhoodHomeApp(Application):
    """
    An app that provides the landing and support pages for a neighborhood.
    """

    tool_label = "Neighborhood"
    static_folder = "Neighborhood"
    default_mount_label = "Home"
    default_mount_point = "home"
    cons = {
        24: '{ep_name}/images/home_24.png',
        32: '{ep_name}/images/home_32.png',
        48: '{ep_name}/images/home_48.png'
    }
    permissions = ['read']
    default_acl = {
        '*anonymous': ['read']
    }
    is_customizable = False

    root_controller_class = NeighborhoodHomeRootController

    def __init__(self, project, app_config_object):
        super(NeighborhoodHomeApp, self).__init__(project, app_config_object)
        self.root = self.root_controller_class(project, app_config_object)
        self.api_root = NeighborhoodHomeRestController()
        self.neighborhood = self.project.neighborhood

    def is_visible_to(self, user):
        """Whether the user can view the app."""
        return True

    def main_menu(self):
        """Apps should provide their entries to be added to the main nav
        :return: a list of :class:`SitemapEntries <vulcanforge.common.types.SitemapEntry>`
        """
        return self.sitemap

    @property
    def sitemap(self):
        return [SitemapEntry(self.config.options.mount_label, '.')]

    @property
    def extra_sidebars(self):
        return [SitemapEntry(sidebar.name, sidebar.url)
                for sidebar in self.neighborhood.extra_sidebars]

    def sidebar_menu(self):
        entries = [
            SitemapEntry(self.neighborhood.name, "{}".format(self.url)),
            SitemapEntry("Browse Projects", "{}browse".format(self.url))
        ]
        entries.extend(self.extra_sidebars)
        if self.neighborhood.user_can_register():
            entries.append(
                SitemapEntry("Add a Project", "{}add_project".format(
                    self.neighborhood.url()))
            )
        if self.neighborhood.enable_marketplace:
            entries.extend([
                SitemapEntry("Marketplace"),
                SitemapEntry("Designers",
                             "{}market/browse_users".format(self.url)),
                SitemapEntry("Projects",
                             "{}market/browse_projects".format(self.url))
            ])
        if g.security.has_access(self.neighborhood, 'overseer'):
            entries.extend(self.get_overseer_menu_items())
        return entries

    def get_overseer_menu_items(self):
        return [
            SitemapEntry("Monitor"),
            SitemapEntry(
                "Collaboration",
                self.url + "monitor/artifacts",
                ui_icon=Icon('', 'ico-bars')
            ),
            SitemapEntry(
                "Logins",
                self.url + "monitor/logins",
                ui_icon=Icon('', 'ico-bars')
            )
        ]

    def admin_menu(self):
        return []
