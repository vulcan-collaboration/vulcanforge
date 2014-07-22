import gzip
import logging
import tarfile
import zipfile
import bz2
import re
import os
from urllib2 import urlopen
from contextlib import contextmanager

import jinja2
from jinja2.loaders import FileSystemLoader

import vulcanforge.command
from vulcanforge.command import base
from vulcanforge.common.util.filesystem import temporary_zip_extract

log = logging.getLogger(__name__)
URL_RE = re.compile(r"$(?:https?|ftp)://")
DEFAULT_TEMPLATE = os.path.join(
    vulcanforge.command.__path__[0], 'resources', 'vulcan_template')
ZIP_EXT_MAP = [
    ('.zip', zipfile.ZipFile),
    ('.tar.gz', tarfile.open),
    ('.tar.bz', tarfile.open),
    ('.tar', tarfile.open),
    ('.bz', bz2.BZ2File),
    ('.gz', gzip.GzipFile)
]


class CreateVulcanAppCommand(base.Command):
    summary = "Creates a new vulcan application"
    parser = base.Command.standard_parser(verbose=True)
    usage = '<package> <target directory (defaults to current)>'
    min_args = 1
    max_args = 2
    parser.add_option(
        '-n', '--name', help="Project name (defaults to name of package)")
    parser.add_option(
        '-r', '--repos', default=False, action="store_true",
        help="Application includes support for repositories (should have "
             "vulcanrepo installed)")
    parser.add_option(
        '-t', '--template',
        help='Path to custom application template (file path or url')

    def command(self):
        context = {
            "repo": self.options.repos,
            "package": self.args[0],
            "project": self.options.name or self.args[0]
        }

        if len(self.args) > 1:
            target_dir = self.args[1]
        else:
            target_dir = os.getcwd()

        with self.with_src_directory() as src_dir:
            self.write_template(src_dir, target_dir, context)

    def write_template(self, src_dir, target_dir, context):
        jinja_env = jinja2.Environment(loader=FileSystemLoader(src_dir))
        for root, dirs, fnames in os.walk(src_dir):
            rel_path = os.path.relpath(root, src_dir)
            for dirname in dirs:
                path = os.path.join(target_dir, rel_path, dirname)
                path = path.replace('_package_', context['package'])
                os.makedirs(path)
            for fname in fnames:
                src_path = os.path.join(rel_path, fname)
                path = os.path.join(target_dir, src_path)
                path = path.replace('_package_', context['package'])
                if fname.endswith('.jinja'):
                    template = jinja_env.get_template(src_path)
                    content = template.render(**context).encode('utf8')
                    path = path[:-6]
                else:
                    with open(os.path.join(root, fname), 'rb') as fp:
                        content = fp.read()
                with open(path, 'wb') as fp:
                    fp.write(content)

    @contextmanager
    def with_src_directory(self):
        template = self.options.template
        if not template:
            template = DEFAULT_TEMPLATE
        if URL_RE.match(template):
            fname = os.path.basename(template)
            for (ext, zip_module) in ZIP_EXT_MAP:
                if fname.endswith(ext):
                    break
            else:
                zip_module = zipfile.ZipFile
            resp = urlopen(template)
            with temporary_zip_extract(resp, zip_module=zip_module) as dirname:
                yield dirname
        else:
            yield template






