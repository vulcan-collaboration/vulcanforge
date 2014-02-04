import getpass
import logging
import os
import shutil

from pylons import app_globals as g

from vulcanforge.common.util.filesystem import mkdir_p
from vulcanforge.resources.manager import RECIPE_FILE


class StaticResourceStager(object):

    def __init__(self, destination_dir=None, log=None):
        if destination_dir is None:
            destination_dir = g.resource_manager.build_dir
        self.destination_dir = destination_dir
        self.exceptions = []
        self.log = log or logging.getLogger(__name__)
        self.log.info("User is '{}'.".format(getpass.getuser()))

    def copy_images(self, source_dir, destination_dir):
        if not source_dir.endswith('/'):
            source_dir += '/'
        for root, dirs, files in os.walk(source_dir):
            for res_file in files:
                file_path, ext = os.path.splitext(res_file)
                if ext in ['.js', '.css', '.scss', ]:
                    continue
                source_tail = root.split(source_dir)[1]
                res_file_path = os.path.join(root, res_file)
                destination_dir2 = os.path.join(destination_dir, source_tail)
                if not os.path.exists(destination_dir2):
                    mkdir_p(destination_dir2)

                shutil.copy2(res_file_path, destination_dir2)

    def stage_images(self):
        for (namespace, directories) in g.resource_manager.paths:
            for directory in directories[::-1]:
                destination_dir = os.path.join(self.destination_dir, namespace)
                self.copy_images(directory, destination_dir)

    def iter_css_js(self):
        recipe_path = os.path.join(
            g.resource_manager.static_recipes_dir, RECIPE_FILE)

        if not os.path.exists(recipe_path):
            with open(recipe_path, 'w') as fp:
                fp.write('')
                raise StopIteration

        with open(recipe_path, 'r') as fp:
            for line in fp:
                resource_list = line.strip().split(
                    g.resource_manager.separator)
                file_type = None
                for resource in resource_list:
                    if resource.endswith('.js'):
                        file_type = 'js'
                        break
                    elif resource.endswith('.css'):
                        file_type = 'css'
                        break
                if file_type is None:
                    continue
                yield file_type, resource_list

    def stage_css_js(self):
        for file_type, resource_list in self.iter_css_js():
            try:
                g.resource_manager.write_slim_file(
                    file_type,
                    resource_list,
                    destination_dir=self.destination_dir)
            except IOError, e:
                self.exceptions.append(e)
                missing_files = []
                for res in resource_list:
                    path = g.resource_manager.get_filename(res)
                    if not os.path.exists(path):
                        missing_files.append(res)
                self.log.exception(' Skipping recipe: ' +
                              g.resource_manager.separator.join(resource_list))
                self.log.exception(
                    ' The following files do not exist: ' + '; '.join(
                        missing_files))
