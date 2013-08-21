import logging
import os
import re
import gzip
import glob
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

from .widgets import Resource, CSSLink, JSLink, JSScript

LOG = logging.getLogger(__name__)

RESOURCE_URL = re.compile(r"url\([\'\"]?([^\"\'\)]+)[\'\"]?\)")
RECIPE_FILE = 'static_recipes.txt'
SPRITE_MAP_PREFIX = 'SPRITE-MAP/'


class ResourceManager(ew.ResourceManager):
    file_types = ['css', 'js']
    scopes = ['forge', 'tool', 'page']
    cache_max_age = 60 * 60 * 24 * 365
    paths = []
    kwargs = {}
    resource_cache = {}
    combine_static_resources = False
    static_resources_dir = None
    build_key = 'default'

    def __init__(self, config):
        self.script_name = config.get('ew.script_name', '/_ew_resources/')
        self._url_base = config.get('ew.url_base', '/_ew_resources/')
        self.combine_static_resources = asbool(
            config.get('combine_static_resources', 'false'))
        self.static_resources_dir = config.get('static_resources_dir', None)
        self.build_key = config.get('build_key', 'default')

        self.debug_mode = asbool(config.get('debug', 'true'))
        minify = asbool(config.get('minify_static', not self.debug_mode))
        self.use_cssmin = self.use_jsmin = minify
        self.use_cache = not self.debug_mode

        self.build_dir = os.path.join(
            self.static_resources_dir, self.build_key)
        if not os.path.exists(self.build_dir):
            mkdir_p(self.build_dir)

    @property
    def resources(self):
        return widget_context.resources

    def init_resource_context(self):
        widget_context.resources = {
            'js': defaultdict(list),
            'css': defaultdict(list)
        }

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
            mod_res_path = res_path.split(SPRITE_MAP_PREFIX,1)[1]
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

    def extend_recipe_list(self, recipe):
        recipe = recipe + os.linesep
        recipe_path = os.path.join(self.static_resources_dir, RECIPE_FILE)
        recipe_list = []

        if os.path.exists(recipe_path):
            recipe_file = open(recipe_path, 'r+')
            recipe_list = [line for line in recipe_file]
        else:
            recipe_file = open(recipe_path, 'w')

        if recipe not in recipe_list:
            recipe_file.writelines(recipe)
            recipe_file.flush()

        recipe_file.close()

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

    def write_slim_file(self, file_type, rel_resource_paths):
        """
        Write files with concat+minify+gzip
        """
        joined_list = ';'.join(rel_resource_paths)
        file_hash = str(abs(hash(joined_list))) + '.' + file_type
        build_file_path = os.path.join(self.build_dir, file_hash)
        if not os.path.exists(build_file_path):
            if file_type == 'js' and self.use_jsmin:
                content = '\n'.join(
                    jsmin.jsmin(open(self.get_filename(h)).read())
                    for h in rel_resource_paths
                    if h is not None and self.get_filename(h) is not None)
            elif file_type == 'css' and self.use_cssmin:
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

                content = cssmin.cssmin('\n'.join(content_list))

            zip_file = gzip.GzipFile(build_file_path, 'wb')
            zip_file.write(content)
            zip_file.close()

            self.extend_recipe_list(joined_list)

        return file_hash

    def serve_slim(self, file_type, href):
        if href in self.resource_cache:
            return self.resource_cache[href]

        content_path = os.path.join(self.static_resources_dir, self.build_key,
                                    href)
        if not os.path.abspath(content_path).startswith(
                self.static_resources_dir):
            raise IOError()

        stat = os.stat(content_path)
        content = open(content_path).read()
        resource = (content, stat.st_mtime)
        if self.use_cache:
            self.resource_cache[href] = resource
        return resource
