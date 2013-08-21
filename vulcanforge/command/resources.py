import logging
import os
import shutil
import datetime

from pylons import app_globals as g
from vulcanforge.common.util.filesystem import mkdir_p
from vulcanforge.resources.manager import RECIPE_FILE

from base import Command

LOG = logging.getLogger(__name__)


class StageStaticResources(Command):
    min_args = 1
    max_args = 3
    usage = '<ini file> <speed_up> <offset>'
    summary = '''
    Copy images and compile JS and CSS resources into the build folder
    '''
    parser = Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        start = datetime.datetime.now()

        try:
            speed_up = int(self.args[1])
            offset = int(self.args[2])
        except:
            speed_up = 1
            offset = 0

        if offset == 0:
            print 'Copying images'
            for (namespace, directories) in g.resource_manager.paths:
                for directory in directories[::-1]:
                    destination_dir = os.path.join(
                        g.resource_manager.build_dir, namespace)
                    self.copy_files(directory, destination_dir)

        print 'Combining JS and CSS based on recipes'
        recipe_path = os.path.join(
            g.resource_manager.static_resources_dir, RECIPE_FILE)
        if not os.path.exists(recipe_path):
            with open(recipe_path, 'w') as fp:
                fp.write('')
        recipe_file = open(recipe_path, 'r')
        recipe_list = [line for line in recipe_file]
        recipe_file.close()
        i = 0
        for recipe in recipe_list:
            if i % speed_up == offset:
                if '.js' in recipe:
                    file_type = 'js'
                else:
                    file_type = 'css'
                resource_list = recipe.split('\n')[0].split(';')
                try:
                    g.resource_manager.write_slim_file(
                        file_type, resource_list)
                except IOError:
                    missing_files = []
                    for res in resource_list:
                        path = g.resource_manager.get_filename(res)
                        if not os.path.exists(path):
                            missing_files.append(res)
                    LOG.warning(
                        ' Skipping recipe: ' + str(recipe.split('\n')[0]))
                    LOG.warning(
                        ' The following files do not exist: ' + '; '.join(
                            missing_files))
            i += 1

        LOG.info('Finished JS and CSS compilation in ' + str(
            datetime.datetime.now() - start))

    def copy_files(self, source_dir, destination_dir):
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
