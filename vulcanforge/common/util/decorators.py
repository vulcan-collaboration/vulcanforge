"""
Utilities for working with exceptions, not exceptions themselves

"""


class exceptionless(object):
    """
    Decorator making the decorated function return 'error_result' on any
    exceptions rather than propagating exceptions up the stack

    """
    def __init__(self, error_result, log=None):
        self.error_result = error_result
        self.log = log

    def __call__(self, fun):
        fname = 'exceptionless(%s)' % fun.__name__

        def inner(*args, **kwargs):
            try:
                return fun(*args, **kwargs)
            except Exception as e:
                if self.log:
                    self.log.exception('Error calling %s %s' % (fname, str(e)))
                return self.error_result

        inner.__name__ = fname
        return inner
