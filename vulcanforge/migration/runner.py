import logging
import sys
import os

from ming.odm.odmsession import ThreadLocalODMSession
from tg import config
from vulcanforge.migration.base import BaseMigration
from vulcanforge.migration.model import MigrationLog

LOG = logging.getLogger(__name__)


class MigrationRunner(object):

    @property
    def _default_modules(self):
        return [
            config['package'].__name__ + '.migrations',
            'vulcanforge.migrations'
        ]

    def _load_migrations_from_dir(self, module):
        for fname in sorted(os.listdir(module.__path__[0])):
            if os.path.isdir(fname):
                module_name = module.__name__ + '.' + fname
                try:
                    __import__(module_name)
                except ImportError:
                    continue
                sub_module = sys.modules[module_name]
                for mig in self._load_migrations_from_dir(sub_module):
                    yield mig
            elif fname.endswith('.py') and not fname == '__init__.py':
                module_name = module.__name__ + '.' + fname[:-3]
                __import__(module_name)
                sub_module = sys.modules[module_name]
                for mig in self._load_migrations_from_file(sub_module):
                    yield mig

    def _load_migrations_from_file(self, module):
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, BaseMigration) and \
                    obj.__module__ == module.__name__:
                yield obj

    def load_migrations(self, module_names=None):
        if module_names is None:
            module_names = self._default_modules
        for module_name in module_names:
            __import__(module_name)
            module = sys.modules[module_name]
            if hasattr(module, '__path__') and os.path.isdir(
                    module.__path__[0]):
                for mig in self._load_migrations_from_dir(module):
                    yield mig
            else:
                for mig in self._load_migrations_from_file(module):
                    yield mig

    def _mig_cls_needs_running(self, mig_cls, erroneous=True):
        old_log = MigrationLog.get_from_migration(mig_cls)
        if old_log and (not erroneous or old_log.status != 'error'):
            return False
        return True

    def run_migrations(self, module_names=None, all_migrations=False,
                       erroneous=True, continue_on_error=False):
        for mig_cls in self.load_migrations(module_names):
            if not all_migrations and not self._mig_cls_needs_running(
                    mig_cls, erroneous):
                continue

            mig = mig_cls()
            if mig.is_needed():
                LOG.info('Running %s', str(mig.get_name()))
                try:
                    mig.full_run()
                except Exception:
                    if continue_on_error:
                        LOG.exception('Error running %s', mig)
                    else:
                        raise
            else:
                mig.miglog.status = 'unnecessary'
            ThreadLocalODMSession.flush_all()
            ThreadLocalODMSession.close_all()
