from pylons import tmpl_context as c
from formencode import validators as fev

import ew as ew_core
import ew.jinja2_ew as ew

from vulcanforge.common import validators as V
from vulcanforge.common.widgets.util import PageList, PageSize
from vulcanforge.discussion import widgets as DW
from vulcanforge.tools.forum import model as DM

TEMPLATE_DIR = 'jinja:vulcanforge:tools/forum/templates/discussion_widgets/'


class _ForumSummary(ew_core.Widget):
    template = TEMPLATE_DIR + 'forum_summary.html'
    defaults = dict(
        ew_core.Widget.defaults,
        name=None,
        value=None,
        show_label=True,
        label=None)


class _ForumsTable(ew.TableField):
    class hidden_fields(ew_core.NameList):
        _id = ew.HiddenField(validator=V.MingValidator(DM.ForumThread))

    class fields(ew_core.NameList):
        num_topics = ew.HTMLField(show_label=True, label='Topics')
        num_posts = ew.HTMLField(show_label=True, label='Posts')
        last_post = ew.HTMLField(text="${value and value.summary()}",
                                 show_label=True)
        subscribed = ew.Checkbox(suppress_label=True, show_label=True)

    fields.insert(0, _ForumSummary())


class ForumSubscriptionForm(ew.SimpleForm):
    class fields(ew_core.NameList):
        forums = _ForumsTable()
        page_list = PageList()

    submit_text = 'Update Subscriptions'


class _ThreadsTable(DW._ThreadsTable):
    class fields(ew_core.NameList):
        num_replies = ew.HTMLField(show_label=True, label='Num Replies')
        num_views = ew.HTMLField(show_label=True)
        flags = ew.HTMLField(show_label=True,
                             text="${unicode(', '.join(value))}")
        last_post = ew.HTMLField(text="${value and value.summary()}",
                                 show_label=True)
        subscription = ew.Checkbox(suppress_label=True, show_label=True)

    fields.insert(0, ew.LinkField(
        label='Subject', text="${value['subject']}",
        href="${value['url']()}", show_label=True))
    defaults = dict(DW._ThreadsTable.defaults, div_id='forum_threads')


class ThreadSubscriptionForm(DW.SubscriptionForm):
    class fields(ew_core.NameList):
        threads = _ThreadsTable()
        page_list = PageList()
        page_size = PageSize()


class AnnouncementsTable(DW._ThreadsTable):
    class fields(ew_core.NameList):
        num_replies = ew.HTMLField(show_label=True, label='Num Replies')
        num_views = ew.HTMLField(show_label=True)
        flags = ew.HTMLField(show_label=True,
                             text="${unicode(', '.join(value))}")
        last_post = ew.HTMLField(text="${value and value.summary()}",
                                 show_label=True)

    fields.insert(0, ew.LinkField(
        label='Subject', text="${value['subject']}",
        href="${value['url']()}", show_label=True))
    defaults = dict(DW._ThreadsTable.defaults, div_id='announcements')
    name = 'announcements'


class _ForumSelector(ew.SingleSelectField):
    def options(self):
        return [
            ew.Option(label=f.name, py_value=f, html_value=f.shortname)
            for f in c.app.forums]

    def to_python(self, value, state):
        result = DM.Forum.query.get(shortname=value,
                                    app_config_id=c.app.config._id)
        if not result:
            raise fev.Invalid('Illegal forum shortname: %s' % value, value,
                              state)
        return result

    def from_python(self, value, state):
        return value.shortname


class ModerateThread(ew.SimpleForm):
    submit_text = 'Save Changes'

    class fields(ew_core.NameList):
        discussion = _ForumSelector(label='New Forum')
        flags = ew.CheckboxSet(options=['Sticky', 'Announcement'])

    class buttons(ew_core.NameList):
        delete = ew.SubmitButton(label='Delete Thread')


class ModeratePost(ew.SimpleForm):
    submit_text = None
    fields = [
        ew.FieldSet(legend='Promote post to its own thread', fields=[
            ew.TextField(name='subject', label='Thread title'),
            ew.SubmitButton(name='promote', label='Promote to thread')])]


class PromoteToThread(ew.SimpleForm):
    submit_text = None
    fields = [
        ew.TextField(name='subject', label='Thread title'),
        ew.SubmitButton(name='promote', label='Promote to thread')]


class ForumHeader(DW.DiscussionHeader):
    template = TEMPLATE_DIR + 'forum_header.html'
    widgets = dict(DW.DiscussionHeader.widgets,
                   announcements_table=AnnouncementsTable(),
                   forum_subscription_form=ForumSubscriptionForm())


class ThreadHeader(DW.ThreadHeader):
    template = TEMPLATE_DIR + 'thread_header.html'
    defaults = dict(DW.ThreadHeader.defaults,
                    show_subject=True,
                    show_moderate=True,
                    show_tag_post=False)
    widgets = dict(DW.ThreadHeader.widgets,
                   moderate_thread=ModerateThread(),
                   announcements_table=AnnouncementsTable())


class Post(DW.PostWidget):
    show_subject = False
    widgets = dict(DW.PostWidget.widgets,
                   promote_to_thread=PromoteToThread())


class Thread(DW.ThreadWidget):
    defaults = dict(
        DW.ThreadWidget.defaults,
        show_subject=False)
    widgets = dict(DW.ThreadWidget.widgets,
                   thread_header=ThreadHeader(),
                   post=Post())


class Forum(DW.DiscussionWidget):
    allow_create_thread = True
    show_subject = True
    widgets = dict(DW.DiscussionWidget.widgets,
                   discussion_header=ForumHeader(),
                   forum_subscription_form=ForumSubscriptionForm(),
                   subscription_form=ThreadSubscriptionForm()
    )
