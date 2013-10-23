from vulcanforge.taskd import task
from vulcanforge.common.model import ForgeGlobals


@task
def test_task(*args, **kwargs):
    fg = ForgeGlobals.query.get()
    fg.taskd_tester = {
        'counter': fg.taskd_tester['counter'] + 1,
        'args': args,
        'kwargs': kwargs
    }
