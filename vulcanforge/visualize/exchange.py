"""
A few classes for integration with the vulcan exchange

"""
import logging
from markupsafe import Markup
import os
from urlparse import urlparse

from webob import exc
from pylons import app_globals as g, tmpl_context as c
from tg import expose, validate, redirect

from vulcanforge.artifact.widgets import BaseArtifactRenderer
from vulcanforge.common.util.http import set_download_headers
from vulcanforge.common.validators import ObjectIdValidator
from vulcanforge.exchange.controllers.view import ArtifactViewController
from vulcanforge.resources.widgets import CSSLink

LOG = logging.getLogger(__name__)
ON_UNVISUALIZABLE_TMPL = '''
<div class="padded">
    <p>This resource cannot be visualized within the context of the forge.
    <a class="btn" href="{resource_url}">Download</a> it instead.</p>
</div>
'''


class VisualizableRenderer(BaseArtifactRenderer):
    def resources(self):
        for r in super(VisualizableRenderer, self).resources():
            yield r
        yield CSSLink('visualize/vf_visualizer_embedder.scss')

    def display(self, artifact, node=None, extra_params=None, **kwargs):
        if 'resource_url' not in kwargs and self.is_exchange and node:
            local_url = '{}view/raw?node_id={}'.format(node.url_prefix, node._id)
            download_url = '{}view/download?node_id={}'.format(node.url_prefix,
                                                       node._id)
            extra_params = {'node_id': node._id,
                            'resource_url': local_url}
            kwargs['download_url'] = download_url
            if 'on_unvisualizable' not in kwargs:
                def on_unvisualizable(r):
                    s = ON_UNVISUALIZABLE_TMPL.format(resource_url=local_url)
                    return Markup(s)
                kwargs['on_unvisualizable'] = on_unvisualizable
        return g.visualize_artifact(artifact).full_render(
            extra_params=extra_params, **kwargs)


class VisualizableExchangeViewController(ArtifactViewController):
    @expose()
    @validate({"node_id": ObjectIdValidator()})
    def raw(self, node_id, **kwargs):
        node = c.artifact_config['node'].query.get(_id=node_id)
        if not node:
            raise exc.HTTPNotFound
        g.security.require_access(node, 'read')

        artifact = node.artifact
        if hasattr(artifact, 'local_url'):
            local_url = artifact.local_url()
            if 'node_id' not in local_url:
                if "?" in local_url:
                    local_url += "&node_id={}".format(node_id)
                else:
                    local_url += "?node_id={}".format(node_id)
            redirect(local_url)

        parsed = urlparse(artifact.url())
        filename = os.path.basename(parsed.path)
        set_download_headers(filename)

        return iter(artifact)

    @expose()
    @validate({"node_id": ObjectIdValidator()})
    def download(self, node_id, **kwargs):
        node = c.artifact_config['node'].query.get(_id=node_id)
        if not node:
            raise exc.HTTPNotFound
        g.security.require_access(node, 'read')

        artifact = node.artifact
        parsed = urlparse(artifact.url())
        filename = os.path.basename(parsed.path)
        set_download_headers(filename)

        if not g.s3_serve_local and hasattr(artifact, 'get_s3_temp_url'):
            redirect(artifact.get_s3_temp_url())
        else:
            return iter(artifact)