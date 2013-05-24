# -*- coding: utf-8 -*-

"""
monitor

@summary: monitor

@author: U{tannern<tannern@gmail.com>}
"""
import logging

from pylons import app_globals as g

from tg import expose, redirect
from tg.decorators import validate, without_trailing_slash
from vulcanforge.artifact.stats import ArtifactQuerySchema, ArtifactAggregator
from vulcanforge.auth.stats import LoginAggregator
from vulcanforge.cache.decorators import cache_rendered

from vulcanforge.common.controllers import BaseController
from vulcanforge.stats import STATS_CACHE_TIMEOUT, StatsQuerySchema

LOG = logging.getLogger(__name__)

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.tools.neighborhood_home:templates/monitor/'


class NeighborhoodMonitorController(BaseController):

    def __init__(self, neighborhood):
        self.neighborhood = neighborhood

    def _check_security(self):
        g.security.require_access(self.neighborhood, 'overseer')

    @expose()
    def index(self):
        redirect('artifacts')

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'artifacts.html')
    def artifacts(self):
        return {
            "title": "Collaboration Artifact Statistics",
            "data_src": "artifact_aggregate"
        }

    @expose('json')
    @cache_rendered(timeout=STATS_CACHE_TIMEOUT)
    @validate(ArtifactQuerySchema())
    def artifact_aggregate(self, date_start=None, date_end=None, bins=None,
                           artifact_type=None, order=None, label=None):
        agg = ArtifactAggregator(
            date_start=date_start,
            date_end=date_end,
            bins=bins,
            artifact_type=artifact_type,
            order=order,
            label=label,
            neighborhood=self.neighborhood.name
        )
        agg.run()
        return agg.fix_results()

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'logins.html')
    def logins(self):
        return {
            "title": "Login Statistics",
            "data_src": "login_aggregate"
        }

    @expose('json')
    @cache_rendered(timeout=STATS_CACHE_TIMEOUT)
    @validate(StatsQuerySchema())
    def login_aggregate(self, date_start=None, date_end=None, bins=None,
                        order=None, label=None):
        agg = LoginAggregator(
            date_start=date_start,
            date_end=date_end,
            bins=bins,
            order=order,
            label=label
        )
        agg.run()
        return agg.fix_results()
