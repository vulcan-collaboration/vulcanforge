# -*- coding: utf-8 -*-

"""
root

@summary: root

@author: U{tannern<tannern@gmail.com>}
"""
import logging

from pylons import tmpl_context as c, app_globals as g
from tg.decorators import expose

from vulcanforge.common.controllers import BaseController
from vulcanforge.neighborhood.controllers import \
    NeighborhoodProjectBrowseController
from vulcanforge.neighborhood.marketplace.controllers import NeighborhoodMarketplaceController
from vulcanforge.tools.neighborhood_home.controllers.monitor import \
    NeighborhoodMonitorController

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.tools.neighborhood_home:templates/'


class NeighborhoodHomeRootController(BaseController):

    def __init__(self, project, app_config):
        super(NeighborhoodHomeRootController, self).__init__()
        self.neighborhood = project.neighborhood
        self.project = project
        self.app_config = app_config
        self.browse = NeighborhoodProjectBrowseController(
            neighborhood=self.neighborhood,
            hide_sidebar=False
        )
        self.monitor = NeighborhoodMonitorController(self.neighborhood)
        if self.neighborhood.enable_marketplace:
            self.market = NeighborhoodMarketplaceController(
                self.neighborhood
            )

    @expose(TEMPLATE_DIR + 'master.html')
    def index(self, **kwargs):
        return {
            'hide_header': True,
            'content': g.markdown.convert(self.neighborhood.homepage),
        }


class NeighborhoodHomeRestController(BaseController):

    def _check_security(self):
        g.security.require_access(c.project, 'read')

    @expose('json:')
    def index(self, **kwargs):
        return dict(shortname=c.project.shortname)
