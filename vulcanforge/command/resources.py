import logging
import datetime

from base import Command
from vulcanforge.resources.stage import StaticResourceStager

LOG = logging.getLogger(__name__)


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
        stager = StaticResourceStager()

        print 'Copying images'
        stager.stage_images()

        print 'Combining JS and CSS based on recipes'
        stager.stage_css_js()

        LOG.info('Finished JS and CSS compilation in ' + str(
            datetime.datetime.now() - start))
