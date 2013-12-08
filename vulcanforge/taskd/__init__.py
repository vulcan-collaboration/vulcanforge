from ming.odm.odmsession import ThreadLocalODMSession
from .model import MonQTask
from vulcanforge.common.util.filesystem import import_object
from vulcanforge.taskd.exceptions import TaskdException


def task(func):
    """Decorator to add some methods to task functions"""
    def post(*args, **kwargs):
        return MonQTask.post(func, args, kwargs)
    func.post = post
    return func


class BaseMethodTask(object):
    """For calling methods of objects asynchronously"""
    decorator = None

    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return self.decorator(self.func, instance)


class BaseTaskDecorator(object):
    task_runner = None

    def __init__(self, func, instance):
        self.func = func
        self.instance = instance
        super(BaseTaskDecorator, self).__init__()

    def get_instance_args(self):
        """Used to instantiate the instance"""
        return []

    def get_instance_kwargs(self):
        return {}

    def post(self, *args, **kwargs):
        method_path = '{module}:{cls}.{method}'.format(
            module=self.instance.__class__.__module__,
            cls=self.instance.__class__.__name__,
            method=self.func.__name__
        )
        args = [method_path] + self.get_instance_args() + list(args)
        task_kwargs = self.get_instance_kwargs()
        task_kwargs.update(kwargs)
        return MonQTask.post(self.task_runner, args, task_kwargs)

    def __call__(self, *args, **kwargs):
        return self.func(self.instance, *args, **kwargs)


def _run_model_task(method_path, _id, *args, **kwargs):
    """this is only run as a task

    It loads the corresponding model instance and runs the appropriate method

    """
    path, method = method_path.rsplit('.', 1)
    cls = import_object(path)
    inst = cls.query.get(_id=_id)
    if inst is None:
        raise TaskdException("Instance of {} not found with _id {}".format(
            path, _id))
    func = getattr(inst, method)
    resp = func(*args, **kwargs)
    ThreadLocalODMSession.flush_all()
    return resp


class _model_task_decorator(BaseTaskDecorator):
    """model task methods are decorated dynamically"""
    task_runner = _run_model_task

    def get_instance_args(self):
        return [self.instance._id]


class model_task(BaseMethodTask):
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
    decorator = _model_task_decorator
