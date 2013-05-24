from urllib import unquote
from datetime import datetime

from tg import expose, redirect, validate, request, response, flash
from tg.decorators import without_trailing_slash
from pylons import app_globals as g, tmpl_context as c
from formencode import validators
from formencode.variabledecode import variable_decode
from webob import exc
from ming.base import Object
from ming.utils import LazyProperty


from vulcanforge.artifact.controllers import AttachmentController, \
    AttachmentsController
from vulcanforge.artifact.model import Feed
from vulcanforge.artifact.widgets import RelatedArtifactsWidget
from vulcanforge.common.controllers import BaseController, BaseTGController
from vulcanforge.common.controllers.decorators import vardec, require_post, \
    validate_form
from vulcanforge.common.helpers import json_validation_error
from vulcanforge.common.model.session import artifact_orm_session
from vulcanforge.common.util.filesystem import guess_mime_type
from vulcanforge.common.validators import DateTimeConverter

from vulcanforge.discussion.model import (
    Discussion,
    Post,
    Thread,
    DiscussionAttachment
)
from vulcanforge.discussion.widgets import (
    EditPost,
    PostWidget,
    FlagPost,
    ModeratePost,
    ThreadWidget,
    ThreadHeader,
    ModeratePosts,
    PostFilter,
    DiscussionWidget
)

TEMPLATE_DIR = 'jinja:vulcanforge:discussion/templates/'


class pass_validator(object):
    def validate(self, v, s):
        return v
pass_validator = pass_validator()


class ModelConfig(object):
    Discussion = Discussion
    Thread = Thread
    Post = Post
    Attachment = DiscussionAttachment


class DiscussionAttachmentController(AttachmentController):
    AttachmentClass = DiscussionAttachment
    edit_perm = 'moderate'


class DiscussionAttachmentsController(AttachmentsController):
    AttachmentControllerClass = DiscussionAttachmentController


class PostController(BaseController):
    Model = ModelConfig

    class Widgets(BaseController.Widgets):
        post = PostWidget()

    class Forms(BaseController.Forms):
        edit_post = EditPost()
        flag_post = FlagPost()
        moderate_post = ModeratePost()

    def _check_security(self):
        g.security.require_access(self.post, 'read')

    attachments_controller_cls = DiscussionAttachmentsController

    def __init__(self, thread, slug):
        self.thread = thread
        self._post_slug = slug
        self.post = self.Model.Post.query.get(
            slug=slug,
            thread_id=self.thread._id
        )
        if not self.post:
            raise exc.HTTPNotFound()
        self.attachment = self.attachments_controller_cls(self.post)

    @vardec
    @expose(TEMPLATE_DIR + 'post.html')
    @validate(pass_validator)
    def index(self, version=None, **kw):
        c.post = self.Widgets.post
        if request.method == 'POST':
            g.security.require_access(self.post, 'moderate')
            posted_values = variable_decode(request.POST)
            for attachment in posted_values.pop('new_attachments', []):
                if not hasattr(attachment, 'file'):
                    continue
                self.post.attach(
                    attachment.filename,
                    attachment.file,
                    content_type=attachment.type,
                    post_id=self.post._id,
                    thread_id=self.post.thread_id,
                    discussion_id=self.post.discussion_id)
            post_fields = self.Forms.edit_post.to_python(kw, None)
            for k, v in post_fields.iteritems():
                try:
                    setattr(self.post, k, v)
                except AttributeError:
                    continue
            self.post.edit_count = self.post.edit_count + 1
            self.post.last_edit_date = datetime.utcnow()
            self.post.last_edit_by_id = c.user._id
            redirect(request.referrer or self.thread.url())
        elif request.method == 'GET':
            if version is not None:
                HC = self.post.__mongometa__.history_class
                ss = HC.query.find({
                    'artifact_id': self.post._id,
                    'version': int(version)
                }).first()
                if not ss:
                    raise exc.HTTPNotFound
                ### NOTE: wtf?
                post = Object(
                    ss.data,
                    acl=self.post.acl,
                    author=self.post.author,
                    url=self.post.url,
                    thread=self.post.thread,
                    reply_subject=self.post.reply_subject,
                    attachments=self.post.attachments,
                    related_artifacts=self.post.related_artifacts,
                    relations=self.post.relations,
                    type_s=self.post.type_s,
                    index_id=lambda: self.post.index_id(),
                    absolute_url=lambda: self.post.absolute_url(),
                    app_config=self.post.app_config
                )
            else:
                post = self.post
            return dict(discussion=self.post.discussion, post=post)

    @vardec
    @expose()
    @validate_form('edit_post', error_handler=index)
    @require_post(redir='.')
    def reply(self, **kw):
        g.security.require_access(self.thread, 'post')
        reply = self.thread.post(parent_id=self.post._id, **kw)
        posted_values = variable_decode(request.POST)
        for attachment in posted_values.pop('new_attachments', []):
            if hasattr(attachment, 'file'):
                reply.attach(
                    attachment.filename,
                    attachment.file,
                    content_type=attachment.type,
                    post_id=reply._id,
                    thread_id=self.post.thread_id,
                    discussion_id=self.post.discussion_id)
        self.thread.num_replies += 1
        redirect(request.referer or self.thread.url())

    @vardec
    @expose()
    @require_post()
    @validate(pass_validator, error_handler=index)
    def moderate(self, **kw):
        g.security.require_access(self.post, 'moderate')
        if kw.pop('delete', None):
            self.post.delete()
            self.thread.update_stats()
        elif kw.pop('spam', None):
            self.post.status = 'spam'
            self.thread.update_stats()
        redirect(request.referer or self.thread.url())

    @vardec
    @expose()
    @require_post()
    @validate_form('flag_post', error_handler=index)
    def flag(self, **kw):
        if c.user._id not in self.post.flagged_by:
            self.post.flagged_by.append(c.user._id)
            self.post.flags += 1
        redirect(request.referer or self.thread.url())

    @vardec
    @expose()
    @require_post()
    def attach(self, file_info=None):
        g.security.require_access(self.post, 'moderate')
        if hasattr(file_info, 'file'):
            mime_type = file_info.type
            # If mime type was not passed or bogus, guess it
            if not mime_type or '/' not in mime_type:
                mime_type = guess_mime_type(file_info.filename)
            self.post.attach(
                file_info.filename, file_info.file, content_type=mime_type,
                post_id=self.post._id,
                thread_id=self.post.thread_id,
                discussion_id=self.post.discussion_id)
        redirect(request.referer or self.thread.url())

    @expose()
    def _lookup(self, id, *remainder):
        id = unquote(id)
        controller = self.__class__(self.thread, self._post_slug + '/' + id)
        return controller, remainder


class ThreadController(BaseController):
    Model = ModelConfig

    class Widgets(BaseController.Widgets):
        thread = ThreadWidget()
        thread_header = ThreadHeader()
        related_artifacts = RelatedArtifactsWidget()

    class Forms(BaseController.Forms):
        edit_post = EditPost()

    post_controller_cls = PostController

    def _check_security(self):
        g.security.require_access(self.thread, 'read')

    def __init__(self, thread_id):
        self.thread = self.Model.Thread.query.get(_id=thread_id)
        if not self.thread:
            raise exc.HTTPNotFound

    @expose()
    def _lookup(self, id, *remainder):
        id = unquote(id)
        return self.post_controller_cls(self.thread, id), remainder

    @expose(TEMPLATE_DIR + 'thread.html')
    def index(self, limit=25, page=0, count=0, **kw):
        c.thread = self.Widgets.thread
        c.thread_header = self.Widgets.thread_header
        c.related_artifacts_widget = self.Widgets.related_artifacts
        limit, page, start = g.handle_paging(limit, page)
        self.thread.num_views += 1
        # the update to num_views shouldn't affect it
        artifact_orm_session._get().skip_mod_date = True
        count = self.thread.query_posts(page=page, limit=int(limit)).count()
        return dict(
            discussion=self.thread.discussion,
            thread=self.thread,
            page=page,
            count=count,
            limit=limit,
            show_moderate=kw.get('show_moderate')
        )

    @vardec
    @expose()
    @require_post()
    @validate_form("edit_post", error_handler=index)
    def post(self, **kw):
        g.security.require_access(self.thread, 'post')
        if not kw['text']:
            flash('Your post was not saved. You must provide content.',
                  'error')
            redirect(request.referer or 'index')
        p = self.thread.add_post(**kw)
        posted_values = variable_decode(request.POST)
        for attachment in posted_values.get('new_attachments', []):
            if not hasattr(attachment, 'file'):
                continue
            p.attach(
                attachment.filename,
                attachment.file,
                content_type=attachment.type,
                post_id=p._id,
                thread_id=p.thread_id,
                discussion_id=p.discussion_id)
        if self.thread.artifact:
            self.thread.artifact.mod_date = datetime.utcnow()
        flash('Message posted')
        redirect(request.referer or 'index')

    @expose()
    @require_post()
    def tag(self, labels, **kw):
        g.security.require_access(self.thread, 'post')
        self.thread.labels = labels.split(',')
        redirect(request.referer or 'index')

    @expose()
    @require_post()
    def flag_as_spam(self, **kw):
        g.security.require_access(self.thread, 'moderate')
        self.thread.first_post.status = 'spam'
        flash('Thread flagged as spam.')
        redirect(request.referer or 'index')

    @without_trailing_slash
    @expose()
    @validate(dict(
            since=DateTimeConverter(if_empty=None),
            until=DateTimeConverter(if_empty=None),
            page=validators.Int(if_empty=None),
            limit=validators.Int(if_empty=None)))
    def feed(self, since=None, until=None, page=None, limit=None):
        if request.environ['PATH_INFO'].endswith('.atom'):
            feed_type = 'atom'
        else:
            feed_type = 'rss'
        title = 'Recent posts to %s' % (self.thread.subject or '(no subject)')
        feed = Feed.feed(
            dict(ref_id=self.thread.index_id()),
            feed_type,
            title,
            self.thread.url(),
            title,
            since, until, page, limit)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        return feed.writeString('utf-8')


class ThreadsController(BaseController):

    def __init__(self, thread_controller_cls):
        self.thread_controller_cls = thread_controller_cls

    @expose()
    def _lookup(self, id=None, *remainder):
        if id:
            id = unquote(id)
            return self.thread_controller_cls(id), remainder
        else:
            raise exc.HTTPNotFound()


class ModerationController(BaseController):
    Model = ModelConfig

    class Forms(BaseController.Forms):
        post_filter = PostFilter()
        moderate_posts = ModeratePosts()

    def __init__(self, discussion_controller):
        self.discussion_controller = discussion_controller

    @property
    def discussion(self):
        """Enables context-driven discussion acquisition"""
        return self.discussion_controller.discussion

    def _check_security(self):
        g.security.require_access(self.discussion, 'moderate')

    @vardec
    @expose(TEMPLATE_DIR + 'moderate.html')
    @validate_form("post_filter")
    def index(self, **kw):
        page = kw.pop('page', 0)
        limit = kw.pop('limit', 50)
        status = kw.pop('status', 'pending')
        flag = kw.pop('flag', None)
        c.post_filter = self.Forms.post_filter
        c.moderate_posts = self.Forms.moderate_posts
        query = dict(discussion_id=self.discussion._id)
        if status != '-':
            query['status'] = status
        if flag:
            query['flags'] = {'$gte': int(flag)}
        q = self.Model.Post.query.find(query)
        count = q.count()
        if not page:
            page = 0
        page = int(page)
        limit = int(limit)
        q = q.skip(page)
        q = q.limit(limit)
        pgnum = (page // limit) + 1
        pages = (count // limit) + 1
        return dict(
            discussion=self.discussion,
            posts=q, page=page, limit=limit,
            status=status, flag=flag,
            pgnum=pgnum, pages=pages)

    @vardec
    @expose()
    @require_post()
    def save_moderation(self, post=None, delete=None, spam=None, approve=None,
                        **kw):
        for p in post:
            if 'checked' in p:
                posted = self.Model.Post.query.get(full_slug=p['full_slug'])
                if delete:
                    posted.delete()
                    posted.thread.num_replies -= 1
                elif spam:
                    posted.status = 'spam'
                    posted.thread.num_replies -= 1
                elif approve:
                    posted.status = 'ok'
                    posted.thread.num_replies += 1
        redirect(request.referer or 'index')


# Controllers
class BaseDiscussionController(BaseTGController):
    Model = ModelConfig

    class Widgets(BaseTGController.Widgets):
        discussion = DiscussionWidget()

    thread_controller_cls = ThreadController
    moderate_controller_cls = ModerationController
    discussion = None  # subclasses should implement this

    def __init__(self):
        self.thread = ThreadsController(self.thread_controller_cls)
        if self.moderate_controller_cls:
            self.moderate = self.moderate_controller_cls(self)

    @expose(TEMPLATE_DIR + 'index.html')
    def index(self, threads=None, limit=None, page=0, count=0, **kw):
        c.discussion = self.Widgets.discussion
        if threads is None:
            threads = self.discussion.threads
        return dict(discussion=self.discussion, limit=limit, page=page,
            count=count, threads=threads)

    @vardec
    @expose()
    def subscribe(self, **kw):
        threads = kw.pop('threads')
        for t in threads:
            thread = self.Model.Thread.query.find(dict(_id=t['_id'])).first()
            if 'subscription' in t:
                thread['subscription'] = True
            else:
                thread['subscription'] = False
            artifact_orm_session._get().skip_mod_date = True
        redirect(request.referer or 'index')

    @without_trailing_slash
    @expose()
    @validate(dict(
        since=DateTimeConverter(if_empty=None),
        until=DateTimeConverter(if_empty=None),
        page=validators.Int(if_empty=None),
        limit=validators.Int(if_empty=None)))
    def feed(self, since=None, until=None, page=None, limit=None):
        if request.environ['PATH_INFO'].endswith('.atom'):
            feed_type = 'atom'
        else:
            feed_type = 'rss'
        title = 'Recent posts to %s' % self.discussion.name
        query = {
            'ref_id': {'$in': [t.index_id() for t in self.discussion.threads]}
        }
        feed = Feed.feed(
            query, feed_type, title, self.discussion.url(), title, since,
            until, page, limit)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        return feed.writeString('utf-8')


class AppDiscussionController(BaseDiscussionController):

    @LazyProperty
    def discussion(self):
        return self.Model.Discussion.query.get(
            shortname=c.app.config.options.mount_point,
            app_config_id=c.app.config._id)


class PostRestController(PostController):

    @expose('json:')
    def index(self, **kw):
        return dict(post=self.post)

    @vardec
    @expose()
    @require_post()
    @validate_form("edit_post", error_handler=json_validation_error)
    def reply(self, **kw):
        g.security.require_access(self.thread, 'post')
        post = self.thread.post(parent_id=self.post._id, **kw)
        self.thread.num_replies += 1
        redirect(post.slug.split('/')[-1] + '/')


class ThreadRestController(ThreadController):

    post_controller_cls = PostRestController

    @expose('json:')
    def index(self, **kw):
        return dict(thread=self.thread)

    @vardec
    @expose()
    @require_post()
    @validate_form("edit_post", error_handler=json_validation_error)
    def new(self, **kw):
        g.security.require_access(self.thread, 'post')
        p = self.thread.add_post(**kw)
        redirect(p.slug + '/')


class AppDiscussionRestController(AppDiscussionController):
    thread_controller_cls = ThreadRestController

    @expose('json:')
    def index(self, **kw):
        return dict(discussion=self.discussion)
