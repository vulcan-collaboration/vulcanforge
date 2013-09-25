import random
import time
import logging

from vulcanforge.common.model import ForgeGlobals
from .tasks import test_task
from vulcanforge.common.util.model import pymongo_db_collection

LOG = logging.getLogger(__name__)


class TestTaskTimeout(Exception):
    pass


def test_running_taskd(timeout=2):
    i0 = random.randint(1, 1000)
    args = range(i0, i0 + 5)
    kwargs = {str(i): i + 1 for i in args}
    db, coll = pymongo_db_collection(ForgeGlobals)
    fg = coll.find({})[0]
    counter0 = fg['taskd_tester']['counter']
    LOG.info('Running task with counter: {}, args: {}, kwargs: {}'.format(
        counter0, args, kwargs))
    test_task.post(*args, **kwargs)

    counter1 = counter0
    t0 = time.time()
    fg_doc = None
    while counter1 == counter0:
        if time.time() > t0 + timeout:
            raise TestTaskTimeout('Timeout waiting for test task to finish')
        fg_doc = coll.find({})[0]
        counter1 = fg_doc.get('taskd_tester', {}).get('counter', counter0)
    assert counter1 == counter0 + 1
    assert fg_doc['taskd_tester']['args'] == args, \
        fg_doc['taskd_tester']['args']
    assert fg_doc['taskd_tester']['kwargs'] == kwargs, \
        fg_doc['taskd_tester']['kwargs']
