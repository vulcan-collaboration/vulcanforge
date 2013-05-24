
from .model import MonQTask


def task(func):
    """Decorator to add some methods to task functions"""
    def post(*args, **kwargs):
        return MonQTask.post(func, args, kwargs)
    func.post = post
    return func
