"""
Utilities when working with TG Controllers

"""
import os

from tg import request


def get_remainder_path(args, use_ext=True):
    """
    For situations when you want to get the remainder of a request after
    tg is done routing:

    For example, you have a controller mounted at /example:

    class ExampleController(BaseController):
         @expose()
         def my_method(*args, **kwargs):
            path = get_remainder_path(args)

    A request to /example/my_method/path/to/awesomeness.txt
    would route to my_method, and the `path` variable would be computed to be
    "/path/to/awesomeness.txt"

    """
    path = u'/' + u'/'.join([a.decode('utf8') for a in args])
    if use_ext and request.response_ext:
        if not os.path.basename(request.path) == os.path.basename(path):
            path += request.response_ext.decode('utf8')
    return path
