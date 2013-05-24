import logging
from datetime import datetime
from ming.utils import LazyProperty

import pymongo
from pylons import tmpl_context as c, app_globals as g

from ming import schema
from ming.odm.base import session
from ming.odm import (
    FieldProperty,
    RelationProperty,
    ForeignIdProperty,
    Mapper
)

from vulcanforge.artifact.model import (
    Artifact,
    Feed,
    Snapshot,
    Message,
    VersionedArtifact,
    BaseAttachment
)
from vulcanforge.auth.model import User
from vulcanforge.common.helpers import urlquote, ago
from vulcanforge.common.util import nonce
from vulcanforge.notification.util import gen_message_id

LOG = logging.getLogger(__name__)


class Discussion(Artifact):
    class __mongometa__:
        name = 'discussion'
    type_s = 'Discussion'

    parent_id = FieldProperty(schema.Deprecated)
    shortname = FieldProperty(str)
    name = FieldProperty(str)
    description = FieldProperty(str, if_missing='')
    num_topics = FieldProperty(int, if_missing=0)
    num_posts = FieldProperty(int, if_missing=0)
    subscriptions = FieldProperty({str: bool})

    threads = RelationProperty('Thread')
    posts = RelationProperty('Post')

    def __json__(self):
        return dict(
            _id=str(self._id),
            shortname=self.shortname,
            name=self.name,
            description=self.description,
            threads=[dict(_id=t._id, subject=t.subject)
                     for t in self.threads])

    @classmethod
    def thread_class(cls):
        return cls.threads.related

    @classmethod
    def post_class(cls):
        return cls.posts.related

    @classmethod
    def attachment_class(cls):
        return DiscussionAttachment

    def update_stats(self):
        self.num_topics = self.thread_class().query.find(
            dict(discussion_id=self._id)).count()
        self.num_posts = self.post_class().query.find(
            dict(discussion_id=self._id, status='ok')).count()

    @property
    def last_post(self):
        q = self.post_class().query.find({
            'discussion_id': self._id
        }).sort('timestamp', pymongo.DESCENDING)
        return q.first()

    def url(self):
        return self.app.url + '_discuss/'

    def shorthand_id(self):
        return self.shortname

    def index(self, **kw):
        return Artifact.index(
            self,
            type_s=self.type_s,
            title_s='Discussion: %s' % self.name,
            name_s=self.name,
            text_objects=[
                self.name,
                self.description,
            ],
            **kw
        )

    def subscription(self):
        return self.subscriptions.get(str(c.user._id))

    def delete(self):
        # Delete all the threads, posts, and artifacts
        # delete them by calling delete() on each instance instead of remove()
        # to ensure session hooks are called
        query_sets = [
            self.thread_class().query,
            self.post_class().query,
        ]
        query_params = {'discussion_id': self._id}
        for q in query_sets:
            for obj in q.find(query_params):
                obj.delete()
        self.attachment_class().remove(query_params)
        super(Discussion, self).delete()

    def find_posts(self, **kw):
        q = dict(kw, discussion_id=self._id)
        return self.post_class().query.find(q)


class AbstractThread(Artifact):

    class __mongometa__:
        name = 'abstract_thread'

    type_s = 'Thread'

    _id = FieldProperty(str, if_missing=lambda: nonce(8))
    subject = FieldProperty(str, if_missing='')
    num_replies = FieldProperty(int, if_missing=0)
    num_views = FieldProperty(int, if_missing=0)
    subscriptions = FieldProperty({str: bool})
    last_post_date = FieldProperty(datetime, if_missing=datetime(1970, 1, 1))
    posts = RelationProperty('Post', via='thread_id')

    first_post_id = ForeignIdProperty('Post')
    first_post = RelationProperty('Post', via='first_post_id')
    discussion_id = ForeignIdProperty(Discussion)

    def __json__(self):
        return dict(
            _id=self._id,
            discussion_id=str(self.discussion_id),
            subject=self.subject,
            posts=[
                dict(slug=p.slug, subject=p.subject) for p in self.posts
            ]
        )

    @staticmethod
    def discussion_class():
        return None

    @staticmethod
    def post_class():
        return None

    @property
    def artifact(self):
        return None

    def get_discussion_thread(self, data=None, generate_if_missing=True):
        """For Indexing"""
        return self

    # Use wisely - there's .num_replies also
    @LazyProperty
    def post_count(self):
        return self.post_class().query.find(dict(
            discussion_id=self.discussion_id,
            thread_id=self._id)
        ).count()

    def add_post(self, **kw):
        """Helper function to avoid code duplication."""
        p = self.post(**kw)
        p.commit()
        self.num_replies += 1
        if not self.first_post:
            self.first_post_id = p._id
        Feed.post(self, title=p.subject, description=p.text)
        return p

    def update_stats(self):
        self.num_replies = self.post_class().query.find(
            dict(thread_id=self._id, status='ok')).count() - 1

    @property
    def last_post(self):
        q = self.post_class().query.find(dict(
            thread_id=self._id)).sort('timestamp', pymongo.DESCENDING)
        return q.first()

    def create_post_threads(self, posts):
        result = []
        post_index = {}
        for p in sorted(posts, key=lambda p: p.full_slug):
            pi = dict(post=p, children=[])
            post_index[p._id] = pi
            if p.parent_id in post_index:
                post_index[p.parent_id]['children'].append(pi)
            else:
                result.append(pi)
        return result

    def query_posts(self, page=None, limit=None, timestamp=None,
                    style='threaded'):
        if timestamp:
            terms = dict(discussion_id=self.discussion_id,
                         thread_id=self._id,
                         status='ok', timestamp=timestamp)
        else:
            terms = dict(discussion_id=self.discussion_id,
                         thread_id=self._id,
                         status='ok')
        q = self.post_class().query.find(terms)
        if style == 'threaded':
            q = q.sort('full_slug')
        else:
            q = q.sort('timestamp')
        if page is not None:
            q = q.skip(page*limit)
        if limit is not None:
            q = q.limit(limit)
        return q

    def find_posts(self, page=None, limit=25, timestamp=None,
                   style='threaded'):
        return self.query_posts(
            page=page,
            limit=limit,
            timestamp=timestamp,
            style=style
        ).all()

    def top_level_posts(self):
        return self.post_class().query.find(dict(
            thread_id=self._id,
            parent_id=None,
            status='ok'))

    def url(self):
        # Can't use self.discussion because it might change during the req
        discussion = self.discussion_class().query.get(_id=self.discussion_id)
        return discussion.url() + 'thread/' + str(self._id) + '/'

    def shorthand_id(self):
        return self._id

    def post(self, text, message_id=None, parent_id=None, timestamp=None, **kw):
        g.security.require_access(self, 'post')
        if message_id is None:
            message_id = gen_message_id()
        parent = parent_id and self.post_class().query.get(_id=parent_id)
        slug, full_slug = self.post_class().make_slugs(parent, timestamp)
        kwargs = dict(
            discussion_id=self.discussion_id,
            full_slug=full_slug,
            slug=slug,
            thread_id=self._id,
            parent_id=parent_id,
            text=text,
            status='pending'
        )
        if timestamp is not None:
            kwargs['timestamp'] = timestamp
        if message_id is not None:
            kwargs['_id'] = message_id
        post = self.post_class()(**kwargs)
        if g.security.has_access(self, 'unmoderated_post'):
            LOG.info('Auto-approving message from %s', c.user.username)
            post.approve()
        return post

    def delete(self):
        self.post_class().query.remove(dict(thread_id=self._id))
        self.attachment_class().remove(dict(thread_id=self._id))
        Artifact.delete(self)

    def _get_subscription(self):
        return self.subscriptions.get(str(c.user._id))
    def _set_subscription(self, value):
        if value:
            self.subscriptions[str(c.user._id)] = True
        else:
            self.subscriptions.pop(str(c.user._id), None)
    subscription = property(_get_subscription, _set_subscription)


class Thread(AbstractThread):

    class __mongometa__:
        name = 'thread'
        polymorphic_on = 'kind'
        polymorphic_identity = 'thread'
        indexes = [
            ('ref_id',),
            ('ref_id', 'app_config_id'),
            (('app_config_id', pymongo.ASCENDING),
             ('last_post_date', pymongo.DESCENDING),
             ('mod_date', pymongo.DESCENDING)),
        ]
    type_s = 'Thread'

    ref_id = ForeignIdProperty('ArtifactReference')
    kind = FieldProperty(str, if_missing='thread')
    artifact_reference = FieldProperty(schema.Deprecated)
    artifact_id = FieldProperty(schema.Deprecated)

    discussion = RelationProperty(Discussion)
    ref = RelationProperty('ArtifactReference')

    def index(self, *args, **kw):
        """Don't need to index these"""
        return None

    @staticmethod
    def discussion_class():
        return Discussion

    @staticmethod
    def post_class():
        return Post

    @classmethod
    def attachment_class(cls):
        return DiscussionAttachment

    @property
    def artifact(self):
        if self.ref:
            return self.ref.artifact
        return self.discussion

    def primary(self):
        return self.artifact

    def post(self, *args, **kw):
        post = AbstractThread.post(self, *args, **kw)
        if self.artifact:
            self.artifact.autosubscribe()
        return post


class PostHistory(Snapshot):
    class __mongometa__:
        name = 'post_history'

    artifact_id = ForeignIdProperty('Post')

    @classmethod
    def post_class(cls):
        return cls.artifact_id.related

    def original(self):
        return self.post_class().query.get(_id=self.artifact_id)

    def shorthand_id(self):
        original = self.original()
        if original:
            return '%s#%s' % (original.shorthand_id(), self.version)
        else:
            return None

    def url(self):
        if self.original():
            return self.original().url() + '?version=%d' % self.version
        else:
            return None

    def index(self, **kw):
        return super(PostHistory, self).index(
            type_s='Post Snapshot',
            text_objects=[
                self.data.text,
            ],
            **kw
        )


class AbstractPost(Message, VersionedArtifact):

    class __mongometa__:
        name = 'abstractpost'
        indexes = ['discussion_id', 'thread_id']

    type_s = 'Post'

    thread_id = ForeignIdProperty(Thread)
    discussion_id = ForeignIdProperty(Discussion)
    subject = FieldProperty(schema.Deprecated)
    status = FieldProperty(
        schema.OneOf('ok', 'pending', 'spam', if_missing='pending')
    )
    flagged_by = FieldProperty([schema.ObjectId])
    flags = FieldProperty(int, if_missing=0)
    last_edit_date = FieldProperty(datetime, if_missing=None)
    last_edit_by_id = ForeignIdProperty(User)
    edit_count = FieldProperty(int, if_missing=0)

    thread = RelationProperty(Thread)
    discussion = RelationProperty(Discussion)

    def __json__(self):
        author = self.author()
        return dict(
            _id=str(self._id),
            thread_id=self.thread_id,
            slug=self.slug,
            subject=self.subject,
            status=self.status,
            text=self.text,
            flagged_by=map(str, self.flagged_by),
            timestamp=self.timestamp,
            author_id=str(author._id),
            author=author.username)

    def index(self, **kw):
        return super(AbstractPost, self).index(
            type_s=self.type_s,
            title_s='Post by %s on %s' % (
                self.author().username, self.subject),
            name_s=self.subject,
            text_objects=[
                self.text,
                self.subject,
                ],
            **kw
        )

    def get_discussion_thread(self, **kw):
        return None

    def get_link_content(self):
        return self.text

    def index_parent(self):
        return self.primary()

    @classmethod
    def discussion_class(cls):
        return cls.discussion.related

    @classmethod
    def thread_class(cls):
        return cls.thread.related

    @classmethod
    def attachment_class(cls):
        raise NotImplementedError

    @property
    def parent(self):
        return self.query.get(_id=self.parent_id)

    @property
    def subject(self):
        subject = None
        if self.thread:
            subject = self.thread.subject
            if not subject:
                artifact = self.thread.artifact
                if artifact:
                    subject = getattr(artifact, 'email_subject', '')
        return subject or '(no subject)'

    @property
    def attachments(self):
        return self.attachment_class().query.find(dict(
            post_id=self._id, type='attachment'))

    def last_edit_by(self):
        return User.query.get(_id=self.last_edit_by_id) or User.anonymous()

    def primary(self):
        if self.thread:
            return self.thread.primary()

    def summary(self):
        return '<a href="%s">%s</a> %s' % (
            self.author().url(), self.author().get_pref('display_name'),
            ago(self.timestamp))

    def absolute_url(self):
        """URL of just this post, and this post alone"""
        if self.thread:
            return self.thread.url() + urlquote(self.slug) + '/'

    @property
    def id_safe_slug(self):
        return urlquote(self.slug).replace('/','')[::-1]

    def url(self):
        """URL within thread"""
        raise NotImplementedError

    def shorthand_id(self):
        if self.thread:
            return '%s#%s' % (self.thread.shorthand_id(), self.slug)
        else:  # pragma no cover
            return None

    def link_text(self):
        return self.subject

    def link_text_short(self):
        return 'Post in ' + self.subject

    def reply_subject(self):
        if self.subject and self.subject.lower().startswith('re:'):
            return self.subject
        else:
            return 'Re: ' + (self.subject or '(no subject)')

    def delete(self):
        self.attachment_class().remove(dict(post_id=self._id))
        super(AbstractPost, self).delete()

    def approve(self):
        from vulcanforge.notification.model import Notification
        if self.status == 'ok': return
        self.status = 'ok'
        if self.parent_id is None:
            thd = self.thread_class().query.get(_id=self.thread_id)
            g.post_event('discussion.new_thread', thd._id)
        author = self.author()
        g.security.simple_grant(
            self.acl, c.project.project_role(author)._id, 'moderate')
        self.commit()
        if (c.app.config.options.get('PostingPolicy') == 'ApproveOnceModerated'
            and author._id != None):
            g.security.simple_grant(
                self.acl,
                c.project.project_role(author)._id,
                'unmoderated_post')
        g.post_event('discussion.new_post', self.thread_id, self._id)
        artifact = self.thread.artifact or self.thread
        Notification.post(artifact, 'message', post=self)
        session(self).flush()
        self.thread.last_post_date = max(
            self.thread.last_post_date,
            self.mod_date)
        self.thread.update_stats()
        self.discussion.update_stats()

    def spam(self):
        self.status = 'spam'
        g.post_event('spam', self.index_id())


class Post(AbstractPost):

    class __mongometa__:
        name = 'post'
        polymorphic_on = 'kind'
        polymorphic_identity = 'post'
        history_class = PostHistory

    kind = FieldProperty(str, if_missing='post')

    def url(self):
        if self.thread and self.thread.artifact:
            return self.thread.artifact.url() + '#' + self.id_safe_slug

    @classmethod
    def attachment_class(cls):
        return DiscussionAttachment


class DiscussionAttachment(BaseAttachment):
    DiscussionClass = Discussion
    ThreadClass = Thread
    PostClass = Post
    ArtifactClass = Post

    class __mongometa__:
        polymorphic_identity = 'DiscussionAttachment'
        indexes = ['filename', 'discussion_id', 'thread_id', 'post_id']

    discussion_id = FieldProperty(schema.ObjectId)
    thread_id = FieldProperty(str)
    post_id = FieldProperty(str)
    artifact_id = FieldProperty(str)
    attachment_type = FieldProperty(str, if_missing='DiscussionAttachment')

    @property
    def discussion(self):
        return self.DiscussionClass.query.get(_id=self.discussion_id)

    @property
    def thread(self):
        return self.ThreadClass.query.get(_id=self.thread_id)

    @property
    def post(self):
        return self.PostClass.query.get(_id=self.post_id)

    @property
    def artifact(self):
        """Get associated artifact. Used for acl purposes"""
        artifact = None
        if self.post_id:
            artifact = self.post
        if artifact is None and self.thread_id:
            artifact = self.thread
        if artifact is None:
            artifact = self.discussion
        return artifact

    @classmethod
    def metadata_for(cls, post):
        return dict(
            post_id=post._id,
            thread_id=post.thread_id,
            discussion_id=post.discussion_id,
            app_config_id=post.app_config_id)

    def local_url(self):
        if self.post_id:
            prefix = self.artifact.absolute_url()
        else:
            prefix = self.artifact.url()
        return prefix + 'attachment/' + urlquote(self.filename)



