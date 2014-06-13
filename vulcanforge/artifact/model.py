import logging
from collections import defaultdict
from datetime import datetime
from pprint import pformat
import re
import bson

from pylons import tmpl_context as c, app_globals as g, request
from webhelpers import feedgenerator as FG
import tg
import pymongo
from ming import schema as S
from ming.odm import state, session
from ming.odm import (
    FieldProperty,
    ForeignIdProperty,
    RelationProperty
)
from ming.odm.declarative import MappedClass
from ming.utils import LazyProperty

from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.s3.model import File
from vulcanforge.common.model.session import (
    artifact_orm_session,
    project_orm_session,
    main_orm_session,
    visualizable_orm_session,
    visualizable_artifact_session)
from vulcanforge.common.helpers import absurl, urlquote
from vulcanforge.common.util import nonce
from vulcanforge.common.util.filesystem import import_object
from vulcanforge.auth.model import User
from vulcanforge.auth.schema import ACL
from vulcanforge.project.model import Project
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.notification.util import gen_message_id
from vulcanforge.taskd import model_task
from vulcanforge.visualize.base import VisualizableMixIn

LOG = logging.getLogger(__name__)


class ArtifactApiMixin(object):
    """Objects that behave as artifacts within the forge need to
    implement this

    """
    preview_url = None
    link_type = 'generic'

    @property
    def project(self):
        if self.app_config:
            return self.app_config.project

    @property
    def project_id(self):
        if self.app_config:
            return self.app_config.project_id

    def url(self):  # pragma no cover
        """
        Subclasses should implement this, providing the URL to the artifact

        """
        raise NotImplementedError('url')

    def index_id(self):
        """
        Globally unique artifact identifier.

        Used for SOLR ID, shortlinks, and maybe elsewhere

        """
        raise NotImplementedError('index_id')

    def shorthand_id(self):
        """
        How to refer to this artifact within the app instance context.

        For a wiki page, it might be the title.  For a ticket, it might be the
        ticket number.  For a discussion, it might be the message ID. Generally
        this should have a strong correlation to the URL.

        """
        raise NotImplementedError('shorthand_id')

    def s3_key_prefix(self):
        return self.shorthand_id()

    def link_text(self):
        """
        The link text that will be used when a shortlink to this artifact
        is expanded into an <a></a> tag.

        By default this method returns shorthand_id(). Subclasses should
        override this method to provide more descriptive link text.

        """
        return self.shorthand_id()

    def link_text_short(self):
        """
        Shortened version of the link text. Defaults to same as link_text.

        Used for ReferenceBin
        @return: str
        """
        return self.link_text()

    def parent_security_context(self):
        """ACL processing should continue at the  AppConfig object. This lets
        AppConfigs provide a 'default' ACL for all artifacts in the tool."""
        return self.app_config

    def primary(self):
        """
        If an artifact is a "secondary" artifact (discussion of a ticket, for
        instance), return the artifact that is the "primary".

        """
        return self

    @LazyProperty
    def ref(self):
        return ArtifactReference.query.get(_id=self.index_id())

    @LazyProperty
    def refs(self):
        refs = []
        if self.ref:
            refs = [r['index_id'] for r in self.ref.references]
        return refs

    @LazyProperty
    def backrefs(self):
        q = ArtifactReference.query.find({
            'references.index_id': self.index_id()
        })
        return [aref._id for aref in q]

    def get_content_to_folder(self, path):
        raise NotImplementedError('get_content_to_folder')

    def relations(self):
        """
        generator for related artifacts with link context

        (extra field in ArtifactReference.references)

        """
        seen = set()
        # get backreferences to this artifact
        index_id = self.index_id()
        q = ArtifactReference.query.find({'references.index_id': index_id})
        for backref in q:
            if backref.artifact:
                for ref in filter(lambda r: r['index_id'] == index_id,
                        backref.references):
                    artifact = backref.artifact.primary()
                    if artifact.index_id() not in seen:
                        seen.add(artifact.index_id())
                        yield dict(
                            artifact=artifact,
                            index_id=backref._id,
                            datetime=ref.datetime
                        )

        if not self.ref:
            raise StopIteration()

        # get this artifacts references
        for ref in self.ref.references:
            artifact = ArtifactReference.artifact_by_index_id(ref['index_id'])
            if artifact:
                artifact = artifact.primary()
                seen.add(artifact.index_id())
                yield dict(artifact=artifact, **ref)

    def has_relations(self):
        """returns boolean"""
        return bool(
            (self.ref and self.ref.references) or
            ArtifactReference.query.find({
                'references.index_id': self.index_id()}).count()
        )

    def ref_category(self):
        """
        Category for grouping types of relations

        @return: str
        """
        return self.app_config.options.mount_label

    def raw_url(self):
        """
        Url at which to download the resource.

        @return: str

        """
        return self.url()

    def get_discussion_thread(self, data=None, generate_if_missing=True):
        """
        Return the discussion thread for this artifact (possibly made more
        specific by the message_data)

        @rtype: vulcanforge.discussion.model.Thread
        """
        app = self.app_config.instantiate()
        thread_class = app.DiscussionClass.thread_class()
        thread = thread_class.query.get(ref_id=self.index_id())
        if thread is None and generate_if_missing:
            idx = self.index() or {}
            thread = thread_class(
                app_config_id=self.app_config_id,
                discussion_id=self.app_config.discussion_id,
                ref_id=idx.get('id', self.index_id()),
                subject='%s discussion' % idx.get('title_s', self.link_text()))
            thread.flush_self()
        return thread

    @LazyProperty
    def discussion_thread(self):
        return self.get_discussion_thread()


class Artifact(BaseMappedClass, ArtifactApiMixin):
    """
    The base class for anything you want to keep track of.

    It will automatically be added to solr (see index() method).  It also
    gains a discussion thread and can have files attached to it.

    :var tool_version: default's to the app's version
    :var acl: dict of permission name => [roles]
    :var labels: list of plain old strings

    """

    class __mongometa__:
        session = artifact_orm_session
        name = 'artifact'
        indexes = ['app_config_id']

        def before_save(data):
            sesh = artifact_orm_session._get()
            if not getattr(sesh, 'skip_mod_date', False):
                data['mod_date'] = datetime.utcnow()
            else:
                LOG.debug('Not updating mod_date')
            #if hasattr(c, 'project') and c.project:
            #    c.project.last_updated = datetime.utcnow()

    type_s = 'Generic Artifact'

    # Artifact base schema
    mod_date = FieldProperty(datetime, if_missing=datetime.utcnow)
    app_config_id = ForeignIdProperty(
        'AppConfig', if_missing=lambda: c.app.config._id)
    tool_version = FieldProperty(
        {str: str},
        if_missing=lambda: {c.app.config.tool_name: c.app.__version__}
    )
    acl = FieldProperty(ACL)
    labels = FieldProperty([str])
    app_config = RelationProperty('AppConfig')
    preview_url = FieldProperty(str, if_missing=None)

    @classmethod
    def attachment_class(cls):  # pragma no cover
        raise NotImplementedError('attachment_class')

    @classmethod
    def translate_query(cls, q, fields):
        for f in fields:
            for e in g.search.dynamic_postfixes:
                if f.endswith(e):
                    base = f[:-len(e)]
                    actual = f
                    q = q.replace(base + ':', actual + ':')
                    break
        return q

    @LazyProperty
    def ref(self):
        return ArtifactReference.from_artifact(self)

    def index_id(self):
        index_id = '%s.%s#%s' % (
            self.__class__.__module__, self.__class__.__name__, self._id)
        return index_id.replace('.', '/')

    def shorthand_id(self):
        return str(self._id)  # pragma no cover

    def s3_key_prefix(self):
        return str(self._id)

    def related_artifacts(self):
        related_artifacts = []
        for ref_id in self.refs + self.backrefs:
            artifact = ArtifactReference.artifact_by_index_id(ref_id)
            if artifact is None:
                continue
            artifact = artifact.primary()
            if artifact not in related_artifacts:
                related_artifacts.append(artifact)
        return related_artifacts

    def subscribe(self, user=None, topic=None, type='direct', n=1, unit='day'):
        from vulcanforge.notification.model import Mailbox
        if user is None:
            user = c.user
        Mailbox.subscribe(
            user_id=user._id,
            project_id=self.app_config.project_id,
            app_config_id=self.app_config._id,
            artifact=self, topic=topic,
            type=type, n=n, unit=unit)

    def unsubscribe(self, user=None):
        from vulcanforge.notification.model import Mailbox
        if user is None:
            user = c.user
        Mailbox.unsubscribe(
            user_id=user._id,
            project_id=self.app_config.project_id,
            app_config_id=self.app_config._id,
            artifact_index_id=self.index_id())

    def autosubscribe(self, user=None, *args, **kwargs):
        if user is None:
            user = c.user
        if user.get_pref('autosubscribe'):
            return self.subscribe(user=user, *args, **kwargs)

    @classmethod
    def artifacts_labeled_with(cls, label):
        return cls.query.find({'labels': label})

    def email_link(self, subject='artifact'):
        if subject:
            return 'mailto:%s?subject=[%s:%s:%s] Re: %s' % (
                self.email_address,
                self.app_config.project.shortname,
                self.app_config.options.mount_point,
                self.shorthand_id(),
                subject)
        else:
            return 'mailto:%s' % self.email_address

    @property
    def email_address(self):
        return tg.config.get(
            'forgemail.return_path', 'noreply@vulcanforge.org')

    @LazyProperty
    def app(self):
        if getattr(c, 'app', None) and c.app.config._id == self.app_config._id:
            return c.app
        else:
            return self.app_config.instantiate()

    def index(self, text_objects=None, use_posts=True, **kwargs):
        """
        TODO: update docstring

        Subclasses should override this, providing a dictionary of
        solr_field => value.
        These fields & values will be stored by solr.  Subclasses should call
        the this and extend it with more fields.  All these fields will be
        included in the 'text' field (done by search.solarize())

        The _s and _t suffixes, for example, follow solr dynamic field naming
        pattern.
        You probably want to override at least title_s and text to have
        meaningful search results and email senders.
        """
        if text_objects is None:
            text_objects = []
        index = dict(
            id=self.index_id(),
            mod_date_dt=self.mod_date,
            title_s='Artifact %s' % self._id,
            project_id_s=str(self.project._id),
            project_name_t=self.project.name,
            project_shortname_t=self.project.shortname,
            tool_name_s=self.app_config.tool_name,
            mount_point_s=self.app_config.options.mount_point,
            app_config_id_s=self.app_config_id,
            is_history_b=False,
            url_s=self.url(),
            read_roles=self.get_read_roles(),
            type_s=self.type_s,
            labels_t=' '.join(l for l in self.labels),
            snippet_s='',
            can_reference_b=True,
            post_text_s=''
        )
        index.update(**kwargs)

        # FIX: for objects with incorrect read roles:
        if not len(index['read_roles']):
            index['read_roles'] = ['authenticated']

        # no text, generate a sensible default
        if 'text' not in index and not text_objects:
            index['text'] = u" ".join(
                str(pformat(v)) for k, v in index.iteritems()
                if k in g.index_default_text_fields
            )

        # add discussion threads
        if use_posts:
            thread = self.get_discussion_thread(generate_if_missing=False)
            if thread:
                for post in thread.query_posts():
                    author = post.author()
                    text_objects.append(
                        u"{} {} {}".format(author.display_name,
                                           author.username,
                                           post.text)
                    )

        # append these objects to the text
        index['text'] = index.get('text', '') + " ".join(str(
            x.encode('ascii', "xmlcharrefreplace") if type(x) == unicode else x
            ) for x in text_objects)

        return index

    @LazyProperty
    def link_content(self):
        return self.get_link_content()

    def get_link_content(self):
        """
        Text content that contains the artifacts shortlinks

        Used for parsing references

        """
        # TODO: fix subclasses of artifacts to use this instead of index
        index_dict = self.index(use_posts=False)
        if index_dict:
            return index_dict.get('text')

    def index_parent(self):
        """
        For artifacts whose parent indexes should be updated when they are
        updated (e.g. Posts)
        @return: artifact | None
        """
        return None

    def attach(self, filename, fp, **kw):
        att = self.attachment_class().save_attachment(
            filename=filename, fp=fp, artifact_id=self._id, **kw)
        return att

    def get_read_roles(self):
        """
        It can only be more restrictive than the project read roles
        @return:
        """
        return g.security.roles_with_permission(self, 'read')


class Snapshot(Artifact):
    """
    A snapshot of an :class:`Artifact <vulcanforge.artifact.model.Artifact>`,
    used in
    :class:`VersionedArtifact <vulcanforge.artifact.model.VersionedArtifact>`

    """
    class __mongometa__:
        session = artifact_orm_session
        name = 'artifact_snapshot'
        unique_indexes = [('artifact_class', 'artifact_id', 'version')]
        indexes = [('artifact_id', 'version')]

    _id = FieldProperty(S.ObjectId)
    artifact_id = FieldProperty(S.ObjectId)
    artifact_class = FieldProperty(str)
    version = FieldProperty(S.Int, if_missing=0)
    author = FieldProperty({
        'id': S.ObjectId,
        'username': str,
        'display_name': str,
        'logged_ip': str
    })
    timestamp = FieldProperty(datetime)
    data = FieldProperty(None)

    def index(self, text_objects=None, **kwargs):
        if text_objects is None:
            text_objects = []
        index = dict()
        original = self.original()
        original_text = []
        if original:
            index = original.index()
            original_text = index.pop('text')
            index['title_s'] = 'Version %d of %s' % (
                    self.version, index['title_s'])
        index.update(
            id=self.index_id(),
            version_i=self.version,
            author_username_t=self.author.username,
            author_display_name_t=self.author.display_name,
            timestamp_dt=self.timestamp,
            is_history_b=True)
        index.update(kwargs)
        index['text_objects'] = text_objects + [original_text] + [
            self.author.username,
            self.author.display_name,
        ]

        return super(Snapshot, self).index(**index)

    def is_current(self):
        return not bool(self.__class__.query.get(
            version=self.version + 1,
            artifact_id=self.artifact_id,
            artifact_class=self.artifact_class
        ))

    def original(self):
        raise NotImplemented('original')  # pragma no cover

    def get_link_content(self):
        return None

    def shorthand_id(self):
        return '%s#%s' % (self.original().shorthand_id(), self.version)

    @property
    def author_user(self):
        if self.author:
            return User.query.get(_id=self.author.id)

    def __getattr__(self, name):
        return getattr(self.data, name)


class VersionedArtifact(Artifact):
    """
    An :class:`Artifact <vulcanforge.artifact.model.Artfiact>` that has versions.
    Associated data like attachments and discussion thread are not versioned.
    """
    class __mongometa__:
        session = artifact_orm_session
        name = 'versioned_artifact'
        history_class = Snapshot
        indexes = [('last_updated', pymongo.DESCENDING)]

    version = FieldProperty(S.Int, if_missing=0)
    last_updated = FieldProperty(S.DateTime, if_missing=datetime.utcnow)

    def commit(self):
        """Save off a snapshot of the artifact and increment the version #"""
        session(self.__class__).flush(self)
        obj = self.__class__.query.find_and_modify(
            query=dict(_id=self._id),
            update={'$inc': {'version': 1}},
            new=True)

        now = datetime.utcnow()
        self.version = obj.version
        self.last_updated = now

        try:
            ip_address = request.headers.get(
                'X_FORWARDED_FOR',
                request.remote_addr
            )
            ip_address = ip_address.split(',')[0].strip()
        except:
            ip_address = '0.0.0.0'

        try:
            artifact_state = self.state()
        except:
            artifact_state = state(self).clone()

        data = dict(
            artifact_id=self._id,
            artifact_class='%s.%s' % (
                self.__class__.__module__,
                self.__class__.__name__),
            version=self.version,
            author=dict(
                id=c.user._id,
                username=c.user.username,
                display_name=c.user.get_pref('display_name'),
                logged_ip=ip_address),
            timestamp=now,
            data=artifact_state)
        ss = self.__mongometa__.history_class(**data)
        session(ss).insert_now(ss, state(ss))
        LOG.info('Snapshot version %s of %s',
                 self.version, self.__class__)
        return ss

    def get_version(self, n):
        if n < 0:
            n = self.version + n + 1
        ss = self.__mongometa__.history_class.query.get(
            artifact_id=self._id,
            version=n
        )
        if ss is None:
            raise IndexError(n)
        return ss

    def revert(self, version):
        ss = self.get_version(version)
        old_version = self.version
        for k, v in ss.data.iteritems():
            setattr(self, k, v)
        self.version = old_version

    def history(self):
        history_cls = self.__mongometa__.history_class
        q = history_cls.query.find(dict(
            artifact_id=self._id
        )).sort('version', pymongo.DESCENDING)
        return q

    def is_current(self):
        return True


class Message(Artifact):
    """
    A message

    :var _id: an email friendly (e.g. message-id) string id
    :var slug: slash-delimeted random identifier.  Slashes useful for threaded
               searching and ordering
    :var full_slug: string of slash-delimited "timestamp:slug" components.
                    Useful for sorting by timstamp

    """

    class __mongometa__:
        session = artifact_orm_session
        name = 'message'
        indexes = Artifact.__mongometa__.indexes + [
            'slug',
            'parent_id',
            'timestamp'
        ]

    type_s = 'Generic Message'

    _id = FieldProperty(str, if_missing=gen_message_id)
    slug = FieldProperty(str, if_missing=nonce)
    full_slug = FieldProperty(str, if_missing=None)
    parent_id = FieldProperty(str)
    app_id = FieldProperty(S.ObjectId, if_missing=lambda: c.app.config._id)
    timestamp = FieldProperty(datetime, if_missing=datetime.utcnow)
    author_id = FieldProperty(S.ObjectId, if_missing=lambda: c.user._id)
    text = FieldProperty(str, if_missing='')

    @classmethod
    def make_slugs(cls, parent=None, timestamp=None):
        part = nonce()
        if timestamp is None:
            timestamp = datetime.utcnow()
        dt = timestamp.strftime('%Y%m%d%H%M%S')
        slug = part
        full_slug = dt + ':' + part
        if parent:
            return (parent.slug + '/' + slug,
                    parent.full_slug + '/' + full_slug)
        else:
            return slug, full_slug

    def author(self):
        return User.query.get(_id=self.author_id) or User.anonymous()

    def reply(self):
        new_id = gen_message_id()
        slug, full_slug = self.make_slugs(self)
        new_args = dict(
            state(self).document,
            _id=new_id,
            slug=slug,
            full_slug=full_slug,
            parent_id=self._id,
            timestamp=datetime.utcnow(),
            author_id=c.user._id)
        return self.__class__(**new_args)

    def descendants(self):
        q = self.query.find(dict(slug={'$gt': self.slug})).sort('slug')
        for msg in q:
            if msg.slug.startswith(self.slug):
                yield msg
            else:
                break

    def replies(self):
        return self.query.find(dict(parent_id=self._id))

    def index(self, text_objects=None, **kwargs):
        if text_objects is None:
            text_objects = []
        author = self.author()
        index = dict()
        index.update(type_s=self.type_s,
                author_user_name_t=author.username,
                author_display_name_t=author.get_pref('display_name'),
                timestamp_dt=self.timestamp)
        index.update(kwargs)
        index['text_objects'] = text_objects + [
                author.username,
                author.get_pref('display_name'),
                self.text,
            ]

        return super(Message, self).index(**index)

    def shorthand_id(self):
        return self.slug


class Feed(MappedClass):
    """
    Used to generate rss/atom feeds.  This does not need to be extended;
    all feed items go into the same collection
    """
    class __mongometa__:
        session = project_orm_session
        name = 'artifact_feed'
        indexes = [
            'pubdate',
            ('artifact_ref.project_id', 'artifact_ref.mount_point')]

    _id = FieldProperty(S.ObjectId)
    ref_id = ForeignIdProperty('ArtifactReference')
    neighborhood_id = ForeignIdProperty(Neighborhood)
    project_id = ForeignIdProperty('Project')
    app_config_id = ForeignIdProperty('AppConfig')
    tool_name = FieldProperty(str)
    title = FieldProperty(str)
    link = FieldProperty(str)
    pubdate = FieldProperty(datetime, if_missing=datetime.utcnow)
    description = FieldProperty(str)
    unique_id = FieldProperty(str, if_missing=lambda: nonce(40))
    author_name = FieldProperty(str,
        if_missing=lambda: c.user.get_pref('display_name')
                           if hasattr(c, 'user') else None)
    author_link = FieldProperty(str,
        if_missing=lambda: c.user.url() if hasattr(c, 'user') else None)
    artifact_reference = FieldProperty(S.Deprecated)

    @classmethod
    def post(cls, artifact, title=None, description=None, author=None,
             author_link=None, author_name=None):
        """
        Create a Feed item and returns the item.

        If anon doesn't have read access, create does not happen and None
        is returned
        """
        # TODO: fix security system so we can do this correctly and fast
        anon = User.anonymous()
        if not g.security.has_access(artifact, 'read', user=anon):
            return
        if not g.security.has_access(c.project, 'read', user=anon):
            return
        idx = artifact.index()
        if title is None:
            title = '%s modified by %s' % (
                idx['title_s'], c.user.get_pref('display_name'))
        if description is None:
            description = title
        if author is None:
            author = c.user
        item = cls(
            ref_id=artifact.index_id(),
            neighborhood_id=artifact.app_config.project.neighborhood_id,
            project_id=artifact.app_config.project_id,
            app_config_id=artifact.app_config_id,
            tool_name=artifact.app_config.tool_name,
            title=title,
            description=description,
            link=artifact.url(),
            author_name=author_name or author.get_pref('display_name'),
            author_link=author_link or author.url())
        return item

    @classmethod
    def feed(cls, q, feed_type, title, link, description,
             since=None, until=None, offset=None, limit=None):
        """Produces webhelper.feedgenerator Feed"""
        d = dict(
            title=title,
            link=absurl(link),
            description=description,
            language=u'en'
        )
        if feed_type == 'atom':
            feed = FG.Atom1Feed(**d)
        elif feed_type == 'rss':
            feed = FG.Rss201rev2Feed(**d)
        query = defaultdict(dict)
        query.update(q)
        if since is not None:
            query['pubdate']['$gte'] = since
        if until is not None:
            query['pubdate']['$lte'] = until
        cur = cls.query.find(query)
        cur = cur.sort('pubdate', pymongo.DESCENDING)
        if limit is None:
            limit = 10
        query = cur.limit(limit)
        if offset is not None:
            query = cur.skip(offset)
        for r in query:
            feed.add_item(title=r.title,
                          link=absurl(r.link.encode('utf-8')),
                          pubdate=r.pubdate,
                          description=r.description,
                          unique_id=r.unique_id,
                          author_name=r.author_name,
                          author_link=absurl(r.author_link))
        return feed


class BaseAttachment(File, VisualizableMixIn):
    thumbnail_size = (96, 96)
    ArtifactType = None
    visualizable_kind = 'attachment'

    class __mongometa__:
        name = 'attachment'
        polymorphic_on = 'attachment_type'
        polymorphic_identity = None
        session = visualizable_orm_session
        indexes = ['artifact_id', 'app_config_id'] + File.__mongometa__.indexes

    artifact_id = FieldProperty(S.ObjectId)
    app_config_id = FieldProperty(S.ObjectId)
    type = FieldProperty(str)
    attachment_type = FieldProperty(str)

    @property
    def artifact(self):
        return self.ArtifactType.query.get(_id=self.artifact_id)

    def local_url(self):
        """Forge-local URL (not s3. Generally one should use File.url)"""
        filename = self.filename
        if self.is_thumb:
            filename += '/thumb'
        return self.artifact.url() + 'attachment/' + urlquote(filename)

    def is_embedded(self):
        return self.filename in request.environ.get(
            'vehicleforge.macro.att_embedded', [])

    @classmethod
    def metadata_for(cls, artifact):
        return {
            'artifact_id': artifact._id,
            'app_config_id': artifact.app_config_id
        }

    @classmethod
    def save_attachment(cls, filename, fp, content_type=None, **kwargs):
        original_meta = dict(type="attachment", app_config_id=c.app.config._id)
        original_meta.update(kwargs)

        if cls.file_is_image(filename, content_type):
            thumbnail_meta = {
                'type': "thumbnail",
                'app_config_id': c.app.config._id
            }
            thumbnail_meta.update(kwargs)
            orig, thumbnail = cls.save_image(
                filename, fp,
                content_type=content_type,
                square=True,
                thumbnail_size=cls.thumbnail_size,
                thumbnail_meta=thumbnail_meta,
                save_original=True,
                original_meta=original_meta)
            if orig is not None:
                return [orig, thumbnail]
        else:
            return [
                cls.from_stream(
                    filename, fp, content_type=content_type, **original_meta)]

    def get_thumb_query_params(self):
        return {
            'filename': self.filename,
            'is_thumb': True,
            'app_config_id': self.app_config_id,
            'artifact_id': self.artifact_id
        }

    def get_unique_id(self):
        return 'attachment.{}.{}.{}'.format(
            self.attachment_type,
            self.artifact.index_id(),
            self.filename
        )

    def artifact_ref_id(self):
        return self.artifact.index_id()

    @model_task
    def trigger_vis_upload_hook(self):
        # process attachments immediately
        for visualizer in g.visualize_artifact(self).find_for_processing():
            try:
                visualizer.process_artifact(self)
            except Exception:
                LOG.exception('Error running on_upload hook on %s in %s',
                              self.get_unique_id(), visualizer.name)


# Ephemeral Functions for ArtifactReference
REPO_SHORTLINK_RE = re.compile(r'^\((?P<commit>[a-z0-9]+)\)(?P<path>/.*)')
REPO_INDEX_ID_RE = re.compile(r'^Repo\.')
SHORTLINK_RE = re.compile(r'(?<![\[])\[((([^\]]*?):)?(([^\]]*?):)?([^\]]+))\]')


def repo_get_by_index_id(index_id, match=None):
    artifact = None
    try:
        _, ac_id, ci_oid, path = index_id.split('.', 3)
        with g.context_manager.push(app_config_id=bson.ObjectId(ac_id)):
            ci = c.app.repo.commit(ci_oid)
            if ci:
                artifact = ci.get_path(path)
    except Exception:
        LOG.warn('Error looking up repo? index_id {}'.format(index_id))
        pass
    return artifact


def _get_by_slink_with_context(repo, ci_oid, path):
    ci = repo.commit(ci_oid)
    if ci:
        return ci.get_path(path)


def repo_get_by_shortlink(parsed_link, match):
    artifact = None
    ci_oid, path = match.group('commit'), match.group('path')
    project = Project.query.get(shortname=parsed_link['project'])
    if project:
        if parsed_link['app']:
            app = project.app_instance(parsed_link['app'])
            if app and hasattr(app, 'repo'):
                artifact = _get_by_slink_with_context(app.repo, ci_oid, path)
        else:
            for ac in project.app_configs:
                app = project.app_instance(ac)
                if hasattr(app, 'repo'):
                    artifact = _get_by_slink_with_context(
                        app.repo, ci_oid, path)
                    if artifact:
                        break
    return artifact


def repo_ref_id_by_link(parsed_link, match, upsert=True):
    ref_id = None
    artifact = repo_get_by_shortlink(parsed_link, match)
    if artifact:
        ref_id = artifact.index_id()
        if upsert:
            Shortlink.from_artifact(artifact)
    return ref_id


def find_shortlink_refs(text, **kw):
    ref_ids = []
    # TODO: include markdown extensions in vulcanforge then uncomment following
    #fcp = FencedCodeProcessor()
    #converted = fcp.run(text.split('\n'))
    converted = text.split('\n')
    for line in converted:
        if not line.startswith('    '):
            ref_ids.extend(
                Shortlink.ref_id_by_link(alink.group(1), **kw)
                for alink in SHORTLINK_RE.finditer(line) if alink
            )
    return ref_ids
# End Ephemerals


class ArtifactReference(BaseMappedClass):
    """
    ArtifactReference manages the artifact graph.

    fields are all strs, corresponding to Solr index_ids
    """
    class __mongometa__:
        session = main_orm_session
        name = 'artifact_reference'
        indexes = ['references.index_id', 'artifact_reference.app_config_id']

    _id = FieldProperty(str)
    artifact_reference = FieldProperty(S.Object(dict(
        module=str,
        classname=str,
        project_id=S.ObjectId,
        app_config_id=S.ObjectId,
        artifact_id=S.Anything(if_missing=None)
    )))
    references = FieldProperty([S.Object(dict(
        index_id=str,
        extra=str,  # extra label information,
        datetime=S.DateTime(if_missing=datetime.utcnow)
    ))])

    # patterns for looking up artifacts by index_id when no ArtifactReference
    # document yet exists, or the artifact is not persisted (repo objects)
    EPHEMERAL_PATTERNS = {
        REPO_INDEX_ID_RE: repo_get_by_index_id
    }

    @classmethod
    def artifact_by_index_id(cls, index_id):
        """
        Get artifact by index_id. Allows for the existence of ephemeral
        artifacts that have no ArtifactReference persisted, such as repo
        files and folders.

        """
        artifact = None

        # find ephemerals
        for regex, func in cls.EPHEMERAL_PATTERNS.iteritems():
            match = regex.match(index_id)
            if match:
                artifact = func(index_id, match)

        # standard approach
        if artifact is None:
            aref = cls.query.get(_id=index_id)
            if aref:
                artifact = aref.artifact

        return artifact

    @classmethod
    def from_artifact(cls, artifact, flush=True):
        """
        Upsert logic to generate an ArtifactReference object from an artifact

        """
        obj = cls.query.get(_id=artifact.index_id())
        if not obj:
            try:
                obj = cls(
                    _id=artifact.index_id(),
                    artifact_reference=dict(
                        module=artifact.__module__,
                        classname=artifact.__class__.__name__,
                        project_id=artifact.app_config.project_id,
                        app_config_id=artifact.app_config._id,
                        artifact_id=artifact._id),
                )
                if flush:
                    session(obj).flush(obj)
            except pymongo.errors.DuplicateKeyError:  # pragma no cover
                session(obj).expunge(obj)
                obj = cls.query.get(_id=artifact.index_id())
                session(obj).flush(obj)
        return obj

    @property
    def artifact(self):
        """Look up the artifact referenced"""
        aref = self.artifact_reference
        try:
            path = '{}:{}'.format(aref.module, aref.classname)
            cls = import_object(path)
            with g.context_manager.push(app_config_id=aref.app_config_id):
                artifact = cls.query.get(_id=aref.artifact_id)
                return artifact
        except Exception, e:
            LOG.exception('Error loading artifact for %s: %r: %s',
                          self._id, aref, e)

    def upsert_reference(self, index_id, **kwargs):
        for ref in self.references:
            if ref.index_id == index_id:
                ref.update(**kwargs)
                break
        else:
            self.references.append(dict(index_id=index_id, **kwargs))


class Shortlink(BaseMappedClass):
    """Collection mapping shorthand_ids for artifacts to ArtifactReferences"""

    class __mongometa__:
        session = main_orm_session
        name = 'shortlink'
        indexes = [
            ('link', 'project_shortname', 'app_mount'),
            ('ref_id',),
            ('app_config_id',)
        ]

    # Stored properties
    _id = FieldProperty(S.ObjectId)
    ref_id = ForeignIdProperty(ArtifactReference)
    project_id = ForeignIdProperty('Project')
    project_shortname = FieldProperty(str)
    app_config_id = ForeignIdProperty('AppConfig')
    app_mount = FieldProperty(str)
    link = FieldProperty(str)
    url = FieldProperty(str)

    # Relation Properties
    project = RelationProperty('Project')
    app_config = RelationProperty('AppConfig')
    ref = RelationProperty('ArtifactReference')

    # Regexes used to find shortlinks
    _core_re = r'''(\[
            (?:(?P<project_id>.*?):)?      # optional project ID
            (?:(?P<app_id>.*?):)?      # optional tool ID
            (?P<artifact_id>.*)             # artifact ID
    \])'''
    re_link_1 = re.compile(r'\s' + _core_re, re.VERBOSE)
    re_link_2 = re.compile(r'^' + _core_re, re.VERBOSE)

    re_link_bracket = re.compile(r'\s*\[([^\]\[]*)]\s*')

    # artifact patterns for ephemeral lookups (see same in ArtifactReference)
    EPHEMERAL_PATTERNS = {
        REPO_SHORTLINK_RE: {
            'ref_id': repo_ref_id_by_link,
            'artifact': repo_get_by_shortlink
        }
    }

    def __repr__(self):
        return u'%s -> %s' % (self.render_link(), self.ref_id)

    def render_link(self):
        return u'[{}:{}:{}]'.format(
            self.project.shortname,
            self.app_config.options.mount_point,
            self.link
        )

    @classmethod
    def lookup(cls, link):
        return cls.from_links(link)[link]

    @classmethod
    def from_artifact(cls, a, flush=True):
        result = cls.query.get(ref_id=a.index_id())
        if result is None:
            try:
                result = cls(
                    ref_id=a.index_id(),
                    project_id=a.app_config.project_id,
                    project_shortname=a.project.shortname,
                    app_config_id=a.app_config._id,
                    app_mount=a.app_config.options.mount_point)
                if flush:
                    session(result).flush(result)
            except pymongo.errors.DuplicateKeyError:  # pragma no cover
                session(result).expunge(result)
                result = cls.query.get(ref_id=a.index_id())
        result.link = a.shorthand_id()
        result.url = a.url()
        if result.link is None:
            result.delete()
            return None
        return result

    @classmethod
    def from_links(cls, *links):
        """Convert a sequence of shortlinks to matching Shortlink objects"""
        result = {}
        for link in links:
            if link not in result:
                parsed = cls._parse_link(link)
                if parsed:
                    result[link] = cls._get_from_parsed(parsed)
        return result

    @classmethod
    def _get_from_parsed(cls, parsed):
        result = None

        # assemble query
        query = {
            'link': parsed['artifact'],
            'project_shortname': parsed['project']
        }
        if parsed['app']:
            query['app_mount'] = parsed['app']
        cursor = cls.query.find(query)

        # determine link to choose if multiple options
        num = cursor.count()
        if num == 1 or not getattr(c, 'app', None):
            result = cursor.first()
        elif num > 1:
            result = cls._filter_by_context(cursor, parsed)
        return result

    @classmethod
    def _filter_by_context(cls, cursor, parsed=None):
        opts = cursor.all()
        for slink in opts:
            if slink.app_config_id == c.app.config._id:
                result = slink
                break
        else:
            # favor current project
            for slink in opts:
                if slink.project_id == c.project._id:
                    result = slink
                    break
            else:
                # favor current neighborhood
                for slink in opts:
                    if slink.project.neighborhood_id ==\
                       c.project.neighborhood_id:
                        result = slink
                        break
                else:
                    result = cursor.first()
                    LOG.warn('Ambiguous link {}'.format(parsed))
        return result

    @classmethod
    def _parse_link(cls, s):
        """Parse a shortlink into its project/app/artifact parts"""
        link_bracket_match = cls.re_link_bracket.match(s)
        if link_bracket_match:
            s = link_bracket_match.group(1)

        parts = s.split(':', 2)
        p_shortname = None
        if hasattr(c, 'project'):
            p_shortname = getattr(c.project, 'shortname', None)
        if len(parts) == 3:
            return {
                'project': parts[0],
                'app': parts[1],
                'artifact': parts[2]
            }
        elif len(parts) == 2:
            return {
                'project': p_shortname,
                'app': parts[0],
                'artifact': parts[1]
            }
        elif len(parts) == 1:
            return {
                'project': p_shortname,
                'app': None,
                'artifact': parts[0]
            }
        else:
            return None

    @classmethod
    def artifact_by_link(cls, link):
        parsed = cls._parse_link(link)
        if parsed:
            artifact = None

            # standard method
            shortlink = cls._get_from_parsed(parsed)
            if shortlink:
                artifact = shortlink.ref.artifact

            # try ephemerals
            if not artifact:
                for regex, func in cls.EPHEMERAL_PATTERNS.iteritems():
                    match = regex.match(parsed['artifact'])
                    if match:
                        artifact = func['artifact'](parsed, match)

            return artifact

    @classmethod
    def ref_id_by_link(cls, link, upsert=True):
        parsed = cls._parse_link(link)
        if parsed:
            ref_id = None

            # standard method
            shortlink = cls._get_from_parsed(parsed)
            if shortlink:
                ref_id = shortlink.ref_id

            # try ephemerals
            if ref_id is None:
                for regex, func in cls.EPHEMERAL_PATTERNS.iteritems():
                    match = regex.match(parsed['artifact'])
                    if match:
                        ref_id = func['ref_id'](parsed, match, upsert=upsert)

            return ref_id


class VisualizableArtifact(Artifact, VisualizableMixIn):

    class __mongometa__:
        session = visualizable_artifact_session

    def get_unique_id(self):
        return self.index_id()

    def artifact_ref_id(self):
        return self.index_id()
