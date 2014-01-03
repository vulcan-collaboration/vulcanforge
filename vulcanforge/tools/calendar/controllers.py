from formencode.validators import String, OneOf, Int
from pylons import app_globals as g, tmpl_context as c
from tg import expose, validate

from vulcanforge.common.controllers.base import BaseController
from vulcanforge.common.validators import (
    TimestampValidator,
    CommaSeparatedEach
)

TEMPLATE_HOME = 'jinja:vulcanforge.tools.calendar:templates/'
DATE_FMT = '%Y-%m-%d'


class CalendarRootController(BaseController):

    def _check_security(self):
        g.security.require_access(c.app, 'read')

    @expose(TEMPLATE_HOME + 'index.html')
    @validate({
        "start": TimestampValidator(),
        "view": OneOf(
            ['month', 'basicWeek', 'basicDay', 'agendaWeek', 'agendaDay'],
            if_empty='month')
    })
    def index(self, start=None, view='month'):
        return {
            "title": c.app.config.options.mount_label,
            "start": start,
            "view": view
        }

    @expose('json')
    @validate({
        "start": TimestampValidator(),
        "end": TimestampValidator(),
        "tools": CommaSeparatedEach(String())
    })
    def get_events(self, start=None, end=None, tools=None, **kw):
        if tools:
            apps = filter(None, [c.project.app_instance(t) for t in tools])
        else:
            apps = [c.project.app_instance(ac) for ac in c.project.app_configs]
        events = []
        for app in apps:
            events.extend(app.get_calendar_events(start, end))
        return {"events": events}
