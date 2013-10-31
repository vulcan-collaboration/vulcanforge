import logging
import urllib

from pylons import app_globals as g

from vulcanforge.common.helpers import pretty_print_file_size


LOG = logging.getLogger(__name__)


def get_fs_items(url, visualizers=None, dl_too=False, size=None):
    if visualizers is None:
        visualizers = g.visualize.find_visualizers_by_url(url)

    fs_items = []
    for visualizer in visualizers:
        escaped_name = visualizer.config.name.replace('"', '\\"')
        query_str = urllib.urlencode(visualizer.get_query_str_for_url(url))
        fs_items.append({
            "name": escaped_name,
            "url": visualizer.fs_url + '?' + query_str,
            "title": escaped_name
        })
    if dl_too:
        name = 'Download File...'
        if size is not None:
            name += ' ({})'.format(pretty_print_file_size(size))
        fs_items.append({
            "name": name,
            "url": url,
            "title": name
        })
    return fs_items
