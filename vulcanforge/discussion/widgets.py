from formencode import validators as fev

import ew as ew_core
import ew.jinja2_ew as ew
from pylons import tmpl_context as c, url
import tg

from vulcanforge.common import validators as V
from vulcanforge.common.widgets import form_fields as ffw, forms as ff
from vulcanforge.common.widgets.util import PageList, PageSize
from vulcanforge.artifact.widgets import RelatedArtifactsWidget
from vulcanforge.discussion.model import Thread
from vulcanforge.resources.widgets import JSLink, JSScript

TEMPLATE_DIR = 'jinja:vulcanforge:discussion/templates/widgets/'


class NullValidator(fev.FancyValidator):
    perform_validation = True

    def _to_python(self, value, state):
        return value

    def _from_python(self, value, state):
        return value


# Discussion forms
class ModerateThread(ew.SimpleForm):
    defaults = dict(
        ew.SimpleForm.defaults,
        submit_text=None)

    class buttons(ew_core.NameList):
        delete = ew.SubmitButton(label='Delete Thread')


class ModeratePost(ew.SimpleForm):
    template = TEMPLATE_DIR + 'moderate_post.html'
    defaults = dict(
        ew.SimpleForm.defaults,
        submit_text=None)


class FlagPost(ew.SimpleForm):
    template = TEMPLATE_DIR + 'flag_post.html'
    defaults = dict(
        ew.SimpleForm.defaults,
        submit_text=None)


class AttachPost(ff.ForgeForm):
    defaults = dict(
        ff.ForgeForm.defaults,
        submit_text='Attach File',
        enctype='multipart/form-data')

    @property
    def fields(self):
        fields = [
            ew.InputField(name='file_info', field_type='file',
                          label='New Attachment')
        ]
        return fields


class ModeratePosts(ew.SimpleForm):
    template = TEMPLATE_DIR + 'moderate_posts.html'
    defaults = dict(
        ew.SimpleForm.defaults,
        submit_text=None)

    def resources(self):
        for r in super(ModeratePosts, self).resources(): yield r
        yield JSScript('''
      (function($){
          var tbl = $('form table');
          var checkboxes = $('input[type=checkbox]', tbl);
          $('a[href=#]', tbl).click(function () {
              checkboxes.each(function () {
                  if(this.checked) { this.checked = false; }
                  else { this.checked = true; }
              });
              return false;
          });
      }(jQuery));''')


class PostFilter(ff.ForgeForm):
    defaults = dict(
        ew.SimpleForm.defaults,
        submit_text=None,
        method='GET')
    fields = [
        ew.HiddenField(
            name='page',
            validator=fev.Int()),
        ew.FieldSet(label='Post Filter', fields=[
            ew.SingleSelectField(
                name='status',
                label='Show posts with status',
                options=[
                    ew.Option(py_value='-', label='Any'),
                    ew.Option(py_value='spam', label='Spam'),
                    ew.Option(py_value='pending', label='Pending moderation'),
                    ew.Option(py_value='ok', label='Ok')],
                if_missing='pending'),
            ew.IntField(name='flag',
                        label='Show posts with at least "n" flags',
                        css_class='text',
                        if_missing=0),
            ew.SubmitButton(label='Filter Posts')
        ])
    ]


class TagPost(ff.ForgeForm):
    # this ickiness is to override the default submit button
    def __call__(self, **kw):
        result = super(TagPost, self).__call__(**kw)
        submit_button = ffw.SubmitButton(label=result['submit_text'])
        result['extra_fields'] = [submit_button]
        result['buttons'] = [submit_button]
        return result

    fields = [ffw.LabelEdit(label='Labels', name='labels', className='title')]

    def resources(self):
        for r in ffw.LabelEdit(name='labels').resources(): yield r


class EditPost(ff.ForgeForm):
    template = TEMPLATE_DIR + 'edit_post.html'
    defaults = dict(
        ff.ForgeForm.defaults,
        show_subject=False,
        value=None,
        show_cancel=True,
        embedded=False,
        attachment_context_id=None
    )

    @property
    def fields(self):
        fields = ew_core.NameList()
        fields.append(ffw.MarkdownEdit(
            name='text',
            class_name='markdown-edit post-markdown'
        ))
        fields.append(ffw.RepeatedAttachmentField(
            name='new_attachments',
            label="Attach Files"
        ))
        fields.append(ew.HiddenField(name='forum', if_missing=None))
        if ew_core.widget_context.widget and ew_core.widget_context.render_context:
            # we are being displayed
            if ew_core.widget_context.render_context.get(
                    'show_subject', self.show_subject):
                fields.append(ew.TextField(name='subject'))
        else:
            # We are being validated
            validator = fev.UnicodeString(not_empty=True, if_missing='')
            fields.append(ew.TextField(name='subject', validator=validator))
        return fields

    def resources(self):
        for r in super(EditPost, self).resources():
            yield r
        for field in self.fields:
            for r in field.resources():
                yield r
        yield JSLink('discussion/post.js')


class NewTopicPost(EditPost):
    template = TEMPLATE_DIR + 'new_topic_post.html'
    defaults = dict(
        EditPost.defaults,
        show_subject=True,
        forums=None)


class _ThreadsTable(ew.TableField):
    template = TEMPLATE_DIR + 'threads_table.html'

    class hidden_fields(ew_core.NameList):
        _id = ew.HiddenField(validator=V.MingValidator(Thread))

    class fields(ew_core.NameList):
        num_replies = ew.HTMLField(show_label=True, label='Num Posts')
        num_views = ew.HTMLField(show_label=True)
        last_post = ew.HTMLField(
            text="${value and value.summary()}", show_label=True)
        subscription = ew.Checkbox(suppress_label=True, show_label=True)

    fields.insert(0, ew.LinkField(
        label='Subject', text="${value['subject']}",
        href="${value['url']()}", show_label=True))


class SubscriptionForm(ew.SimpleForm):
    template = 'jinja:vulcanforge:artifact/templates/widgets/subscription_form.html'
    value = None
    threads = None
    show_subject = False
    allow_create_thread = False
    limit = None
    page = 0
    count = 0
    submit_text = 'Update Subscriptions'
    params = ['value', 'threads', 'limit', 'page', 'count',
              'show_subject', 'allow_create_thread']

    class fields(ew_core.NameList):
        page_list = PageList()
        page_size = PageSize()
        threads = _ThreadsTable()

    def resources(self):
        for r in super(SubscriptionForm, self).resources(): yield r
        yield JSScript('''
        $(window).load(function () {
            $('tbody').children(':even').addClass('even');
        });''')


# Widgets
class HierWidget(ew_core.Widget):
    widgets = {}

    def prepare_context(self, context):
        response = super(HierWidget, self).prepare_context(context)
        response['widgets'] = self.widgets
        response['session'] = tg.session
        for w in self.widgets.values():
            w.parent_widget = self
        return response

    def resources(self):
        for w in self.widgets.itervalues():
            for r in w.resources():
                yield r

    def display(self, **kw):
        return ew_core.Widget.display(self, **kw)


class DiscussionHeader(HierWidget):
    template = TEMPLATE_DIR + 'discussion_header.html'
    params = ['value']
    value = None
    widgets = dict(
        edit_post=EditPost(submit_text='New Thread'))


class ThreadHeader(HierWidget):
    template = TEMPLATE_DIR + 'thread_header.html'
    defaults = dict(
        HierWidget.defaults,
        value=None,
        page=None,
        limit=None,
        count=None,
        show_moderate=False)
    widgets = dict(
        page_list=PageList(),
        page_size=PageSize(),
        moderate_thread=ModerateThread())
    #tag_post=TagPost())


class PostWidget(HierWidget):
    template = TEMPLATE_DIR + 'post_widget.html'
    defaults = dict(
        HierWidget.defaults,
        value=None,
        indent=0,
        page=0,
        limit=25,
        show_subject=False,
        suppress_promote=False,
        last_edit_date=None,
        last_edit_name=None)
    widgets = dict(
        moderate_post=ModeratePost(),
        edit_post=EditPost(submit_text='Save'),
        attachment_list=ffw.AttachmentList(),
        related_artifacts=RelatedArtifactsWidget()
    )

    def resources(self):
        for r in super(PostWidget, self).resources(): yield r
        for w in self.widgets.itervalues():
            for r in w.resources():
                yield r
        yield JSLink('js/lib/jquery/jquery.lightbox_me.js')
        yield JSLink('visualize/js/visualizer_util.js')
        yield JSLink('discussion/post.js')

    def display(self, value=None, attachment_context_id=None, **kw):
        last_edit_name, last_edit_date = None, None
        if value is not None:
            if attachment_context_id is None:
                attachment_context_id = str(value.slug)
            if value.edit_count:
                last_edit_date = value.last_edit_date
                if value.author().display_name != value.last_edit_by().display_name:
                    last_edit_name = value.last_edit_by().display_name
            else:
                last_edit_date = value.timestamp

        return HierWidget.display(
            self, value=value, last_edit_date=last_edit_date,
            attachment_context_id=attachment_context_id,
            last_edit_name=last_edit_name, **kw)


class PostThread(ew_core.Widget):
    template = TEMPLATE_DIR + 'post_thread.html'
    defaults = dict(
        ew_core.Widget.defaults,
        value=None,
        indent=0,
        page=0,
        limit=25,
        show_subject=False,
        suppress_promote=False,
        parent=None,
        children=None)


class ThreadWidget(HierWidget):
    template = TEMPLATE_DIR + 'thread_widget.html'
    name = 'thread'
    defaults = dict(
        HierWidget.defaults,
        value=None,
        page=None,
        limit=50,
        count=None,
        show_subject=False,
        new_post_text='+ New Comment')
    widgets = dict(
        page_list=PageList(),
        thread_header=ThreadHeader(),
        post_thread=PostThread(),
        post=PostWidget(),
        edit_post=EditPost(submit_text='Submit'))

    def resources(self):
        for r in super(ThreadWidget, self).resources():
            yield r
        for w in self.widgets.itervalues():
            for r in w.resources():
                yield r
        yield JSScript('''
        $(document).ready(function () {
            var thread_tag = $('a.thread_tag');
            var thread_spam = $('a.sidebar_thread_spam');
            var tag_thread_holder = $('#tag_thread_holder');
            var allow_moderate = $('#allow_moderate');
            var mod_thread_link = $('#mod_thread_link');
            var mod_thread_form = $('#mod_thread_form');
            if (mod_thread_link.length) {
                if (mod_thread_form.length) {
                    mod_thread_link.click(function (e) {
                        mod_thread_form.show();
                        return false;
                    });
                }
            }
            if (thread_tag.length) {
                if (tag_thread_holder.length) {
                    var submit_button = $('input[type="submit"]', tag_thread_holder);
                    var cancel_button = $('<a href="#" class="btn link">Cancel</a>').click(function(evt){
                        evt.preventDefault();
                        tag_thread_holder.hide();
                        thread_tag.removeClass('active');
                    });
                    submit_button.after(cancel_button);
                    thread_tag.click(function (e) {
                        tag_thread_holder.show();
                        thread_tag.addClass('active');
                        // focus the submit to scroll to the form, then focus the subject for them to start typing
                        submit_button.focus();
                        $('input[type="text"]', tag_thread_holder).focus();
                        return false;
                    });
                }
            }
            if (thread_spam.length) {
                if (allow_moderate.length) {
                    var cval = $.cookie('_session_id');
                    thread_spam[0].style.display='block';
                    thread_spam.click(function(evt){
                        evt.preventDefault();
                        $.post(thread_spam.attr('href'), {_session_id: cval}, function () {
                            window.location.reload();
                        });
                    });
                }
            }
        });
        ''')


class DiscussionWidget(HierWidget):
    template = TEMPLATE_DIR + 'discussion.html'
    defaults = dict(
        HierWidget.defaults,
        value=None,
        threads=None,
        show_subject=False,
        allow_create_thread=False)
    widgets = dict(
        discussion_header=DiscussionHeader(),
        edit_post=EditPost(submit_text='New Topic'),
        subscription_form=SubscriptionForm())

    def resources(self):
        for r in super(DiscussionWidget, self).resources():
            yield r

    def prepare_context(self, context):
        c.url = url.current()
        return HierWidget.prepare_context(self, context)
