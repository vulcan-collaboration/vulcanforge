import json
import logging
import string
import random

from formencode import validators as fev
from pylons import tmpl_context as c, app_globals as g
from tg import config
import ew as ew_core
import ew.jinja2_ew as ew
from ew.render import File

from vulcanforge.common.widgets.util import onready
from vulcanforge.resources.widgets import JSLink, CSSLink, Widget
from vulcanforge.visualize.widgets.visualize import ThumbnailVisualizer, IFrame
from vulcanforge.visualize.model import Visualizer
from vulcanforge.visualize.util import render_fs_urls

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:common/templates/form/'
GENSHI_DIR = 'genshi:vulcanforge.common.templates.form.'


class LabelEdit(ew.TextField):
    template = TEMPLATE_DIR + "artifact-labels-field.html"
    defaults = dict(
        ew.TextField.defaults,
        name=None,
        value=None,
        css_class='artifact-labels-field',
        show_label=True,
        placeholder=None,
        available_tags=None)

    def to_python(self, value, state=None):
        if isinstance(value, basestring):
            value = super(LabelEdit, self).to_python(value, state)
            value = [v.strip() for v in value.split(',') if v.strip()]
        return value

    def from_python(self, value, state):
        if not value:
            return ""
        if not isinstance(value, basestring):
            value = ', '.join(value)
            value = super(LabelEdit, self).from_python(value, state)
        return value

    def prepare_context(self, context):
        context = super(LabelEdit, self).prepare_context(context)
        try:
            project = c.project
        except AttributeError:
            raise AttributeError(
                "LabelEdit must be used in the context of a project")
        labels = project.get_labels()
        context.update(available_tags=json.dumps(labels))
        return context

    def resources(self):
        for r in super(LabelEdit, self).resources():
            yield r
        yield JSLink('js/lib/jquery/tag-it.js')
        yield CSSLink('css/jquery.tagit.css')
        yield JSLink('artifact/artifact-labels-field.js')
        yield CSSLink('artifact/artifact-labels-field.css')


class SetPasswordField(ew.PasswordField):
    template = TEMPLATE_DIR + 'password_field.html'
    defaults = dict(
        ew.PasswordField.defaults,
        requirements_hidden=False
    )

    def prepare_context(self, context):
        return dict(
            super(SetPasswordField, self).prepare_context(context),
            min_length=int(config.get('auth.pw.min_length', 10))
        )


class Attachment(Widget):
    template = TEMPLATE_DIR + 'attachment.html'
    js_template = '''
    $(document).ready(function(){
        $('#more-{{value._id}}').visualizerOptions({
            visualizerLinks: {{visualizer_links|safe}},
            linksAlign: "left top-6",
            targetAlign: "left bottom"
        });
    });'''
    defaults = dict(
        value=None,
        name=None,
        thumb_widget=ThumbnailVisualizer(),
        delete_url=None,
    )
    params = ['value']

    def resources(self):
        yield JSLink('visualize/visualizer.js')
        yield JSLink('assets/attachment/attachment.js')

    def prepare_context(self, context):
        new_context = super(Attachment, self).prepare_context(context)
        new_context['render_fs_urls'] = render_fs_urls
        return new_context

    def get_mode(self, *args, **kw):
        return 'thumb'

    def display(self, value=None, **kw):
        visualizer_links = render_fs_urls(
            value.url(), dl_too=True, size=value.length)
        return super(Attachment, self).display(
            value=value,
            visualizer_links=visualizer_links,
            **kw
        )


class AttachmentList(ew_core.Widget):
    template = TEMPLATE_DIR + 'attachment_list.html'
    defaults = dict(
        ew_core.Widget.defaults,
        attachments=None,
        context_id=None
    )

    widgets = dict(
        attachment=Attachment()
    )

    def resources(self):
        for name, widget in self.widgets.iteritems():
            for r in widget.resources():
                yield r

    def prepare_context(self, context):
        new_context = super(AttachmentList, self).prepare_context(context)
        new_context['widgets'] = self.widgets
        return new_context

    def has_del_permission(self, value):
        return g.security.has_access(
            value, value.app_config.reference_opts['create_perm'])

    def get_delete_url(self, att):
        return att.local_url()

    def display(self, value=None, extraCSS=None, **kw):
        attachments = kw.pop('attachments', None)
        if attachments is None and hasattr(self, 'attachments'):
            attachments = self.attachments
        if attachments is None and hasattr(value, 'attachments'):
            attachments = value.attachments
        return ew_core.Widget.display(
            self,
            value=value,
            attachments=attachments,
            extraCSS=extraCSS or '',
            has_del_permission=self.has_del_permission(value),
            **kw
        )


class AttachmentAdd(ew.FileField):
    template = TEMPLATE_DIR + 'attachment_add.html'
    defaults = dict(
        ew.InputField.defaults,
        action=None,
        name=None,
        collapsed=True,
        standalone=False
    )

    def resources(self):
        for r in super(AttachmentAdd, self).resources():
            yield r
        yield JSLink('assets/attachment/attachment_add.js')


class RepeatedAttachmentField(ew.RepeatedField):
    template = (TEMPLATE_DIR + ''
                'repeated_attachment_field.html')
    defaults = dict(
        ew.RepeatedField.defaults,
        css_class="vf-repeated-attachment-field",
        repetitions=1
    )
    field = ew.FileField(css_class="vf-repeated-attachment-field-input")

    def resources(self):
        for r in super(RepeatedAttachmentField, self).resources():
            yield r
        yield JSLink('assets/attachment/repeated_attachment_field.js')
        yield CSSLink('assets/attachment/repeated_attachment_field.css')


class SubmitButton(ew.SubmitButton):
    attrs = {'class': 'ui-state-default ui-button ui-button-text'}


class AutoResizeTextarea(ew.TextArea):
    defaults = dict(
        ew.TextArea.defaults,
        name=None,
        value=None,
        css_class='auto_resize')

    def resources(self):
        yield JSLink('js/lib/jquery/jquery.elastic.js')
        yield JSLink('assets/textarea/auto_resize_textarea.js')


class MarkdownEdit(ew.TextArea):
    validator = fev.UnicodeString()
    template = TEMPLATE_DIR + 'markdown_edit.html'
    defaults = dict(
        ew.TextArea.defaults,
        name=None,
        value=None,
        show_label=True,
        markdown_project=None,
        markdown_app=None,
        class_name='markdown-edit',
        attachment_context_id=None
    )

    def from_python(self, value, state=None):
        return value

    def prepare_context(self, *args, **kw):
        context = super(MarkdownEdit, self).prepare_context(*args, **kw)
        context['context_id'] = ''.join(random.sample(string.ascii_uppercase, 8))
        try:
            context['markdown_neighborhood'] = c.project.neighborhood.name
        except AttributeError:
            pass
        try:
            context['markdown_project'] = c.project.shortname
        except AttributeError:
            pass
        try:
            context['markdown_app'] = c.app.config.options.mount_point
        except AttributeError:
            pass
        return context

    def resources(self):
        for r in super(MarkdownEdit, self).resources():
            yield r
        yield JSLink('js/lib/jquery/jquery.lightbox_me.js')
        yield JSLink('js/lib/jquery/jquery.textarea.js')
        yield CSSLink('js/lib/google-code-prettify/prettify.css')
        yield JSLink('js/lib/google-code-prettify/prettify.js')
        yield JSLink('js/lib/pagedown/Markdown.Converter.js')
        yield JSLink('js/lib/pagedown/Markdown.Sanitizer.js')
        yield JSLink('js/lib/pagedown/Markdown.Editor.js')
        yield JSLink('assets/markdown/markdown_edit.js')


class FileChooser(ew.InputField):
    template = TEMPLATE_DIR + 'file_chooser.html'
    validator = fev.FieldStorageUploadConverter()
    defaults = dict(ew.InputField.defaults,
                    name=None)

    def resources(self):
        for r in super(FileChooser, self).resources():
            yield r
        yield JSLink('js/lib/jquery/jquery.file_chooser.js')
        yield onready('''
            var num_files = 0;
            var chooser = $('input.file_chooser').file();
            chooser.choose(function (e, input) {
                var holder = document.createElement('div');
                holder.style.clear = 'both';
                e.target.parentNode.appendChild(holder);
                $(holder).append(input.val());
                $(holder).append(input);
                input.attr('name', e.target.id + '-' + num_files);
                input.hide();
                ++num_files;
                var delete_link = document.createElement('a');
                delete_link.className = 'btn';
                var icon = document.createElement('b');
                icon.className = 'ico delete';
                delete_link.appendChild(icon);
                $(delete_link).click(function () {
                    this.parentNode.parentNode.removeChild(this.parentNode);
                });
                $(holder).append(delete_link);
            });''')


class JQueryMixin(object):
    js_widget_name = None
    js_plugin_file = None
    js_params = ['container_cls']
    container_cls = 'container'

    def resources(self):
        for r in super(JQueryMixin, self).resources():
            yield r
        if self.js_plugin_file is not None:
            yield self.js_plugin_file
        opts = dict(
            (k, getattr(self, k))
            for k in self.js_params)
        yield onready('''
$(document).bind('clone', function () {
    $('.%s').%s(%s); });
$(document).trigger('clone');
            ''' % (self.container_cls, self.js_widget_name, json.dumps(opts)))


class SortableRepeatedMixin(JQueryMixin):
    js_widget_name = 'SortableRepeatedField'
    js_plugin_file = JSLink('js/lib/sortable_repeated_field.js',
                            scope='page')
    js_params = JQueryMixin.js_params+[
        'field_cls',
        'flist_cls',
        'stub_cls',
        'msg_cls',
    ]
    defaults = dict(
        container_cls='sortable-repeated-field',
        field_cls='sortable-field',
        flist_cls='sortable-field-list',
        stub_cls='sortable-field-stub',
        msg_cls='sortable-field-message',
        empty_msg='No fields have been defined',
        nonempty_msg='Drag and drop the fields to reorder',
        repetitions=0)
    button = ew.InputField(
        css_class='add', field_type='button', value='New Field')


class SortableRepeatedField(SortableRepeatedMixin, ew.RepeatedField):
    template = GENSHI_DIR + 'sortable_repeated_field'
    defaults = dict(
        ew.RepeatedField.defaults,
        **SortableRepeatedMixin.defaults)


class SortableTable(SortableRepeatedMixin, ew.TableField):
    template = GENSHI_DIR + 'sortable_table'
    defaults = dict(
        ew.TableField.defaults,
        **SortableRepeatedMixin.defaults)


class StateField(JQueryMixin, ew.CompoundField):
    template = GENSHI_DIR + 'state_field'
    js_widget_name = 'StateField'
    js_plugin_file = JSLink('js/lib/state_field.js')
    js_params = JQueryMixin.js_params+[
        'selector_cls',
        'field_cls',
    ]
    defaults = dict(
        ew.CompoundField.defaults,
        js_params=js_params,
        container_cls='state-field-container',
        selector_cls='state-field-selector',
        field_cls='state-field',
        show_label=False,
        selector=None,
        states={},
    )

    @property
    def fields(self):
        return [self.selector]+self.states.values()


class DateField(JQueryMixin, ew.TextField):
    js_widget_name = 'datepicker'
    js_params = JQueryMixin.js_params
    container_cls = 'ui-date-field'
    defaults = dict(
        ew.TextField.defaults,
        container_cls='ui-date-field',
        css_class='ui-date-field short')

    def resources(self):
        for r in super(DateField, self).resources():
            yield r


class CompoundField(ew.CompoundField):
    template = TEMPLATE_DIR + 'compound_field.html'


class FieldCluster(ew.CompoundField):
    template = GENSHI_DIR + 'field_cluster'


class AdminField(ew.InputField):
    """Field with the correct layout/etc for an admin page"""
    template = TEMPLATE_DIR + 'admin_field.html'
    defaults = dict(
        ew.InputField.defaults,
        field=None,
        css_class=None,
        errors=None)

    def __init__(self, **kw):
        super(AdminField, self).__init__(**kw)
        for p in self.field.get_params():
            setattr(self, p, getattr(self.field, p))

    def resources(self):
        for r in self.field.resources():
            yield r


class TermsAgreementField(ew.Checkbox):
    template = TEMPLATE_DIR + 'terms-agreement-field.html'
    defaults = dict(
        ew.Checkbox.defaults,
        terms_str=None,
        terms_file=None,
        rows=10,
        cols=60,
        label="I agree to the terms & conditions",
        header="Terms & Conditions"
    )
    checkbox = ew.Checkbox()

    def render_file(self):
        engine, template = self.terms_file.split(':', 1)
        template = File(template, engine).template
        return template.render()

    def prepare_context(self, context):
        context = ew.Checkbox.prepare_context(self, context)
        if not self.terms_str and self.terms_file:
            self.terms_str = self.render_file()
        context['terms_str'] = self.terms_str
        return context

    def display_checkbox(self, **kw):
        self.defaults.update(kw)
        checkbox_kw = {k: getattr(self, k, None) for k in self.defaults.keys()}
        return self.checkbox.display(**checkbox_kw)


class HtmlTermsAgreementField(TermsAgreementField):
    template = TEMPLATE_DIR + 'html-terms-agreement-field.html'


class VisualizeTermsAgreementField(TermsAgreementField):
    """
    Invokes the forge visualizer machinery to visualize the terms agreement

    """
    template = TEMPLATE_DIR + 'visualizer-terms-agreement-field.html'
    visualizer_widget = IFrame()

    def prepare_context(self, context):
        context = ew.Checkbox.prepare_context(self, context)
        visualizers = Visualizer.get_for_resource(self.terms_file)
        if visualizers:
            visualizer = visualizers[0]
        else:
            visualizer = None
        context['visualizer'] = visualizer
        self.visualizer_widget.no_iframe_msg = (
            'Please install iframes to view the terms, or download them'
            '<a href="{}">here</a>'.format(self.terms_file)
        )
        return context


class IntegerField(ew.IntField):
    defaults = dict(
        ew.IntField.defaults,
        field_type='number',
        attrs={
            'min': '0',
        }
    )


class CurrentFileField(ew.HTMLField):
    """Renders a cool Current File widget"""
    defaults = dict(
        ew.HTMLField.defaults,
        show_label=True,
        label="Current File"
    )

    def prepare_context(self, context):
        text = '<span class="fake-file">{}</span>'.format(
            context.get('value', 'None'))
        context.setdefault('text', text)
        return context
