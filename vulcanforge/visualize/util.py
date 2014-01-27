import logging
import urllib

from pylons import app_globals as g

from vulcanforge.common.helpers import pretty_print_file_size
from vulcanforge.visualize.model import VisualizerConfig


LOG = logging.getLogger(__name__)


def get_resource_interface(resource):
    if isinstance(resource, basestring):
        resource_i = g.visualize_url(resource)
    else:
        resource_i = g.visualize_artifact(resource)
    return resource_i


def get_visualizer_options(resource, shortnames=None, dl_too=True, size=None,
                           extra_params=None):
    resource_i = get_resource_interface(resource)
    fs_items = []
    if shortnames:
        cur = VisualizerConfig.query.find({"shortname": {"$in": shortnames}})
        visualizers = [config.load() for config in cur]
    else:
        visualizers = resource_i.find_visualizers()
    for visualizer in visualizers:
        escaped_name = visualizer.config.name.replace('"', '\\"')
        _, fs_url = resource_i.get_content_urls_for_visualizer(
            visualizer, extra_params=extra_params)
        fs_items.append({
            "name": escaped_name,
            "url": fs_url,
            "title": escaped_name
        })
    if dl_too:
        name = 'Download File...'
        if size is not None:
            name += ' ({})'.format(pretty_print_file_size(size))
        fs_items.append({
            "name": name,
            "url": resource_i.download_url,
            "title": name
        })
    return fs_items
