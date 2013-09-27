import re

from ming import schema
from ming.utils import LazyProperty
from ming.odm import FieldProperty, RelationProperty, ForeignIdProperty, Mapper
import pymongo
from pylons import app_globals as g

from vulcanforge.common.util import ConfigProxy
from vulcanforge.common import helpers as h
from vulcanforge.common.model.filesystem import File
from vulcanforge.artifact.model import Artifact
from vulcanforge.discussion.model import (
    Discussion,
    AbstractThread,
    PostHistory,
    AbstractPost,
    DiscussionAttachment
)

config = ConfigProxy(common_suffix='forgemail.domain')


class Forum(Discussion):

    class __mongometa__:
        name = 'forum'

    type_s = 'Discussion'

    parent_id = FieldProperty(schema.ObjectId, if_missing=None)
    threads = RelationProperty('ForumThread')
    posts = RelationProperty('ForumPost')
    deleted = FieldProperty(bool, if_missing=False)
    ordinal = FieldProperty(int, if_missing=0)

    @classmethod
    def attachment_class(cls):
        return ForumAttachment

    @classmethod
    def thread_class(cls):
        return ForumThread

    @LazyProperty
    def threads(self):
        threads = self.thread_class().query.find(
            dict(discussion_id=self._id)).all()
        announcements, sticky, other = [], [], []
        for t in threads:
            if 'Announcement' in t.flags:
                announcements.append(t)
            elif 'Sticky' in t.flags:
                sticky.append(t)
            else:
                other.append(t)
        return announcements + sticky + other

    @property
    def parent(self):
        return Forum.query.get(_id=self.parent_id)

    @property
    def subforums(self):
        return Forum.query.find(dict(parent_id=self._id)).all()

    @property
    def email_address(self):
        domain = '.'.join(reversed(
            self.app.url[1:-1].split('/'))).replace('_', '-')
        return '%s@%s%s' % (
            self.shortname.replace('/', '.'), domain, config.common_suffix)

    @LazyProperty
    def announcements(self):
        return self.thread_class().query.find(dict(
                app_config_id=self.app_config_id,
                flags='Announcement')).all()

    def breadcrumbs(self):
        if self.parent:
            l = self.parent.breadcrumbs()
        else:
            l = []
        return l + [(self.name, self.url())]

    def url(self):
        return h.urlquote(self.app.url + self.shortname + '/')

    def delete(self):
        # Delete the subforums
        for subforum in self.subforums:
            subforum.delete()
        super(Forum, self).delete()

    def get_discussion_thread(self, data=None, generate_if_missing=True):
        # If the data is a reply, use the parent's thread
        subject = '[no subject]'
        parent_id = None
        message_id = None
        if data is not None:
            parent_id = (data.get('in_reply_to') or [None])[0]
            message_id = data.get('message_id') or ''
            subject = data['headers'].get('Subject', subject)
        if parent_id is not None:
            parent = self.post_class().query.get(_id=parent_id)
            if parent:
                return parent.thread
        if message_id:
            post = self.post_class().query.get(_id=message_id)
            if post:
                return post.thread
        # Otherwise it's a new thread
        if generate_if_missing:
            return self.thread_class()(discussion_id=self._id, subject=subject)

    @property
    def discussion_thread(self):
        return None

    @property
    def icon(self):
        return ForumFile.query.get(forum_id=self._id)

    def icon_url(self):
        icon = self.icon
        if icon:
            return icon.url()
        else:
            return g.resource_manager.absurl('images/project_default.png')

    def get_latest_post(self):
        threads = ForumThread.query.find({'discussion_id': self._id})
        threads.sort('mod_date', pymongo.DESCENDING)
        threads.limit(1)
        threads = threads.all()
        if len(threads) > 0:
            return threads[0]


class ForumFile(File):

    class __mongometa__:
        name = 'forum_file'
        indexes = ['forum_id'] + File.__mongometa__.indexes

    forum_id = FieldProperty(schema.ObjectId)

    THUMB_URL_POSTFIX = ''

    @property
    def artifact(self):
        return Forum.query.get(_id=self.forum_id)

    def local_url(self):
        return self.artifact.url() + 'icon'


class ForumThread(AbstractThread):

    class __mongometa__:
        name = 'forum_thread'
        indexes = ['flags']

    type_s = 'Thread'

    discussion_id = ForeignIdProperty(Forum)
    first_post_id = ForeignIdProperty('ForumPost')
    flags = FieldProperty([str])

    discussion = RelationProperty(Forum)
    posts = RelationProperty('ForumPost')
    first_post = RelationProperty('ForumPost', via='first_post_id')

    def index(self, text_objects=None, **kwargs):
        # collect text objects
        if text_objects is None:
            text_objects = []
        text_objects.append(self.subject)

        # index that noise
        return Artifact.index(self,
            type_s=self.type_s,
            title_s='Thread: %s' % (self.subject or '(no subject)'),
            name_s=self.subject,
            views_i=self.num_views,
            text_objects=text_objects,
            **kwargs
        )

    def link_text(self):
        return self.subject

    @property
    def status(self):
        if self.first_post:
            return self.first_post.status
        else:
            return 'ok'

    @classmethod
    def attachment_class(cls):
        return ForumAttachment

    @staticmethod
    def discussion_class():
        return Forum

    @staticmethod
    def post_class():
        return ForumPost

    @property
    def artifact(self):
        return self.discussion

    def primary(self):
        return self

    @property
    def email_address(self):
        return self.discussion.email_address

    def post(self, subject, text, message_id=None, parent_id=None, **kw):
        post = AbstractThread.post(
            self, text, message_id=message_id, parent_id=parent_id
        )
        if not self.first_post_id:
            self.first_post_id = post._id
            self.num_replies = 1
        return post

    def set_forum(self, new_forum):
        self.post_class().query.update(
            dict(discussion_id=self.discussion_id, thread_id=self._id),
            {'$set': dict(discussion_id=new_forum._id)},
            multi=True)
        self.attachment_class().query.update(
            {'discussion_id': self.discussion_id, 'thread_id': self._id},
            {'$set': dict(discussion_id=new_forum._id)},
            multi=True)
        self.discussion_id = new_forum._id


class ForumPostHistory(PostHistory):

    class __mongometa__:
        name = 'post_history'

    artifact_id = ForeignIdProperty('ForumPost')


class ForumPost(AbstractPost):

    class __mongometa__:
        name = 'forum_post'
        history_class = ForumPostHistory

    discussion_id = ForeignIdProperty(Forum)
    thread_id = ForeignIdProperty(ForumThread)

    discussion = RelationProperty(Forum)
    thread = RelationProperty(ForumThread)

    def url(self):
        if self.thread:
            return self.thread.url() + '#' + self.id_safe_slug

    @classmethod
    def attachment_class(cls):
        return ForumAttachment

    @property
    def email_address(self):
        return self.discussion.email_address

    def primary(self):
        return self

    def promote(self):
        """Make the post its own thread head"""
        thd = self.thread_class()(
            discussion_id=self.discussion_id,
            subject=self.subject,
            first_post_id=self._id)
        self.move(thd, None)
        return thd

    def move(self, thread, new_parent_id):
        # Add a placeholder to note the move
        placeholder = self.thread.post(
            subject='Discussion moved',
            text='',
            parent_id=self.parent_id)
        placeholder.slug = self.slug
        placeholder.full_slug = self.full_slug
        placeholder.approve()
        if new_parent_id:
            parent = self.post_class().query.get(_id=new_parent_id)
        else:
            parent = None
        # Set the thread ID on my replies and attachments
        old_slug = self.slug + '/', self.full_slug + '/'
        reply_re = re.compile(self.slug + '/.*')
        self.slug, self.full_slug = self.make_slugs(
            parent=parent, timestamp=self.timestamp
        )
        placeholder.text = 'Discussion moved to [here](%s#post-%s)' % (
            thread.url(), self.slug)
        new_slug = self.slug + '/', self.full_slug + '/'
        self.discussion_id = thread.discussion_id
        self.thread_id = thread._id
        self.parent_id = new_parent_id
        self.text = 'Discussion moved from [here](%s#post-%s)\n\n%s' % (
            placeholder.thread.url(), placeholder.slug, self.text)
        reply_tree = self.query.find(dict(slug=reply_re)).all()
        for post in reply_tree:
            post.slug = new_slug[0] + post.slug[len(old_slug[0]):]
            post.full_slug = new_slug[1] + post.slug[len(old_slug[1]):]
            post.discussion_id = self.discussion_id
            post.thread_id = self.thread_id
        for post in [self] + reply_tree:
            for att in post.attachments:
                att.discussion_id = self.discussion_id
                att.thread_id = self.thread_id


class ForumAttachment(DiscussionAttachment):
    DiscussionClass = Forum
    ThreadClass = ForumThread
    PostClass = ForumPost

    class __mongometa__:
        polymorphic_identity = 'ForumAttachment'

    attachment_type = FieldProperty(str, if_missing='ForumAttachment')



