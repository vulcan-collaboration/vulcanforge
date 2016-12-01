import json
import logging
from urllib import unquote
import pymongo
from bson import ObjectId

from tg import expose, validate, redirect, flash, response
from tg.decorators import with_trailing_slash
from pylons import tmpl_context as c, app_globals as g, request, url
from formencode import validators
from formencode.variabledecode import variable_decode
from webob import exc

from vulcanforge.artifact.model import Feed
from vulcanforge.artifact.model import Shortlink
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import (
    require_post, validate_form, vardec
)
from vulcanforge.common.app.controllers import DefaultSearchController
from vulcanforge.common.validators import DateTimeConverter
from vulcanforge.discussion import widgets as DW
from .forum import ForumController, TEMPLATE_DIR
from vulcanforge.tools.forum import import_support, model, util, widgets as FW
from vulcanforge.tools.forum.widgets.admin import AddForumShort, AddForum

LOG = logging.getLogger(__name__)


class DiscussionSearchController(DefaultSearchController):
    @expose(TEMPLATE_DIR + 'search.html')
    @with_trailing_slash
    @validate(dict(q=validators.UnicodeString(if_empty=None),
        history=validators.StringBool(if_empty=False),
        limit=validators.Int(if_empty=25),
        page=validators.Int(if_empty=0)))
    def search(self, **kw):
        return DefaultSearchController.search(self, **kw)


class RootController(BaseController):

    class Widgets(BaseController.Widgets):
        announcements_table = FW.AnnouncementsTable()

    class Forms(BaseController.Forms):
        new_topic = DW.NewTopicPost(submit_text='Save')
        forum_subscription_form = FW.ForumSubscriptionForm()
        add_forum = AddForum()
        add_forum_short = AddForumShort()

    def __init__(self):
        super(RootController, self).__init__()
        self.search = DiscussionSearchController()

    def _check_security(self):
        g.security.require_access(c.app, 'read')

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'index.html')
    def index(self, new_forum=False, add_forum=None, **kw):
        c.new_topic = self.Forms.new_topic
        c.add_forum = self.Forms.add_forum_short
        c.announcements_table = self.Widgets.announcements_table
        c.url = url.current()
        announcements = model.ForumThread.query.find(dict(
            app_config_id=c.app.config._id,
            flags='Announcement',
        )).all()
        forums_cursor = model.Forum.query.find(dict(
            app_config_id=c.app.config._id,
            parent_id=None
        ))
        forums_cursor.sort('ordinal', pymongo.ASCENDING)
        forums = forums_cursor.all()
        return dict(
            forums=forums,
            announcements=announcements,
            hide_forum=(not new_forum),
            add_forum=add_forum
        )

    @expose(TEMPLATE_DIR + 'index.html')
    def new_forum(self, **kw):
        g.security.require_access(c.app, 'admin')
        c.url = url.current()
        return self.index(new_forum=True, **kw)

    @expose(TEMPLATE_DIR + 'admin_forums.html')
    def forums(self, add_forum=None, **kw):
        g.security.require_access(c.app, 'admin')
        c.add_forum = self.Forms.add_forum
        return dict(
            app=c.app,
            allow_config=g.security.has_access(c.app, 'admin'),
            add_forum=add_forum
        )

    @vardec
    @expose()
    @require_post()
    def update_forums(self, forum=None, **kw):
        g.security.require_access(c.app, 'admin')
        if forum is None:
            forum = []
        for f in forum:
            forum = model.Forum.query.get(_id=ObjectId(str(f['id'])))
            if f.get('delete'):
                forum.deleted=True
            elif f.get('undelete'):
                forum.deleted=False
            else:
                if any(s in f['shortname'] for s in ('.', '/', ' ')):
                    flash('Shortname cannot contain space . or /', 'error')
                    redirect('.')
                forum.name = f['name']
                forum.shortname = f['shortname']
                forum.description = f['description']
                forum.ordinal = int(f['ordinal'])
                if 'icon' in f and f['icon'] is not None and f['icon'] != '':
                    util.save_forum_icon(forum, f['icon'])
        flash('Forums updated')
        redirect(request.referrer or 'forums')

    @vardec
    @expose()
    @require_post()
    @validate_form("add_forum", error_handler=forums)
    def add_forum(self, add_forum=None, **kw):
        g.security.require_access(c.app, 'admin')
        f = util.create_forum(c.app, add_forum)
        redirect(f.url())

    @vardec
    @expose()
    @require_post()
    @validate_form("add_forum", error_handler=index)
    def add_forum_short(self, add_forum=None, **kw):
        g.security.require_access(c.app, 'admin')
        f = util.create_forum(c.app, add_forum)
        redirect(f.url())

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'create_topic.html')
    def create_topic(self, text='', **kw):
        c.new_topic = self.Forms.new_topic
        forums = model.Forum.query.find(dict(
                        app_config_id=c.app.config._id,
                        deleted=False,
                        parent_id=None)).all()
        action_url = c.app.url + 'save_new_topic'
        return dict(action=action_url, forums=forums, defaults=dict(text=text))

    @expose(TEMPLATE_DIR + 'create_topic.html')
    def new_with_reference(self, artifact_ref=None, **kw):
        if not artifact_ref:
            raise exc.HTTPNotFound()
        shortlink = Shortlink.query.get(ref_id=unquote(artifact_ref))
        if shortlink:
            default_text = shortlink.render_link()
        else:
            default_text = ''
        return self.create_topic(text=default_text, **kw)

    @vardec
    @expose()
    @require_post()
    @validate_form("new_topic", error_handler=create_topic)
    def save_new_topic(self, subject=None, text=None, forum=None, **kw):
        discussion = model.Forum.query.get(
            app_config_id=c.app.config._id,
            shortname=forum)
        if discussion.deleted and not g.security.has_access(c.app, 'admin'):
            flash('This forum has been removed.')
            redirect(request.referrer)
        g.security.require_access(discussion, 'post')
        thd = discussion.get_discussion_thread(dict(
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
        flash('Message posted')
        redirect(thd.url())

    @expose('jinja:vulcanforge:common/templates/markdown_syntax.html')
    def markdown_syntax(self):
        """Static page explaining markdown."""
        return dict()

    @expose()
    def _lookup(self, id=None, *remainder):
        if id:
            id = unquote(id)
            return ForumController(id), remainder
        else:
            raise exc.HTTPNotFound()

    # FIXME this code is not used, but it should be so we can do Forum-level
    # subscriptions
    @vardec
    @expose()
    @validate_form("forum_subscription_form")
    def subscribe(self, **kw):
        g.security.require_authenticated()
        forum = kw.pop('forum', [])
        thread = kw.pop('thread', [])
        objs = []
        for data in forum:
            objs.append(dict(
                obj=model.Forum.query.get(
                    shortname=data['shortname'],
                    app_config_id=c.app.config._id
                ),
                subscribed=bool(data.get('subscribed'))
            ))
        for data in thread:
            objs.append(dict(obj=model.Thread.query.get(_id=data['id']),
                             subscribed=bool(data.get('subscribed'))))
        for obj in objs:
            if obj['subscribed']:
                obj['obj'].subscriptions[str(c.user._id)] = True
            else:
                obj['obj'].subscriptions.pop(str(c.user._id), None)
        redirect(request.referer or 'index')  # TODO: check

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
        title = 'Recent posts to %s' % c.app.config.options.mount_label

        feed = Feed.feed(
            dict(project_id=c.project._id, app_config_id=c.app.config._id),
            feed_type,
            title,
            c.app.url,
            title,
            since, until, page, limit)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        return feed.writeString('utf-8')


class RootRestController(BaseController):

    @expose('json:')
    def validate_import(self, doc=None, username_mapping=None, **kw):
        g.security.require_access(c.project, 'admin')
        if username_mapping is None: username_mapping = {}
        try:
            doc = json.loads(doc)
            warnings, doc = import_support.validate_import(doc, username_mapping)
            return dict(warnings=warnings, errors=[])
        except Exception as e:
            LOG.exception(e)
            raise
            #return dict(status=False, errors=[repr(e)])

    @expose('json:')
    def perform_import(self, doc=None, username_mapping=None,
                       default_username=None, create_users=False, **kw):
        g.security.require_access(c.project, 'admin')
        if username_mapping is None: username_mapping = '{}'
        if c.api_token.get_capability('import') != c.project.shortname:
            LOG.error('Import capability is not enabled for %s', c.project.shortname)
            raise exc.HTTPForbidden(detail='Import is not allowed')
        try:
            doc = json.loads(doc)
            username_mapping = json.loads(username_mapping)
            warnings = import_support.perform_import(
                doc, username_mapping, default_username, create_users)
            return dict(warnings=warnings, errors=[])
        except Exception as e:
            LOG.exception(e)
            raise
            # return dict(status=False, errors=[str(e)])
