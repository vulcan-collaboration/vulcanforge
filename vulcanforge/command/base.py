import os
import sys
import logging
from ming.utils import LazyProperty

from paste.script import command
from paste.deploy import appconfig
from paste.registry import Registry
import pylons
from tg import config

from vulcanforge.auth import credentials
from vulcanforge.auth.model import User
from vulcanforge.auth.security_manager import Credentials
from vulcanforge.common.util.model import close_all_mongo_connections
from vulcanforge.config.ming_config import ming_replicant_configure

from isisforge.config.environment import load_environment

log = None


class EmptyClass(object):
    pass


class Command(command.Command):
    min_args = 0
    max_args = 1
    usage = '[<ini file>]'
    group_name = 'ISISForge'

    @LazyProperty
    def registry(self):
        return Registry()

    @LazyProperty
    def config(self):
        import tg
        return tg.config

    def run(self, args):
        result = command.Command.run(self, args)
        self.cleanup()
        return result

    def basic_setup(self):
        global log
        if self.args:
            # Probably being called from the command line - load the config
            # file
            self.config = conf = appconfig('config:%s' % self.args[0],
                                           relative_to=os.getcwd())
            # Configure logging
            try:
                # ... logging does not understand section#subsection syntax
                logging_config = self.args[0].split('#')[0]
                logging.config.fileConfig(logging_config,
                                          disable_existing_loggers=False)
            except Exception:  # pragma no cover
                print >> sys.stderr, (
                    'Could not configure logging with config file %s' %
                    self.args[0])
            log = logging.getLogger(__name__)
            log.info('Initialize command with config %r', self.args[0])
            load_environment(conf.global_conf, conf.local_conf)
            self.setup_globals()

            ming_replicant_configure(**conf)
            pylons.tmpl_context.user = User.anonymous()
        else:
            # Probably being called from another script (websetup, perhaps?)
            log = logging.getLogger('isisforge.command')
            conf = pylons.config

    def setup_globals(self):
        self.registry.prepare()
        self.registry.register(pylons.tmpl_context, EmptyClass())
        self.registry.register(
            pylons.app_globals, config['pylons.app_globals'])
        self.registry.register(
            credentials,
            Credentials())

    def teardown_globals(self):
        self.registry.cleanup()

    def cleanup(self):
        close_all_mongo_connections()
