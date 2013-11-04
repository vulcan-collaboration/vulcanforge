import logging
import os
import urllib
import urlparse
import json

from bson import ObjectId
from bson.errors import InvalidId
from formencode import validators
from webob import exc
from pylons import tmpl_context as c, app_globals as g
from tg.decorators import expose, validate

from vulcanforge.common.controllers import BaseController
from vulcanforge.visualize.model import VisualizerConfig

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:visualize/templates/'


class VisualizerRootController(BaseController):

    @expose(TEMPLATE_DIR + 'render_resource.html')
    @validate({"height": validators.Int()})
    def render_resource(self, resource_url, iframe_query=None, height=None,
                        **kw):
        extra_params = {}
        if iframe_query:
            extra_params.update(
                dict(urlparse.parse_qsl(urllib.unquote(iframe_query)))
            )
        return {
            "resource_url": resource_url,
            "extra_params": extra_params,
            "height": height
        }

    @expose()
    def _lookup(self, key, *remainder):
        try:
            vis_id = ObjectId(key)
        except InvalidId:
            raise exc.HTTPNotFound

        # try to find a matching id
        visualizer = VisualizerConfig.query.get(_id=vis_id)
        # try to find a matching mime-type
        if visualizer is None:  # pragma no cover
            visualizer = VisualizerConfig.query.get({
                'mime_types': key
            })
        vc = VisualizerController(visualizer)

        return vc, remainder


class VisualizerController(BaseController):

    def __init__(self, visualizer):
        self.visualizer = visualizer

    def _check_security(self):
        # in the future we check access to visualizer here
        return True

    @expose()
    def content(self, resource_url='', *args, **kw):
        """Renders visualizer content"""
        # check permissions
        if self.visualizer is None:
            raise exc.HTTPForbidden()

        visualizer_obj = self.visualizer.load()
        return visualizer_obj.render_content(resource_url)

    @expose(TEMPLATE_DIR + 'fullscreen.html')
    def fs(self, resource_url=None, iframe_query=None, **kw):
        # get iframe query, if exists
        query_params = {'mode': 'fullscreen', 'resource_url': resource_url}
        base_query = query_params.copy()
        if iframe_query:
            parsed = urlparse.parse_qsl(urllib.unquote(iframe_query))
            query_params.update(dict(parsed))

        # fix resource url
        query_params['resource_url'] = query_params['resource_url']\
            .replace(' ', '%20')

        base_url, rquery = urllib.splitquery(query_params['resource_url'])
        filename = os.path.basename(base_url)
        return dict(
            logo_url=g.home_url,
            active_visualizer=self.visualizer,
            filename=filename,
            query_str=urllib.urlencode(query_params, doseq=True),
            base_query=urllib.urlencode(base_query, doseq=True),
            resource_url=resource_url.replace('#', '%23'),
            context='fullscreen',
            workspace_references=json.dumps(c.user.get_workspace_references())
        )
