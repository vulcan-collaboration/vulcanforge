import random
import time

from vulcanforge.common.model import ForgeGlobals
from .tasks import test_task
from vulcanforge.common.util.model import pymongo_db_collection


class TestTaskTimeout(Exception):
    pass


def test_running_taskd(timeout=2):
    i0 = random.randint(1, 1000)
    args = range(i0, i0 + 5)
    kwargs = {str(i): i + 1 for i in args}
    fg = ForgeGlobals.query.get()
    counter0 = fg.taskd_tester['counter']
    test_task.post(*args, **kwargs)
    db, coll = pymongo_db_collection(ForgeGlobals)

    counter1 = counter0
    t0 = time.time()
    fg_doc = None
    while counter1 == counter0:
        if time.time() > t0 + timeout:
            raise TestTaskTimeout('Timeout waiting for test task to finish')
        fg_doc = coll.find({})[0]
        counter1 = fg_doc['taskd_tester']['counter']
    assert counter1 == counter0 + 1
    assert fg_doc['taskd_tester']['args'] == args
    assert fg_doc['taskd_tester']['kwargs'] == kwargs
