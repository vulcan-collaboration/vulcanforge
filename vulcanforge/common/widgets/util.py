# -*- coding: utf-8 -*-
from webhelpers import paginate
from tg import request, url

from vulcanforge.resources.widgets import JSScript, JSLink, CSSLink, Widget

TEMPLATE_DIR = 'jinja:vulcanforge:common/templates/widgets/'


def onready(text):
    return JSScript('$(function () {%s});' % text)


class PageList(Widget):
    _number = 0

    template = TEMPLATE_DIR + 'page_list.html'
    js_template = '''
    $vf.afterInit(function() {
            var pager = new $vf.Pager();
            pager.containerE = $('#{{widget_id}}');
            pager.configure({
                maxLength: 13,
                itemCount: {{count}},
                itemPerPage: {{limit}},
                currentPage: {{page}},
                onGotoPage: function(n) {
                    $.redirect( { page : n }, true);
                }
            });
            pager.render();
        }, []);'''

    defaults = dict(
        Widget.defaults,
        name=None,
        limit=None,
        count=0,
        page=0,
        show_label=False)

    def prepare_context(self, context):
        prepared = super(PageList, self).prepare_context(context)
        prepared['widget_id'] = "pagerContainer_%s" % self.id
        return prepared

    def paginator(self, count, page, limit, zero_based_pages=True):
        count = int(count)
        page = int(page)
        limit = int(limit)
        page_offset = 1 if zero_based_pages else 0
        limit = 10 if limit is None else limit

        def page_url(page):
            params = request.GET.copy()
            params['page'] = page - page_offset
            return url(request.path, params)

        return paginate.Page(range(count), page + page_offset, int(limit),
                             url=page_url)

    def resources(self):
        yield CSSLink('css/page_list.css')

    @property
    def url_params(self, **kw):
        url_params = dict()
        for k, v in request.params.iteritems():
            if k not in ['limit', 'count', 'page']:
                url_params[k] = v
        return url_params

    @property
    def page_url_prefix(self):
        params = request.GET.copy()
        if 'page' in params:
            del params['page']
        base_url = url(request.path, params)
        if base_url == request.path:
            base_url += '?'
        else:
            base_url += '&'
        return base_url

    @property
    def id(self):
        return self._number

    def display(self, **kw):
        self._number += 1
        return super(PageList, self).display(**kw)


class PageSize(Widget):
    template = TEMPLATE_DIR + 'page_size.html'
    defaults = dict(
        Widget.defaults,
        limit=None,
        name=None,
        count=0,
        show_label=False)

    @property
    def url_params(self, **kw):
        url_params = dict()
        for k, v in request.params.iteritems():
            if k not in ['limit', 'count', 'page']:
                url_params[k] = v
        return url_params

    def resources(self):
        yield onready('''
            $('select.results_per_page').change(function () {
                this.form.submit();});''')


class LightboxWidget(Widget):
    template = TEMPLATE_DIR + 'lightbox.html'
    defaults = dict(
        name=None,
        trigger=None,
        content='')

    def resources(self):
        yield JSLink('js/lib/jquery/jquery.lightbox_me.js')
        yield onready('''
            var $lightbox = $('#lightbox_%s');
            var $trigger = $('%s');
            $trigger.bind('click', function(e) {
                $lightbox.lightbox_me();
                return false;
            });
            $($lightbox).delegate('.close', 'click', function(e) {
                $lightbox.trigger('close');
                return false;
            });
        ''' % (self.name, self.trigger))
