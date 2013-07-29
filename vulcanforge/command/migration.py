import logging
import os

from . import base
from vulcanforge.migration.runner import MigrationRunner
from vulcanforge.migration.model import MigrationLog


class CommandMigrationRunner(MigrationRunner):
    def run_migration(self, mig):
        mig.log.setLevel(logging.INFO)
        super(CommandMigrationRunner, self).run_migration(mig)


class MigrationCommand(base.Command):
    min_args = 1
    max_args = None
    usage = '<ini file> [migration modules ...]'
    summary = '''
    Run migration script(s). If no directory/script is specified,
    defaults to migration directories.
    '''
    parser = base.Command.standard_parser(verbose=True)
    parser.add_option(
        '--skip_erroneous', action='store_false', dest='erroneous',
        default=True, help='Skip previous erroneous scripts')
    parser.add_option(
        '--all', action='store_true', dest='all_migrations',
        help='Run all migrations [Instead of only new]')

    def _convert_paths(self, paths):
        converted = []
        for path in paths:
            if path.endswith('.py'):
                path = path[:-3]
            converted.append(path.replace(os.path.sep, '.'))
        return converted

    def command(self):
        self.basic_setup()
        if len(self.args) <= 1:
            migration_modules = None
        else:
            migration_modules = self._convert_paths(self.args[1:])
        MigrationLog.upsert_init()
        runner = CommandMigrationRunner()
        runner.run_migrations(
            migration_modules,
            all_migrations=self.options.all_migrations,
            erroneous=self.options.erroneous)
