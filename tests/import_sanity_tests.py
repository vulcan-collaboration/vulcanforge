# -*- coding: utf-8 -*-
"""
import_sanity_tests

@summary: Validates that all modules and packages inside vulcanforge import
correctly. Uses nosetest test_walk_modules method for dynamic test generation.

"""
import pkgutil
import logging
from mock import Mock

from nose import with_setup
import pylons
import paste


LOG = logging.getLogger(__name__)
REGISTRY = None


def _test_import(name):
    try:
        return __import__(name)
    except:
        msg = "Cannot import {}".format(name)
        LOG.exception(msg)
        raise AssertionError(msg)


def _with_description(method, description):
    def wrapped(*args, **kwargs):
        return method(*args, **kwargs)
    wrapped.description = description
    return wrapped


def _setup():
    global REGISTRY
    # TODO: use Globals() instead of Mock() when app_globals is importable
    #app_globals = __import__('vulcanforge.config.app_globals')
    mock_context = Mock()
    mock_context.app = Mock()
    mock_context.app.__version__ = '0.0'
    REGISTRY = paste.registry.Registry()
    REGISTRY.prepare()
    REGISTRY.register(pylons.tmpl_context, mock_context)
    REGISTRY.register(pylons.app_globals, Mock())


def _teardown():
    global REGISTRY
    REGISTRY.cleanup()


def test_walk_modules():
    root_pkg = _test_import('vulcanforge')
    pkg_walker = pkgutil.walk_packages(root_pkg.__path__,
                                       root_pkg.__name__+'.')
    for module_loader, name, is_pkg in pkg_walker:
        test_method = _test_import
        test_method = _with_description(test_method, "import {}".format(name))
        test_method = with_setup(_setup, _teardown)(test_method)
        yield test_method, name
