import logging

from vulcanforge.common.helpers import pretty_print_file_size
from vulcanforge.visualize.model import Visualizer


LOG = logging.getLogger(__name__)


def _make_vis_url(method, url, visualizer=None, query=''):
    if not visualizer:
        visualizers = Visualizer.get_for_resource(url)
        if not visualizers:
            return url
        visualizer = visualizers[0]
    return '/visualize/%s/%s/%s' % (str(visualizer._id), method, query)


def get_fs_url(url, visualizer=None):
    query = '?resource_url=%s&mode=fullscreen' % url
    return _make_vis_url('fs', url, visualizer, query)


def get_iframe_url(url, visualizer=None, extra_params=None):
    query = '?resource_url=%s&mode=embed' % url
    if extra_params:
        query += '&' + extra_params
    return _make_vis_url('src', url, visualizer, query)


def iframe_json_item(url, visualizer, extra_params):
    return '{{"name": "{}", "url": "{}", "fs_url": "{}"}}'.format(
        visualizer.name.replace('"', '\\"'),
        get_iframe_url(url, visualizer, extra_params).replace('"', '\\"'),
        get_fs_url(url, visualizer).replace('"', '\\"')
    )


def url_iframe_json(url, visualizers=None, extra_params=None):
    if visualizers is None:
        visualizers = Visualizer.get_for_resource(url)
    return '[%s]' % ','.join(
        iframe_json_item(url, v, extra_params) for v in visualizers
    )


def artifact_iframe_json(artifact, visualizers=None, extra_params=None):
    if visualizers is None:
        visualizers = Visualizer.get_for_resource(artifact.url())
    items = []
    for visualizer in visualizers:
        items.append(iframe_json_item(
            artifact.url_for_visualizer(visualizer), visualizer, extra_params
        ))
    return '[%s]' % ','.join(items)


def render_fs_urls(url, visualizers=None, dl_too=False, size=None):
    if visualizers is None:
        visualizers = Visualizer.get_for_resource(url)

    urls = []
    for visualizer in visualizers:
        escaped_name = visualizer.name.replace('"', '\\"')
        urls.append(
            '{{"name": "{name}", "url": "{url}", "title": "{name}"}}'.format(
                name=escaped_name,
                url=get_fs_url(url, visualizer).replace('"', '\\"')
            )
        )
    if dl_too:
        name = 'Download File...'
        if size is not None:
            name += ' ({})'.format(pretty_print_file_size(size))
        urls.append('{name: "%s", url: "%s", title: "%s"}' % (
            name, url.replace('"', '\\"'), 'Download File'))
    return '[%s]' % ','.join(urls)

    #REPO_ARTIFACT_RE = re.compile(r"""
    #    /ci/(?P<commit_id>[a-z0-9]+)    # get commit object_id
    #    /tree(?P<path>/[^\?]*)          # get file path
    #    (?:\?.*)?$                      # dont care about query params
    #""", re.VERBOSE)

    #def get_refid_from_url(url):
    #    """
    #    Get ArtifactReference id for artifact associated with url, if any
    #
    #    @param url: str         resource_url
    #    @return: str,None       reference_id for associated artifact
    #
    #    """
    #    artifact = None
    #    m = REPO_ARTIFACT_RE.search(url)
    #    if m:
    #        commit = M.Commit.query.get(object_id= m.group('commit_id'))
    #        if commit:
    #            artifact = commit.get_path(m.group('path'))
    #    if artifact:
    #        return artifact.index_id()
