
from .model import MonQTask
from vulcanforge.common.util.filesystem import import_object
from vulcanforge.taskd.exceptions import TaskdException


def task(func):
    """Decorator to add some methods to task functions"""
    def post(*args, **kwargs):
        return MonQTask.post(func, args, kwargs)
    func.post = post
    return func


class model_task(object):
    """
    Decorator to allow ming MappedClass instances to behave as tasks. Functions
    the same as the task decorator, but called on instance methods.

    Example:

    class MyMappedClass(MappedClass):
        ...

        @model_task
        def my_method(self):
            ...


    mc1 = MyMappedClass()
    mc1.my_method()  # called synchronously
    mc1.my_method.post()  # called asynchronously

    """
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return _model_task_decorator(self.func, instance)


class _model_task_decorator(object):
    """model task methods are decorated dynamically"""

    def __init__(self, func, instance):
        self.func = func
        self.instance = instance
        super(_model_task_decorator, self).__init__()

    def post(self, *args, **kwargs):
        method_path = '{module}:{cls}.{method}'.format(
            module=self.instance.__class__.__module__,
            cls=self.instance.__class__.__name__,
            method=self.func.__name__
        )
        args = [method_path, self.instance._id] + list(args)
        return MonQTask.post(_run_model_task, args, kwargs)

    def __call__(self, *args, **kwargs):
        return self.func(self.instance, *args, **kwargs)


def _run_model_task(method_path, _id, *args, **kwargs):
    path, method = method_path.rsplit('.', 1)
    cls = import_object(path)
    inst = cls.query.get(_id=_id)
    if inst is None:
        raise TaskdException("Instance of {} not found with _id {}".format(
            path, _id))
    func = getattr(inst, method)
    return func(*args, **kwargs)
