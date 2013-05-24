
import ew as ew_core

from vulcanforge.common.widgets.util import PageSize, PageList, LightboxWidget
from vulcanforge.resources.widgets import JSLink, CSSLink

TEMPLATE_DIR = 'jinja:vulcanforge.tools.tickets:templates/tracker_widgets/'


class TicketSearchResults(ew_core.SimpleForm):
    template = TEMPLATE_DIR + 'ticket_search_results.html'
    defaults = dict(
        ew_core.SimpleForm.defaults,
        solr_error=None,
        count=None,
        limit=None,
        query=None,
        tickets=None,
        sortable_custom_fields=None,
        page=1,
        sort="ticket_num_i desc",
        columns=None,
        paged=True
    )

    class fields(ew_core.NameList):
        page_list = PageList()
        page_size = PageSize()
        lightbox = LightboxWidget(name='col_list', trigger='#col_menu')

    def prepare_context(self, context):
        result = super(TicketSearchResults, self).prepare_context(context)
        if result['sort'] is None:
            result['sort'] = self.defaults['sort']
        return result

    def resources(self):
        yield JSLink('tracker_js/ticket-list.js')
        yield CSSLink('tracker_css/ticket-list.css')
        for r in super(TicketSearchResults, self).resources():
            yield r


class MassEdit(ew_core.Widget):
    template = TEMPLATE_DIR + 'mass_edit.html'
    defaults = dict(
        ew_core.Widget.defaults,
        count=None,
        limit=None,
        query=None,
        tickets=None,
        page=1,
        sort=None)

    def resources(self):
        yield JSLink('tracker_js/ticket-list.js')


class MassEditForm(ew_core.Widget):
    template = TEMPLATE_DIR + 'mass_edit_form.html'
    defaults = dict(
        ew_core.Widget.defaults,
        globals=None,
        query=None,
        cancel_href=None,
        limit=None,
        sort=None)

    def resources(self):
        yield JSLink('tracker_js/mass-edit.js')
