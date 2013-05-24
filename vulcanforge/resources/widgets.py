import logging
from urllib import urlencode

from webob import exc
from webhelpers.html import literal
from pylons import app_globals as g
import ew
from ew.utils import LazyProperty, push_context
from ew.core import widget_context
from ew.fields import FieldWidget
from ew.render import Snippet
from ew.jinja2_ew import BOOLEAN_ATTRS
from jinja2 import escape
import jsmin
import cssmin

LOG = logging.getLogger(__name__)


class _Jinja2Widget(FieldWidget):

    def _escape(self, s):
        try:
            return s.__html__()
        except:
            pass
        if isinstance(s, str):
            return escape(unicode(s, 'utf-8'))
        else:
            return escape(s)

    def _attr(self, k, v):
        if k.lower() in BOOLEAN_ATTRS:
            return self._escape(k)
        else:
            return '%s="%s"' % (
                self._escape(k), self._escape(v))

    def j2_attrs(self, *attrdicts):
        attrdict={}
        for ad in attrdicts:
            if ad:
                attrdict.update(ad)
        result = [
        self._attr(k,v)
        for k,v in sorted(attrdict.items())
        if v is not None ]
        return literal(' '.join(result))


class ResourceHolder(ew.Widget):
    """Simple widget that does nothing but hold resources"""

    def __init__(self, *resources):
        self._resources = resources

    def resources(self):
        return self._resources


class Resource(object):

    def __init__(self, scope, compress=True):
        self.scope = scope
        self.compress = compress
        self.manager = None
        self.widget = None

    def display(self):
        return self.widget.display()

    @classmethod
    def compressed(cls, manager, resources):
        return resources


class ResourceLink(Resource):
    file_type=None

    def __init__(self, url, scope, compress):
        self._url = url
        super(ResourceLink, self).__init__(scope, compress)

    def url(self):
        return self.manager.absurl(self._url)

    def __repr__(self): # pragma no cover
        return '<%s %s>' % (self.__class__.__name__, self._url)

    def __hash__(self):
        return hash(self._url)

    def __eq__(self, o):
        return (self.__class__ == o.__class__
                and self._url == o._url)

    @classmethod
    def compressed(cls, manager, resources):
        rel_hrefs = [r.url()[len(manager.url_base):] for r in resources]
        try:
            file_hash = manager.write_slim_file(cls.file_type, rel_hrefs)
        except Exception:
            LOG.exception('Error writing compressed resource')
            raise exc.HTTPNotFound
        query = urlencode([('href', file_hash)])
        result = cls('%s_slim/%s?%s' % (
            manager.url_base,
            cls.file_type,
            query))
        result.manager = manager
        yield result


class JSLink(ResourceLink):
    file_type='js'
    class WidgetClass(_Jinja2Widget):
        template=Snippet('<script type="text/javascript" src="{{widget.href}}"></script>',
            'jinja2')

    def __init__(self, url, scope='page', compress=True):
        super(JSLink, self).__init__(url, scope, compress)
        del self.widget

    @LazyProperty
    def widget(self):
        return self.WidgetClass(href=self.url())


class CSSLink(ResourceLink):
    file_type='css'
    class WidgetClass(_Jinja2Widget):
        template=Snippet('''<link rel="stylesheet"
                type="text/css"
                href="{{widget.href}}"
                {{widget.j2_attrs(widget.attrs)}}>''', 'jinja2')

    def __init__(self, url, scope='page', compress=True, **attrs):
        super(CSSLink, self).__init__(url, scope, compress)
        self.attrs = attrs
        del self.widget

    @LazyProperty
    def widget(self):
        return self.WidgetClass(href=self.url(), attrs=self.attrs)


class ResourceScript(Resource):
    file_type=None

    def __init__(self, text, scope, compress):
        self.text = text
        super(ResourceScript, self).__init__(scope, compress)

    def __hash__(self):
        return (hash(self.text)
                + hash(self.compress))

    def __eq__(self, o):
        return (self.__class__ == o.__class__
                and self.text == o.text
                and self.compress == o.compress)

    @classmethod
    def compressed(cls, manager, resources):
        text = '\n'.join(r.text for r in resources)
        yield cls(text)


class JSScript(ResourceScript):
    file_type='js'
    class WidgetClass(_Jinja2Widget):
        template=Snippet(
            '<script type="text/javascript">{{widget.text}}</script>',
            'jinja2')

    def __init__(self, text, scope='page', compress=True):
        super(JSScript, self).__init__(text, scope, compress)
        del self.widget

    @LazyProperty
    def widget(self):
        return self.WidgetClass(text=self.text)

    @classmethod
    def compressed(cls, manager, resources):
        text = '\n'.join(r.text for r in resources)
        text = jsmin.jsmin(text)
        yield cls(text)


class CSSScript(ResourceScript):
    file_type='css'
    class WidgetClass(_Jinja2Widget):
        template=Snippet('<style>{{widget.text}}</style>', 'jinja2')

    def __init__(self, text):
        super(CSSScript, self).__init__(text, 'page', True)
        del self.widget

    @LazyProperty
    def widget(self):
        return self.WidgetClass(text=self.text)

    @classmethod
    def compressed(cls, manager, resources):
        text = '\n'.join(r.text for r in resources)
        text = cssmin.cssmin(text)
        yield cls(text)


class Widget(ew.Widget):

    js_template = None

    def display(self, **kw):
        context = self.prepare_context(kw)
        if self.js_template:
            with push_context(widget_context, widget=self):
                js_text = Snippet(self.js_template, 'jinja2')(context)
            g.resource_manager.register_js_snippet(js_text)
        return ew.Widget.display(self, **kw)
