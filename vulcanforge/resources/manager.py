import logging
import os
import re
import jsmin
import cssmin
import gzip

from itertools import groupby
from collections import defaultdict
import scss
from paste.deploy.converters import asbool
from webhelpers.html import literal

import ew
from ew.core import widget_context

from .widgets import Resource, CSSLink, JSLink, JSScript

LOG = logging.getLogger(__name__)
CSS_IMAGE_RE0 = re.compile(r"url\([\'\"]?images/([^\"\'\)]+)[\'\"]?\)",
                           re.VERBOSE)
CSS_IMAGE_RE1 = re.compile(r"url\([\'\"]?../images/([^\"\'\)]+)[\'\"]?\)",
                           re.VERBOSE)
CSS_IMAGE_RE2 = re.compile(r"url\([\'\"]?../img/([^\"\'\)]+)[\'\"]?\)",
                           re.VERBOSE)
CSS_IMAGE_RE3 = re.compile(r"url\([\'\"]?./([^\"\'\)]+)[\'\"]?\)", re.VERBOSE)
CSS_IMAGE_RE4 = re.compile(r"url\([\'\"]?([^\"\'\/\)]+)[\'\"]?\)", re.VERBOSE)

CSS_FONTS_RE = re.compile(r"url\([\'\"]?../fonts/([^\"\'\)]+)[\'\"]?\)",
                          re.VERBOSE)

RECIPE_FILE = 'static_recipes.txt'
RFC_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'


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
            config.get('combine_static_resources', 'false')
        )
        self.static_resources_dir = config.get('static_resources_dir', None)
        self.build_key = config.get('build_key', 'default')

        debug_mode = asbool(config.get('debug', 'true'))
        self.use_cache = self.use_cssmin = self.use_jsmin = not debug_mode

        self.resources = {
            'js': defaultdict(list),
            'css': defaultdict(list)
        }

    @classmethod
    def register_directory(cls, url_path, directory):
        """
        Registers a directory with a url_path.
        """
        for up, dirs in cls.paths:
            if up == url_path:
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
            resources += self.resources[file_type][scope]
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
            self.resources[resource.file_type][resource.scope].append(resource)
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

    def _locate_real_file(self, res_path):
        for url_path, dirs in self.paths:
            if res_path.startswith(url_path):
                for directory in dirs:
                    fs_path = os.path.join(
                        directory,
                        res_path[len(url_path) + 1:])
                    if not os.path.isfile(fs_path):
                        # not found skip this directory
                        continue
                        # Do not allow 'breaking out' of the subdirectory
                    # using ../../.., etc
                    if not os.path.abspath(fs_path).startswith(directory):
                        return None
                    return fs_path, url_path, directory, dirs
        return None

    def get_filename(self, res_path):
        """
        Translate a resource path to a filename
        """
        path_info = self._locate_real_file(res_path)
        if path_info is None:
            return None
        return path_info[0]

    def get_directory_root(self, res_path):
        """
        Translate a resource path to a filename
        """
        path_info = self._locate_real_file(res_path)
        if path_info is None:
            return None
        return path_info[2]

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

    def write_slim_file(self, file_type, rel_resource_paths):
        '''
        Write files with concat+minify+gzip
        '''
        build_dir = os.path.join(self.static_resources_dir, self.build_key)
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        joined_list = ';'.join(rel_resource_paths)
        file_hash = str(abs(hash(joined_list))) + '.' + file_type
        build_file_path = os.path.join(build_dir, file_hash)
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
                    if h is not None and css_path is not None:

                        try:
                            with open(css_path, 'r') as fp:
                                content = fp.read()
                        except Exception:
                            LOG.exception(
                                'Error reading static resource: %s', css_path)
                            continue

                        if css_path.endswith('.scss'):
                            scss_parser = scss.Scss(scss_opts={
                                'compress': False,
                                'debug_info': False,
                            })

                            scss.STATIC_ROOT = self.get_directory_root(h)
                            scss.ASSETS_ROOT = build_dir
                            scss.ASSETS_URL = 'SPRITE-MAP/'
                            scss.LOAD_PATHS = ','.join(self.get_directories())
                            content = scss_parser.compile(content)

                        root3, css_name = os.path.split(css_path)
                        root2, folder2 = os.path.split(root3)
                        root1, folder1 = os.path.split(root2)

                        content = CSS_IMAGE_RE0.sub(
                            'url(%s/images/\g<1>)' % folder2, content)
                        content = CSS_IMAGE_RE1.sub(
                            'url(%s/images/\g<1>)' % folder1, content)
                        content = CSS_IMAGE_RE2.sub(
                            'url(%s/img/\g<1>)' % folder1, content)
                        content = CSS_IMAGE_RE3.sub(
                            'url(%s/%s/\g<1>)' % (folder1, folder2), content)
                        content = CSS_IMAGE_RE4.sub(
                            'url(%s/%s/\g<1>)' % (folder1, folder2), content)

                        content = CSS_FONTS_RE.sub(
                            'url(%s/fonts/\g<1>)' % folder1, content)

                        content = content.replace('SPRITE-MAP/', '')
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

    def __repr__(self):  # pragma no cover
        l = ['<ResourceManager>']
        for name, res in self.resources.iteritems():
            l.append('  <Location %s>' % name)
            for r in res: l.append('    %r' % r)
        for u, d in self.paths:
            l.append('  <Path url="%s" directory="%s">' % (u, d))
        return '\n'.join(l)

