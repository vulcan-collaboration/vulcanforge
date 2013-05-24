import json
from datetime import datetime

from pylons import tmpl_context as c
import ew as ew_core
import ew.jinja2_ew as ew

from vulcanforge.common import helpers as h
from vulcanforge.common.widgets.util import onready
from vulcanforge.resources.widgets import JSLink, CSSLink

TEMPLATE_DIR = 'jinja:vulcanforge:project/templates/widgets/'


class ProjectWidget(ew_core.Widget):
    def resources(self):
        yield JSLink('project/project-widgets.js')
        yield CSSLink('project/project-widgets.css')


class ProjectSummary(ProjectWidget):
    template = TEMPLATE_DIR + 'project_summary.html'
    defaults = dict(
        ew_core.Widget.defaults,
        project=None,
        display_mode='div')

    def prepare_context(self, context):
        context = super(ProjectSummary, self).prepare_context(context)
        # handle solr results and project items the same way
        project = context['project']

        if isinstance(project, dict):
            reg_time = project.get('registration_time_dt')
            if isinstance(reg_time, basestring):
                reg_time = datetime.strptime(reg_time, "%Y-%m-%dT%H:%M:%SZ")
            context.update({
                'name': project['name_s'],
                'icon_url': project.get('icon_url_s', None),
                'url': project['url_s'],
                'short_description': project.get('short_description_s', None),
                'status': project.get('status', ''),
                'cancel_url': project.get('cancel_url'),
                'cancel_text': project.get('cancel_text', ''),
                'project_since': h.ago(reg_time)
            })
        else:
            context.update({
                'name': project.name,
                'icon_url': project.icon_url,
                'url': project.url(),
                'short_description': project.short_description,
                'status': '',
                'cancel_url': None,
                'project_since': h.ago(project.registration_datetime)
            })

        return context


class ProjectListWidget(ProjectWidget):
    template = TEMPLATE_DIR + 'project_list_widget.html'
    defaults = dict(
        ew_core.Widget.defaults,
        projects=[],
        project_summary=ProjectSummary(tag_type='li'),
        display_mode='list')


class ProjectScreenshots(ProjectWidget):
    template = TEMPLATE_DIR + 'project_screenshots.html'
    defaults = dict(
        ew_core.Widget.defaults,
        project=None,
        edit=False)


class ProjectUserSelect(ew.InputField):
    template = TEMPLATE_DIR + 'project_user_select.html'
    defaults = dict(
        ew.InputField.defaults,
        name=None,
        value=None,
        show_label=True,
        className=None)

    def __init__(self, **kw):
        super(ProjectUserSelect, self).__init__(**kw)
        if not isinstance(self.value, list):
            self.value = [self.value]

    def from_python(self, value, state=None):
        return value

    def resources(self):
        for r in ew.InputField.resources(self):
            yield r
        yield onready('''
            var data = %s,
                $input;
            $input = $('input.project_user_select').
                autocomplete({
                    source: data,
                    autoFocus: true,
                    minLength: 0,
                    delay: 10
                }).
                focus(function(){
                    $(this).autocomplete('search','');
                });
            if ($input.length) {
                $input.data( "autocomplete" )._renderItem = function( ul, item ) {
                    return $( "<li></li>" ).
                        data( "item.autocomplete", item ).
                        append( "<a><strong>" + item.label + "</strong><br>" + item.desc + "</a>" ).
                        appendTo( ul );
                };
            }
            ''' % json.dumps([dict(label=u.display_name, desc=u.username,
            value=u.username) for u in c.project.users()]))


class ProjectIconField(ew.FileField):
    template = 'jinja:vulcanforge:common/templates/form/project-icon-field.html'
