import logging
import os
import re
import gzip
import glob
import tempfile
import subprocess
from itertools import groupby
from collections import defaultdict

import jsmin
import cssmin
from scss import config as scss_config, Scss
from paste.deploy.converters import asbool
from webhelpers.html import literal

import ew
from ew.core import widget_context
from vulcanforge.common.util.filesystem import mkdir_p

from .widgets import Resource, CSSLink, JSLink, JSScript, HTMLLink

LOG = logging.getLogger(__name__)

RESOURCE_URL = re.compile(r"url\([\'\"]?([^\"\'\)]+)[\'\"]?\)")
ROOTRELATIVE_URL = re.compile(r"url\([\'\"]?/([^\"\'\)]+)[\'\"]?\)")
SPRITE_MAP_PREFIX = 'SPRITE-MAP/'
RESOURCE_RECIPE_MAPPING = 'resource_recipe_mapping'


class ResourceManager(ew.ResourceManager):
    file_types = ['css', 'js', 'html']
    scopes = ['forge', 'tool', 'page']
    cache_max_age = 60 * 60 * 24 * 365
    paths = []
    kwargs = {}
    resource_cache = {}
    combine_static_resources = False
    static_resources_dir = None
    static_recipes_dir = None
    build_key = 'default'

    def __init__(self, config):
        self.script_name = config.get('ew.script_name', '/_ew_resources/')
        self._url_base = config.get('ew.url_base', '/_ew_resources/')
        self.combine_static_resources = asbool(
            config.get('combine_static_resources', 'false'))
        self.static_resources_dir = config['static_resources_dir']
        self.static_recipes_dir = config.get('static_recipes_dir',
                                             self.static_resources_dir)
        self.build_key = config.get('build_key', 'default')
        self.separator = config.get('resource_separator', ';')

        self.debug_mode = asbool(config.get('debug', 'true'))
        minify = asbool(config.get('minify_static', not self.debug_mode))
        self.use_cssmin = self.use_jsmin = minify
        self.use_cache = not self.debug_mode

        self.build_dir = os.path.join(
            self.static_resources_dir, self.build_key)
        if not os.path.exists(self.build_dir):
            try:
                mkdir_p(self.build_dir)
            except OSError:
                pass
            
        self.globals = config['pylons.app_globals']

    @property
    def resources(self):
        return widget_context.resources

    def init_resource_context(self):
        widget_context.resources = {
            'js': defaultdict(list),
            'css': defaultdict(list),
            'html': defaultdict(list)
        }

    @property
    def recipe_mapping(self):
        return self.globals.cache.redis.hgetall(RESOURCE_RECIPE_MAPPING)

    @classmethod
    def register_directory(cls, url_path, directory):
        """
        Registers a directory with a url_path.
        """
        for up, dirs in cls.paths:
            if up == url_path and not directory in dirs:
                dirs.insert(0, directory)
                return
        cls.paths.append((url_path, [directory]))

    @property
    def url_base(self):
        base = self._url_base
        if base.startswith(':'):
            base = widget_context.scheme + base
        return base

    def absurl(self, href):
        if '://' not in href and not href.startswith('/'):
            return self.url_base + href
        return href

    def emit(self, file_type):
        def squash_dupes(it):
            seen = set()
            for r in it:
                if r in seen:
                    continue
                yield r
                seen.add(r)

        def compress(it):
            grouped = groupby(it, key=lambda r: (type(r), r.compress, r.scope))
            for (cls, compress, scope), rs in grouped:
                if not compress:
                    for r in rs: yield r
                else:
                    for cr in cls.compressed(self, rs):
                        yield cr

        resources = []
        for scope in self.scopes:
            resources += widget_context.resources[file_type][scope]
        resources = squash_dupes(resources)
        if self.combine_static_resources:
            resources = compress(resources)

        yield literal('<!-- ew:%s -->\n' % file_type)
        for r in resources:
            yield r.display()
        yield literal('\n<!-- /ew:%s -->\n' % file_type)

    def register_widgets(self, context):
        """
        Registers all the widget/resource-type objects that exist as attrs on
        context
        """
        for name in dir(context):
            w = getattr(context, name)
            if isinstance(w, (ew.Widget, Resource)):
                LOG.disabled = 0
                self.register(w)

    def register(self, resource):
        """
        Registers the required resources for the given resource/widget
        """
        if isinstance(resource, Resource):
            assert resource.scope in self.scopes, \
                'Resource.scope must be one of %r' % self.scopes
            widget_context.resources[
                resource.file_type][resource.scope].append(resource)
            resource.manager = self
        elif isinstance(resource, ew.Widget):
            for r in resource.resources():
                self.register(r)
        else:  # pragma no cover
            raise AssertionError('Unknown resource type %r' % resource)

    def register_css(self, href, **kw):
        if 'scope' not in kw:
            kw['scope'] = 'page'
        self.register(CSSLink(href, **kw))

    def register_html(self, href, **kw):
        # Coerce the scope to always be forge for now
        kw['scope'] = 'forge'
        self.register(HTMLLink(href, **kw))

    def register_js(self, href, **kw):
        if 'scope' not in kw:
            kw['scope'] = 'page'
        self.register(JSLink(href, **kw))

    def register_js_snippet(self, text, **kw):
        self.register(JSScript(text, **kw))

    def get_filename(self, res_path):
        """
        Translate a resource path to a filename

        """
        if res_path.startswith(SPRITE_MAP_PREFIX):
            # cleanup
            mod_res_path = res_path.split(SPRITE_MAP_PREFIX, 1)[1]
            fs_path = os.path.join(self.build_dir, mod_res_path)
            if not os.path.isfile(fs_path):
                return None
            elif not os.path.abspath(fs_path).startswith(self.static_resources_dir):
                return None
            else:
                return fs_path

        if '/' in res_path:
            res_prefix, res_remainder = res_path.split('/', 1)
        else:
            res_prefix = ''

        for url_path, dirs in self.paths:
            if url_path == '' or res_prefix == url_path:
                for directory in dirs:
                    if url_path == '':
                        fs_path = os.path.join(directory, res_path)
                    else:
                        fs_path = os.path.join(directory, res_remainder)

                    if not os.path.isfile(fs_path):
                        # not found skip this directory
                        continue
                        # Do not allow 'breaking out' of the subdirectory
                    # using ../../.., etc
                    if not os.path.abspath(fs_path).startswith(directory):
                        return None
                    return fs_path
        return None

    def get_directories(self):
        """Translate a resource path to a filename"""
        return [dir_ for url_path, dirs in self.paths for dir_ in dirs]

    def config_scss(self):
        scss_config.STATIC_ROOT = self.scss_static_root
        scss_config.ASSETS_ROOT = self.build_dir

        if self.debug_mode:
            scss_config.ASSETS_URL = self.absurl(SPRITE_MAP_PREFIX)
        else:
            scss_config.ASSETS_URL = SPRITE_MAP_PREFIX

    def scss_static_root(self, scss_images):
        """
        Listing image files for scss
        """
        scss_images_dir, png_filter = scss_images.rsplit('/', 1)
        res_prefix, res_remainder = scss_images_dir.split('/', 1)
        for url_path, dirs in self.paths:
            if url_path == '' or res_prefix == url_path:
                for directory in dirs:
                    if url_path == '':
                        fs_path = os.path.join(directory, scss_images_dir)
                    else:
                        fs_path = os.path.join(directory, res_remainder)

                    if os.path.isdir(fs_path):
                        glob_path = os.path.join(fs_path, png_filter)
                        files = glob.glob(glob_path)
                        return [(file, None) for file in files]
                    else:
                        continue

        return []

    def expand_css_urls(self, content):
        resource_urls = re.findall(ROOTRELATIVE_URL, content)
        # Just in case the same url is listed twice
        resource_urls_set = set(resource_urls)
        for resource_url in resource_urls_set:
            if SPRITE_MAP_PREFIX in resource_url:
                continue
            expanded_url = self.absurl(resource_url)
            content = content.replace('/' + resource_url, expanded_url)

        return content

    def hashed_file(self, file_type, rel_resource_paths):
        joined_list = self.separator.join(rel_resource_paths)
        hashed_file_name = str(abs(hash(joined_list))) + '.' + file_type
        if not self.globals.cache.redis.hexists(RESOURCE_RECIPE_MAPPING, hashed_file_name):
            self.globals.cache.redis.hset(
                RESOURCE_RECIPE_MAPPING,
                hashed_file_name,
                joined_list)

        return hashed_file_name

    def write_slim_file(self, file_type, rel_resource_paths,
                        destination_dir=None):
        """
        Write files with concat+minify+gzip
        """
        if destination_dir is None:
            destination_dir = self.build_dir
        hashed_file_name = self.hashed_file(file_type, rel_resource_paths)
        build_file_path = os.path.join(destination_dir, hashed_file_name)
        content = None
        if not os.path.exists(build_file_path):
            if file_type == 'js':
                valid_paths = [h for h in rel_resource_paths
                        if h is not None and self.get_filename(h) is not None]
                if self.use_jsmin:
                    # Only minify if the file has not been minified yet
                    content = '\n'.join(
                        open(self.get_filename(h)).read() if ".min.js" in h
                        else jsmin.jsmin(open(self.get_filename(h)).read())
                        for h in valid_paths)
                else:
                    content = '\n'.join(
                        open(self.get_filename(h)).read() for h in valid_paths)
            elif file_type == 'css':
                content_list = []
                for h in rel_resource_paths:
                    css_path = self.get_filename(h)
                    css_url_dir = os.path.dirname(h) # namespace/css/a.css -> namespace/css
                    remove_starting_slash = False
                    if not css_url_dir.startswith('/'):
                        remove_starting_slash = True
                        css_url_dir = '/' + css_url_dir # namespace/css -> /namespace/css
                    if h is not None and css_path is not None:
                        try:
                            with open(css_path, 'r') as fp:
                                content = fp.read()
                        except Exception:
                            LOG.exception(
                                'Error reading static resource: %s', css_path)
                            continue

                        if css_path.endswith('.scss'):
                            scss_compiler = Scss(scss_opts={
                                'compress': False,
                                'debug_info': False,
                                'load_paths': self.get_directories()
                            })
                            content = scss_compiler.compile(content)

                        resource_urls = re.findall(RESOURCE_URL, content)
                        # Just in case the same url is listed twice
                        resource_urls_set = set(resource_urls)
                        for resource_url in resource_urls_set:
                            if SPRITE_MAP_PREFIX in resource_url:
                                continue
                            namespaced_resource_url = os.path.abspath(os.path.join(css_url_dir, resource_url))
                            if remove_starting_slash:
                                namespaced_resource_url = namespaced_resource_url[1:]
                            content = content.replace(resource_url, namespaced_resource_url)

                        content = content.replace(SPRITE_MAP_PREFIX, '')
                        content_list.append(content)

                if self.use_cssmin:
                    content = cssmin.cssmin('\n'.join(content_list))
                else:
                    content = '\n'.join(content_list)
            elif file_type == 'html':
                # This is where vulcanization happens
                # Create a temporary file with the links to vulcanize in the
                # static resources folder
                with tempfile.NamedTemporaryFile(suffix='.html',
                                             dir=destination_dir) as input_file:
                    for h in rel_resource_paths:
                        input_file.write('<link rel="import" href="{}"/>'.format(h))
                    input_file.flush()

                    # Now vulcanize it into the file we want
                    with tempfile.NamedTemporaryFile(suffix=".html",
                                          dir=destination_dir) as output_file:
                        call_args = [
                            'vulcanize', '-p', destination_dir,
                            '--out-html', output_file.name,
                            '--inline-scripts',
                            '--inline-css',
                            '--strip-comments',
                            os.path.basename(input_file.name)]
                        subprocess.check_call(call_args)
                        content = output_file.read()

            if content is not None:
                zip_file = gzip.GzipFile(build_file_path, 'wb')
                zip_file.write(content)
                zip_file.close()

    def serve_slim(self, file_type, href):
        content_path = os.path.join(self.static_resources_dir,
            self.build_key,
            href)
        if not os.path.abspath(content_path).startswith(
                self.static_resources_dir):
            raise IOError()

        if not os.path.exists(content_path):
            if file_type not in self.file_types:
                raise IOError()
            if self.globals.cache.redis.hexists(RESOURCE_RECIPE_MAPPING, href):
                recipe = self.globals.cache.redis.hget(RESOURCE_RECIPE_MAPPING, href)
                resource_list = recipe.strip().split(self.separator)
                try:
                    self.write_slim_file(file_type, resource_list)
                except Exception, e:
                    msg = "Unable to serve '{}' with resources {}"
                    LOG.error(msg.format(href, resource_list))
                    raise
            else:
                raise IOError()

        stat = os.stat(content_path)
        content = open(content_path).read()
        resource = (content, stat.st_mtime)
        return resource
