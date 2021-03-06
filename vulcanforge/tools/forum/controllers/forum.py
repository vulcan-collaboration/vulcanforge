import logging
import pymongo

from tg import expose, validate, redirect, request, flash
from tg.decorators import with_trailing_slash
from pylons import app_globals as g, tmpl_context as c, url
from webob import exc
from formencode.variabledecode import variable_decode

from vulcanforge.common.controllers.decorators import (
    require_post, validate_form, vardec
)
from vulcanforge.discussion.controllers import (
    BaseDiscussionController,
    ThreadController,
    PostController,
    ModerationController,
)
from vulcanforge.discussion.model import DiscussionAttachment
from vulcanforge.discussion import widgets as DW
from vulcanforge.tools.forum import model as DM
from vulcanforge.tools.forum import widgets as FW
from vulcanforge.tools.forum import tasks

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.tools.forum:templates/discussionforums/'
BASE_TEMPLATE_DIR = 'jinja:vulcanforge.discussion:templates/'


class pass_validator(object):
    def validate(self, v, s):
        return v

pass_validator = pass_validator()


class ModelConfig(object):
    Discussion = DM.Forum
    Thread = DM.ForumThread
    Post = DM.ForumPost
    Attachment = DiscussionAttachment


class ForumPostController(PostController):
    Model = ModelConfig

    class Widgets(PostController.Widgets):
        post = FW.Post()

    class Forms(PostController.Forms):
        edit_post = DW.EditPost(show_subject=True)
        moderate_post = FW.ModeratePost()

    @expose(BASE_TEMPLATE_DIR + 'post.html')
    def index(self, **kw):
        if self.thread.discussion.deleted and\
           not g.security.has_access(c.app, 'admin'):
            redirect(self.thread.discussion.url() + 'deleted')
        return super(ForumPostController, self).index(**kw)

    @expose()
    @require_post()
    @validate_form("moderate_post", error_handler=index)
    def moderate(self, **kw):
        g.security.require_access(self.post, 'moderate')
        if self.thread.discussion.deleted and\
           not g.security.has_access(c.app, 'admin'):
            redirect(self.thread.discussion.url() + 'deleted')
        tasks.calc_thread_stats.post(self.post.thread._id)
        tasks.calc_forum_stats(self.post.discussion.shortname)
        if kw.pop('promote', None):
            new_thread = self.post.promote()
            tasks.calc_thread_stats.post(new_thread._id)
            redirect(request.referer or self.thread.url())
        return super(ForumPostController, self).moderate(**kw)


class ForumThreadController(ThreadController):
    Model = ModelConfig

    class Widgets(ThreadController.Widgets):
        thread = FW.Thread()
        thread_header = FW.ThreadHeader()
        moderate_thread = FW.ModerateThread()

    class Forms(ThreadController.Forms):
        edit_post = DW.EditPost(show_subject=True)

    post_controller_cls = ForumPostController

    @expose(TEMPLATE_DIR + 'thread.html')
    def index(self, limit=None, page=0, count=0, **kw):
        c.url = url.current()
        if self.thread.discussion.deleted and \
                not g.security.has_access(c.app, 'admin'):
            redirect(self.thread.discussion.url() + 'deleted')

        show_moderate = c.app.config.options.get('PostingPolicy') != 'ApproveAll'
        return super(ForumThreadController, self).index(
            limit=limit,
            page=page,
            count=count,
            show_moderate=show_moderate,
            **kw
        )

    @vardec
    @expose()
    @require_post()
    @validate(pass_validator, index)
    def moderate(self, **kw):
        g.security.require_access(self.thread, 'moderate')
        if self.thread.discussion.deleted and \
                not g.security.has_access(c.app, 'admin'):
            redirect(self.thread.discussion.url() + 'deleted')
        args = self.Widgets.moderate_thread.validate(kw, None)
        tasks.calc_forum_stats.post(self.thread.discussion.shortname)
        if args.pop('delete', None):
            url = self.thread.discussion.url()
            self.thread.delete()
            redirect(url)
        forum = args.pop('discussion')
        if forum != self.thread.discussion:
            tasks.calc_forum_stats.post(forum.shortname)
            self.thread.set_forum(forum)
        self.thread.flags = args.pop('flags', [])
        redirect(self.thread.url())


class ForumModerationController(ModerationController):
    Model = ModelConfig


class ForumController(BaseDiscussionController):
    Model = ModelConfig

    class Forms(object):
        new_topic = DW.NewTopicPost(submit_text='Save')
        subscription_form = DW.SubscriptionForm()

    class Widgets(BaseDiscussionController.Widgets):
        discussion = FW.Forum()
        discussion_header = DW.DiscussionHeader()

    thread_controller_cls = ForumThreadController
    moderate_controller_cls = ForumModerationController

    def _check_security(self):
        g.security.require_access(self.discussion, 'read')

    def __init__(self, forum_id):
        c.discussion = self.discussion = DM.Forum.query.get(
            app_config_id=c.app.config._id,
            shortname=forum_id)
        if not self.discussion:
            raise exc.HTTPNotFound()
        super(ForumController, self).__init__()

    @expose()
    def _lookup(self, id=None, *remainder):
        if id and self.discussion:
            controller = ForumController(self.discussion.shortname + '/' + id)
            return controller, remainder
        else:
            raise exc.HTTPNotFound()

    @expose(TEMPLATE_DIR + 'discussion.html')
    def index(self, threads=None, limit=None, page=0, count=0, **kw):
        if self.discussion.deleted and \
        not g.security.has_access(c.app, 'admin'):
            redirect(self.discussion.url() + 'deleted')
        limit, page, start = g.handle_paging(limit, page)
        threads = DM.ForumThread.query.find({
            'discussion_id': self.discussion._id}
        ).sort([
            ('flags', pymongo.DESCENDING),
            ('mod_date', pymongo.DESCENDING)
        ])
        return dict(
            discussion=self.discussion,
            threads=threads.skip(start).limit(int(limit)).all(),
            limit=limit,
            page=page,
            count=threads.count(),
            show_tutorial=True,
            widgets=dict(
                discussion_header=self.Widgets.discussion_header,
                subscription_form=self.Forms.subscription_form)
        )

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'create_topic.html')
    def create_topic(self, text='', **kw):
        c.new_topic = self.Forms.new_topic
        action_url = c.discussion.url() + 'save_new_topic'
        return dict(action_url=action_url, forums=[], defaults=dict(text=text))

    @vardec
    @expose()
    @require_post()
    @validate_form("new_topic", error_handler=create_topic)
    def save_new_topic(self, subject=None, text=None, **kw):
        g.security.require_access(c.discussion, 'post')
        thd = c.discussion.get_discussion_thread(dict(
                headers=dict(Subject=subject)))
        post = thd.post(subject, text)
        posted_values = variable_decode(request.POST)
        for attachment in posted_values.pop('new_attachments', []):
            if not hasattr(attachment, 'file'):
                continue
            post.attach(
                attachment.filename,
                attachment.file,
                content_type=attachment.type,
                post_id=post._id,
                thread_id=post.thread_id,
                discussion_id=post.discussion_id)
        flash('Topic was created')
        redirect(thd.url())

    @expose()
    def icon(self):
        return self.discussion.icon.serve()

    @expose(TEMPLATE_DIR + 'deleted.html')
    def deleted(self):
        return dict()
