import logging

from bson import ObjectId
from pylons import app_globals as g, tmpl_context as c
from pysolr import SolrError
from tg import expose, redirect
from tg.decorators import with_trailing_slash
from vulcanforge.auth.model import User
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.widgets.util import PageList
from vulcanforge.neighborhood.marketplace import model as marketplace_model
from vulcanforge.project.model import Project

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:neighborhood/marketplace/templates/'
LOG = logging.getLogger(__name__)


class NeighborhoodMarketplaceController(BaseController):

    class Widgets(BaseController.Widgets):
        page_list = PageList()

    def __init__(self, neighborhood):
        self.neighborhood = neighborhood

    def _before(self, *args, **kwargs):
        g.context_manager.set(
            '--init--', mount_point='home', neighborhood=self.neighborhood)

    @classmethod
    def creatable_ad_projects(cls):
        """find all the projects the user can make ads for"""
        creatable_ad_projects = []
        # start by looping over all of their projects
        user_projects = c.user.my_projects()
        for project in user_projects:
            if not project.is_real():
                continue

            # exclude projects outside of this neighborhood
            if project.neighborhood._id != c.project.neighborhood._id:
                continue
                # exclude projects they are not an admin of
            if not g.security.has_access(project, 'admin'):
                continue
                # exclude projects that alread have advertisements
            if marketplace_model.ProjectAdvertisement.query.get(
                    project_id=project._id):
                continue
            creatable_ad_projects.append(project)

        return creatable_ad_projects

    def latest_params(self, limit=10):
        """
        Parameters for displaying the parameters necessary for rendering
        index_content

        """
        user_ads, project_ads = [], []
        user_result = self._search_ads(search_type='User', limit=limit)
        if user_result and user_result.hits:
            for u_doc in user_result.docs:
                u_doc['user'] = User.query.get(
                    _id=ObjectId(u_doc['user_id_s']))
                user_ads.append(u_doc)

        project_result = self._search_ads(search_type='Project', limit=limit)
        if project_result and project_result.hits:
            for p_doc in project_result.docs:
                p_doc['project'] = Project.query.get(
                    _id=ObjectId(p_doc['project_id_s']))
                project_ads.append(p_doc)

        # find out if the user has an ad
        user_has_ad = marketplace_model.UserAdvertisement.query.get(
            user_id=c.user._id) is not None

        return {
            'market_url': '{}market/'.format(c.app.url),
            'user_ads': user_ads,
            'project_ads': project_ads,
            'more_users': user_result.hits > limit,
            'more_projects': project_result.hits > limit,
            'user_has_ad': user_has_ad,
            'creatable_ad_projects': self.creatable_ad_projects()
        }

    def _search_ads(self, q='*:*', search_type='Project', start=0, limit=25,
                    sort='pubdate_dt desc'):
        search_type = search_type.capitalize()
        if search_type not in ['User', 'Project']:
            search_type = 'Project'
        fq = ['type_s:{}Advertisement'.format(search_type)]
        if search_type == 'Project':
            fq.append(
                'read_roles:("%s")' %
                '" OR "'.join(g.security.get_user_read_roles())
            )
        solr_params = {
            'q': q,
            'fq': fq,
            'start': start,
            'rows': limit,
            'sort': sort,
            }
        return g.search(**solr_params)

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'index.html')
    def index(self, **kwargs):
        return self.latest_params()

    def _search(self, q='*:*', search_type='Project', page=0, limit=25,
                sort='score desc', **kwargs):
        if q == "":
            q = '*:*'
        c.page_list = self.Widgets.page_list
        limit, page, start = g.handle_paging(limit, page)
        results = []

        try:
            solr_results = self._search_ads(
                q=q,
                search_type=search_type,
                start=start,
                limit=limit,
                sort=sort
            )
            # get the objects from mongo
            for doc in solr_results.docs:
                ad_class = getattr(marketplace_model, doc['type_s'])
                _id = ObjectId(doc['_id_s'])
                ad = ad_class.query.get(_id=_id)
                if ad is not None:
                    results.append(ad)
            count = solr_results.hits
        except (SolrError, AttributeError), e:
            LOG.exception(e)
            count = 0

        return {
            'q': q,
            'page': page,
            'limit': limit,
            'count': count,
            'results': results,
            'search_type': search_type,
        }

    @expose()
    def search(self, **kwargs):
        search_type = kwargs.get("search_type", "User")
        if search_type == "User":
            return redirect("browse_users", kwargs)

        return redirect("browse_projects", kwargs)

    @expose(TEMPLATE_DIR + 'browse.html')
    def browse_users(self, q='*:*', search_type="User", **kwargs):
        context = self._search(q=q, search_type=search_type,
            sort="pubdate_dt desc", **kwargs)
        context.update({
            'title': 'Competitors Looking for Teams',
        })
        return context

    @expose(TEMPLATE_DIR + 'browse.html')
    def browse_projects(self, q='*:*', search_type="Project", **kwargs):
        context = self._search(q=q, search_type=search_type,
            sort="pubdate_dt desc", **kwargs)
        context.update({
            'title': 'Teams Looking for Members',
            })
        return context
