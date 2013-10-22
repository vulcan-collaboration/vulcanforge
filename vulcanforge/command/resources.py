import datetime

from base import Command
from vulcanforge.resources.stage import StaticResourceStager


class StageStaticResources(Command):
    min_args = 1
    max_args = 3
    usage = '<ini file>'
    summary = '''
    Copy images and compile JS and CSS resources into the build folder
    '''
    parser = Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        start = datetime.datetime.now()
        stager = StaticResourceStager(log=self.log)

        self.log.info('Copying images')
        stager.stage_images()

        self.log.info('Combining JS and CSS based on recipes')
        stager.stage_css_js()

        self.log.info('Staging resources duration: %s',
                      datetime.datetime.now() - start)

        if stager.exceptions:
            self.return_code = 1
            self.log.warn('Finished staging resources with exceptions.')
        else:
            self.log.info('Finished staging resources without exception.')
