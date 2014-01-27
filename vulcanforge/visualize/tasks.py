from ming.odm import ThreadLocalODMSession

from vulcanforge.common.util.filesystem import import_object
from vulcanforge.taskd import BaseMethodTask, BaseTaskDecorator, TaskdException


def _run_visualizable_task(method_path, lookup_args, *args, **kwargs):
    path, method = method_path.rsplit('.', 1)
    cls = import_object(path)
    inst = cls.find_for_task(*lookup_args)
    if inst is None:
        raise TaskdException("Instance of {} not found with _id {}".format(
            path, lookup_args))
    func = getattr(inst, method)
    resp = func(*args, **kwargs)
    ThreadLocalODMSession.flush_all()
    return resp


class _visualizable_task_decorator(BaseTaskDecorator):
    task_runner = _run_visualizable_task

    def get_instance_args(self):
        return [self.instance.get_task_lookup_args()]


class visualizable_task(BaseMethodTask):
    decorator = _visualizable_task_decorator
