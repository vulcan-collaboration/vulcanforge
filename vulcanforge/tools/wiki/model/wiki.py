import logging
import jinja2

from datetime import datetime
from pylons import app_globals as g
from pylons import tmpl_context as c

from ming import schema
from ming.odm import FieldProperty, ForeignIdProperty, session

from vulcanforge.artifact.model import Snapshot, VersionedArtifact, Feed, \
    BaseAttachment
from vulcanforge.auth.model import User
from vulcanforge.common.helpers import urlquote
from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.common.model.session import project_orm_session
from vulcanforge.common.util import ConfigProxy
from vulcanforge.common.util.diff import unified_diff
from vulcanforge.discussion.model import Thread, Post
from vulcanforge.exchange.model.artifact import ExchangeableArtifact
from vulcanforge.notification.model import Notification


config = ConfigProxy(common_suffix='forgemail.domain')
TEMPLATE_DIR = 'vulcanforge.tools.wiki.templates'


class Globals(BaseMappedClass):

    class __mongometa__:
        name = 'wiki-globals'
        session = project_orm_session
        indexes = ['app_config_id']

    type_s = 'WikiGlobals'
    app_config_id = ForeignIdProperty(
        'AppConfig', if_missing=lambda: c.app.config._id)
    root = FieldProperty(str)


class PageHistory(Snapshot, ExchangeableArtifact):
    class __mongometa__:
        name = 'page_history'

    type_s = 'WikiPage Snapshot'

    def original(self):
        return Page.query.get(_id=self.artifact_id)

    def authors(self):
        return self.original().authors()

    def shorthand_id(self):
        return '%s#%s' % (self.original().shorthand_id(), self.version)

    def s3_key_prefix(self):
        return str(self.original()._id)

    def url(self):
        return self.original().url() + '?version=%d' % self.version

    def original_url(self):
        return self.original().url()

    @property
    def title_s(self):
        return 'Version %d of %s' % (self.version, self.original().title)

    def index(self, **kw):
        return super(PageHistory, self).index(
            text_objects=[self.data.text],
            **kw
        )

    @property
    def html_text(self):
        """A markdown processed version of the page text"""
        return g.markdown_wiki.convert(self.data.text)

    @property
    def attachments(self):
        return self.original().attachments

    @property
    def email_address(self):
        return self.original().email_address

    def get_rendered_html(self):
        md = self.app.get_markdown()
        return md.convert(self.text)


class Page(VersionedArtifact, ExchangeableArtifact):
    class __mongometa__:
        name = 'page'
        history_class = PageHistory
        indexes = ['title', ('title', 'app_config_id', 'deleted')]

    title = FieldProperty(str)
    text = FieldProperty(schema.String, if_missing='')
    viewable_by = FieldProperty([str])
    deleted = FieldProperty(bool, if_missing=False)
    deleted_time = FieldProperty(datetime)
    deleter_id = FieldProperty(schema.ObjectId, if_missing=lambda: c.user._id)
    type_s = 'Wiki'
    hide_attachments = FieldProperty(bool, if_missing=False)
    featured = FieldProperty(bool, if_missing=False)
    featured_label = FieldProperty(str, if_missing=None)
    featured_ordinal = FieldProperty(int, if_missing=None)

    def commit(self):
        self.autosubscribe()
        VersionedArtifact.commit(self)
        session(self).flush()
        if self.version > 1:
            v1 = self.get_version(self.version - 1)
            v2 = self
            la = [line + '\n' for line in v1.text.splitlines()]
            lb = [line + '\n' for line in v2.text.splitlines()]
            diff = ''.join(unified_diff(
                    la, lb,
                    'v%d' % v1.version,
                    'v%d' % v2.version))
            description = '<pre>' + diff + '</pre>'
            if v1.title != v2.title:
                subject = '%s renamed page %s to %s' % (
                    c.user.display_name, v1.title, v2.title)
            else:
                subject = '%s modified page %s' % (
                    c.user.display_name, self.title)
        else:
            description = self.text
            subject = '%s created page %s' % (
                c.user.display_name, self.title)
        if description == '<pre></pre>':
            description = 'Content of the page was not altered'
        Feed.post(self, title=None, description=description)
        Notification.post(
            artifact=self, topic='metadata', text=description, safe_text='',
            subject=subject)

    @property
    def deleter(self):
        if self.deleter_id:
            return User.query.get(_id=self.deleter_id)

    @property
    def email_address(self):
        domain = '.'.join(reversed(
            self.app.url[1:-1].split('/'))).replace('_', '-')
        return '%s@%s%s' % (
            self.title.replace('/', '.'), domain, config.common_suffix)

    @property
    def email_subject(self):
        return 'Discussion for %s page' % self.title

    @property
    def is_home(self):
        return self.title == self.app.root_page_name

    def url(self):
        s = self.app_config.url() + \
            urlquote(self.title.encode('utf-8')) + '/'
        return s

    def email_template(self):
        template_loader = jinja2.Environment(
            loader=jinja2.PackageLoader(TEMPLATE_DIR, 'email'))
        return template_loader.get_template('Page.txt')

    def original_url(self):
        return self.url()

    def shorthand_id(self):
        return self.title

    @property
    def title_s(self):
        return 'WikiPage %s' % self.title

    def index(self, **kw):
        return super(VersionedArtifact, self).index(
            version_i=self.version,
            type_s='WikiPage',
            text_objects=[
                self.title,
                self.text,
            ],
            **kw
        )

    @property
    def attachments(self):
        return WikiAttachment.query.find(dict(
            artifact_id=self._id,
            type='attachment'
        )).all()

    @classmethod
    def upsert(cls, title, version=None):
        """Update page with `title` or insert new page with that name"""
        if version is None:
            # Check for existing page object
            obj = cls.query.get(app_config_id=c.app.config._id, title=title)
            if obj is None:
                obj = cls(title=title, app_config_id=c.app.config._id)
                Thread(discussion_id=obj.app_config.discussion_id,
                       ref_id=obj.index_id())
            return obj
        else:
            pg = cls.upsert(title)
            history_cls = cls.__mongometa__.history_class
            ss = history_cls.query.find({
                'artifact_id': pg._id,
                'version': int(version)
            }).one()
            return ss

    @classmethod
    def attachment_class(cls):
        return WikiAttachment

    def reply(self, text):
        Feed.post(self, text)
        # Get thread
        thread = Thread.query.get(artifact_id=self._id)
        return Post(
            discussion_id=thread.discussion_id,
            thread_id=thread._id,
            text=text)

    @property
    def cache_name(self):
        return '.'.join((
            str(self.app_config_id), str(self.version), str(self._id)))

    def authors(self):
        """All the users that have edited this page"""
        user_ids = set(r.author.id for r in self.history())
        return User.query.find({'_id': {'$in': list(user_ids)}}).all()

    def get_rendered_html(self):
        md = self.app.get_markdown()
        return md.convert(self.text)


class WikiAttachment(BaseAttachment):
    ArtifactType = Page

    class __mongometa__:
        polymorphic_identity = 'WikiAttachment'

    attachment_type = FieldProperty(str, if_missing='WikiAttachment')



