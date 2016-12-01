import urllib
from tg import request
from pylons import tmpl_context as c


def get_resource_path():
    resource_url = request.url
    controller_path = c.app.config.url() + 'content'
    return urllib.unquote(resource_url.split(controller_path)[1].split('?')[0])
