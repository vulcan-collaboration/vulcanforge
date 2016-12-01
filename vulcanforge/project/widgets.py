import json
from datetime import datetime
import logging

from pylons import tmpl_context as c
import ew as ew_core
import ew.jinja2_ew as ew

from vulcanforge.common import helpers as h
from vulcanforge.common.validators import CommaSeparatedEach
from vulcanforge.common.widgets.util import onready
from vulcanforge.project.model import Project
from vulcanforge.project.validators import ExistingShortnameValidator
from vulcanforge.resources.widgets import JSLink, CSSLink

TEMPLATE_DIR = 'jinja:vulcanforge:project/templates/widgets/'
LOG = logging.getLogger(__name__)


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


class SingleProjectSelect(ew.InputField):
    template = TEMPLATE_DIR + 'project_select.html'
    validator = ExistingShortnameValidator(not_empty=False)
    defaults = dict(
        ew.InputField.defaults,
        name=None,
        value=None,
        show_label=True,
        className='project_select')

    @property
    def query(self):
        return {'deleted':False}

    def from_python(self, value, state=None):
        if not isinstance(value, basestring) and hasattr(value, 'shortname'):
            value = value.shortname
        return value

    def _format_project(self, p):
        return {
            'label': p.name,
            'desc': h.truncate(p.description, 42),
            'value': p.shortname
        }

    def options(self):
        return [self._format_project(p) for p in Project.query.find(self.query)
                if p.is_real()]

    def resources(self):
        for r in ew.InputField.resources(self):
            yield r
        yield onready('''
            var data = %s,
                $input;
            $input = $('input.project_select').
                autocomplete({
                    source: data,
                    autoFocus: true,
                    minLength: 0,
                    delay: 10
                }).
                focus(function(){ $(this).autocomplete('search', ''); }).
                click(function(){ $(this).autocomplete('search', ''); });
            if ($input.length) {
                $input.data("ui-autocomplete")._renderItem = function(ul, item) {
                    return $("<li></li>").
                        data("ui-autocomplete-item", item).
                        append("<a><strong>" + item.label + "</strong><br>" + item.desc + "</a>").
                        appendTo(ul);
                };
            }
            ''' % json.dumps(self.options()))


class MultiProjectSelect(SingleProjectSelect):

    validator = CommaSeparatedEach(
        ExistingShortnameValidator(not_empty=False),
        strip=True,
        filter_empty=True)

    def __init__(self, **kw):
        super(MultiProjectSelect, self).__init__(**kw)
        if not isinstance(self.value, list):
            self.value = [self.value]

    def from_python(self, value, state=None):
        LOG.info(value)
        if value is None:
            value = ''
        if not isinstance(value, basestring):
            values = []
            for p in value:
                p = super(MultiProjectSelect, self).from_python(p, state)
                values.append(p)
            value = ', '.join(values)
        if value and not value.strip().endswith(','):
            value += ', '
        return value

    def resources(self):
        for r in ew.InputField.resources(self):
            yield r
        yield JSLink('js/vf_form.js')
        yield onready('''
            var data = %s,
                $input;
            $input = $('input.project_select').
                multicomplete({
                    source: data,
                    autoFocus: true,
                    minLength: 0,
                    delay: 10
                }).
                focus(function(){$(this).multicomplete('search','');}).
                click(function(){$(this).multicomplete('search','');});
            if ($input.length) {
                $input.data( "vf-multicomplete" )._renderItem = function( ul, item ) {
                    return $( "<li></li>" ).
                        data( "vf-multicomplete-item", item ).
                        append( "<a><strong>" + item.label + "</strong><br>" + item.desc + "</a>" ).
                        appendTo( ul );
                };
            }
            ''' % json.dumps(self.options()))


class ProjectUserSelect(ew.InputField):
    template = TEMPLATE_DIR + 'project_user_select.html'
    defaults = dict(
        ew.InputField.defaults,
        name=None,
        value=None,
        show_label=True,
        className='project_user_select')

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
                $input.data( "ui-autocomplete" )._renderItem = function( ul, item ) {
                    return $( "<li></li>" ).
                        data( "ui-autocomplete-item", item ).
                        append( "<a><strong>" + item.label + "</strong><br>" + item.desc + "</a>" ).
                        appendTo( ul );
                };
            }
            ''' % json.dumps([dict(label=u.display_name, desc=u.username,
            value=u.username) for u in c.project.users()]))


class MultiProjectUserSelect(ProjectUserSelect):
    template = TEMPLATE_DIR + 'multi_project_user_select.html'
    defaults = dict(
        ProjectUserSelect.defaults,
        className='multi_project_user_select')

    def from_python(self, value, state=None):
        if value is None:
            value = ''
        if not isinstance(value, basestring):
            value = ', '.join(u.username for u in value)
        return value

    def resources(self):
        for r in ew.InputField.resources(self):
            yield r
        yield JSLink('js/vf_form.js')
        yield onready('''
            var data = %s,
                $input;
            $input = $('input.multi_project_user_select').
                multicomplete({
                    source: data,
                    autoFocus: true,
                    minLength: 0,
                    delay: 10
                }).
                focus(function(){$(this).multicomplete('search','');}).
                click(function(){$(this).multicomplete('search','');});
            if ($input.length) {
                $input.data( "vf-multicomplete" )._renderItem = function( ul, item ) {
                    return $( "<li></li>" ).
                        data( "vf-multicomplete-item", item ).
                        append( "<a><strong>" + item.label + "</strong><br>" + item.desc + "</a>" ).
                        appendTo( ul );
                };
            }
            ''' % json.dumps([dict(label=u.display_name, desc=u.username,
            value=u.username) for u in c.project.users()]))


class ProjectIconField(ew.FileField):
    template = 'jinja:vulcanforge:common/templates/form/project-icon-field.html'
