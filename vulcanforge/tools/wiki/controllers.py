from datetime import datetime
import logging
from pprint import pformat
from urllib import unquote
import bson
import re
import types

from formencode import validators
from formencode.variabledecode import variable_decode
from pylons import request, tmpl_context as c, app_globals as g, response
import pymongo
from ew import jinja2_ew as ew
from tg import expose, validate, redirect, flash
from tg.controllers import RestController
from tg.decorators import with_trailing_slash, without_trailing_slash
from webob import exc

from vulcanforge.artifact.controllers import BaseArtifactController, \
    AttachmentController, AttachmentsController, ArtifactRestController
from vulcanforge.artifact.model import Shortlink, Feed
from vulcanforge.artifact.widgets import LabelListWidget, \
    RelatedArtifactsWidget
from vulcanforge.artifact.widgets.subscription import SubscribeForm
from vulcanforge.auth.model import User
from vulcanforge.common.app import DefaultSearchController, \
    DefaultAdminController
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import require_post, vardec, \
    validate_form
from vulcanforge.common.helpers import urlquote, really_unicode, diff_text
from vulcanforge.common.validators import DateTimeConverter
from vulcanforge.common.widgets.form_fields import AttachmentList, \
    MarkdownEdit, LabelEdit, Attachment, RepeatedAttachmentField
from vulcanforge.common.widgets.util import PageList, PageSize
from vulcanforge.discussion.controllers import AppDiscussionController
from vulcanforge.discussion.widgets import ThreadWidget
from vulcanforge.notification.model import Mailbox
from vulcanforge.tools.wiki.model import Page, Globals, WikiAttachment
from vulcanforge.tools.wiki.widgets.wiki import CreatePageWidget, \
    WikiPageMenuBar

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.tools.wiki:templates/'
MARKDOWN_EXAMPLE = '''
# First-level heading

Some *emphasized* and **strong** text

#### Fourth-level heading

'''


def get_page_title_from_request(req_url_utf=None, prefix=None):

    if req_url_utf is None:
        req_url_utf = request.path_info
    if prefix is None:
        prefix = c.app.url

    req_url = req_url_utf.decode('utf-8')

    rest = filter(None, req_url.split(prefix)[-1].split('/'))
    title = rest[0]
    rest = rest[1:]
    while rest:
        part = rest[0]
        if part in PAGE_CONTROLLER_FUNCTIONS:
            break
        else:
            title += '/' + part
            rest = rest[1:]
    return title, rest


class WikiSearchController(DefaultSearchController):
    """Search for wiki pages"""
    @expose(TEMPLATE_DIR + 'search.html')
    @with_trailing_slash
    @validate(dict(
        q=validators.UnicodeString(if_empty=None),
        history=validators.StringBool(if_empty=False),
        limit=validators.Int(if_empty=25),
        page=validators.Int(if_empty=0)))
    def search(self, **kw):
        return DefaultSearchController.search(self, **kw)


class ReferenceController(BaseController):
    """Used to create a new wiki page with a pre-installed reference"""

    @expose()
    def index(self, artifact_ref=None):
        shortlink = Shortlink.query.get(ref_id=unquote(artifact_ref))
        if shortlink is None:
            raise exc.HTTPNotFound()
        tc = 0
        title = 'New Wiki Page'
        page = Page.query.get(
            app_config_id=c.app.config._id, title=title)
        while page is not None:
            tc += 1
            title = 'New Wiki Page %d' % tc
            page = Page.query.get(
                app_config_id=c.app.config._id, title=title)
        edit_url = c.app.url + title + '/edit'
        full_url = '{}?default_content={}'.format(
            edit_url, urlquote(shortlink.render_link())
        )
        redirect(full_url)


class WikiContentBaseController(BaseController):

    class Widgets(BaseController.Widgets):
        create_page_lightbox = CreatePageWidget(
            name='create_wiki_page',
            trigger='#sidebar a.add_wiki_page'
        )
        page_list = PageList()
        page_size = PageSize()

    class Forms(BaseController.Forms):
        page_subscribe_form = SubscribeForm(thing='page')


class RootController(WikiContentBaseController):

    class Widgets(WikiContentBaseController.Widgets):
        menu_bar = WikiPageMenuBar()

    def __init__(self, app):
        setattr(self, 'feed.atom', self.feed)
        setattr(self, 'feed.rss', self.feed)
        c.create_page_lightbox = self.Widgets.create_page_lightbox
        self._discuss = AppDiscussionController()
        self.new_with_reference = ReferenceController()
        self.search = WikiSearchController()

    def _check_security(self):
        g.security.require_access(c.app, 'read')

    @with_trailing_slash
    @expose()
    def index(self, **kw):
        redirect(really_unicode(c.app.root_page_name).encode('utf-8') + '/')

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'browse.html')
    @validate(dict(sort=validators.UnicodeString(if_empty='alpha'),
                   show_deleted=validators.StringBool(if_empty=True),
                   page=validators.Int(if_empty=0),
                   limit=validators.Int(if_empty=None)))
    def browse_pages(self, sort='alpha', show_deleted=True, page=0,
                     limit=None, **kw):
        c.page_list = self.Widgets.page_list
        c.page_size = self.Widgets.page_size
        c.menu_bar = self.Widgets.menu_bar
        c.subscribe_form = self.Forms.page_subscribe_form
        limit, pagenum, start = g.handle_paging(limit, page, default=25)
        pages = []
        criteria = dict(app_config_id=c.app.config._id)
        can_delete = g.security.has_access(c.app, 'write')
        show_deleted = show_deleted and can_delete
        if not can_delete:
            criteria['deleted'] = False
        q = Page.query.find(criteria)
        if sort == 'alpha':
            q = q.sort('title')
        elif sort == 'recent':
            q = q.sort('last_updated', pymongo.DESCENDING)
        count = q.count()
        q = q.skip(start).limit(int(limit))
        for page in q:
            recent_edit = page.history().first()
            p = dict(
                title=page.title,
                url=page.url(),
                deleted=page.deleted,
                artifact=page,
                updated=page.last_updated,
                is_home=page.is_home
            )
            if recent_edit:
                p['user_label'] = recent_edit.author.display_name
                p['user_name'] = recent_edit.author.username
                p['last_changer'] = recent_edit.author_user
                p['subscribed'] = Mailbox.subscribed(artifact=page)
            pages.append(p)
            try:
                if page.deleted:
                    p['updated'] = page.deleted_time
                    p['last_changer'] = page.deleter
            except AttributeError:
                pass
        return dict(
            pages=pages,
            can_delete=can_delete,
            show_deleted=show_deleted,
            limit=limit,
            count=count,
            page=pagenum
        )

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'browse_tags.html')
    @validate(dict(sort=validators.UnicodeString(if_empty='alpha'),
                   page=validators.Int(if_empty=0),
                   limit=validators.Int(if_empty=0)))
    def browse_tags(self, sort='alpha', page=0, limit=0, **kw):
        c.page_list = self.Widgets.page_list
        c.page_size = self.Widgets.page_size
        limit, pagenum, start = g.handle_paging(limit, page, default=25)
        page_tags = {}
        q = Page.query.find(dict(
            app_config_id=c.app.config._id,
            deleted=False
        ))
        count = q.count()
        q = q.skip(start).limit(int(limit))
        for page in q:
            if page.labels:
                for label in page.labels:
                    page_tags.setdefault(label, []).append(page)
        return dict(labels=page_tags, limit=limit, count=count, page=pagenum)

    @with_trailing_slash
    @expose('jinja:vulcanforge.common:templates/markdown_syntax.html')
    def markdown_syntax(self):
        """Display a page about how to use markdown."""
        return dict(example=MARKDOWN_EXAMPLE)

    @without_trailing_slash
    @expose()
    @validate({
        'since': DateTimeConverter(if_empty=None, if_invalid=None),
        'until': DateTimeConverter(if_empty=None, if_invalid=None),
        'offset': validators.Int(if_empty=None),
        'limit': validators.Int(if_empty=None)
    })
    def feed(self, since=None, until=None, offset=None, limit=None):
        if request.environ['PATH_INFO'].endswith('.atom'):
            feed_type = 'atom'
        else:
            feed_type = 'rss'
        title = 'Recent changes to %s' % c.app.config.options.mount_point
        feed = Feed.feed(
            dict(project_id=c.project._id, app_config_id=c.app.config._id),
            feed_type,
            title,
            c.app.url,
            title,
            since, until, offset, limit)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        return feed.writeString('utf-8')

    @expose('json')
    def title_autocomplete(self, q=None):
        if q is None:
            q = ''
        query_params = {
            'app_config_id': c.app.config._id,
            'title': {'$regex': q, '$options': 'i'},
            'deleted': False
        }
        query_cursor = Page.query.find(query_params)
        query_cursor.sort('title', pymongo.ASCENDING)
        return {
            'results': [p.title for p in query_cursor]
        }

    @expose()
    def _lookup(self, title, *remainder):
        """Instantiate a Page object, and continue dispatch there"""
        # The TG request extension machinery will strip off the end of
        # a dotted wiki page name if it matches a known file extension. Here,
        # we reassemble the original page name.
        title, remainder = get_page_title_from_request()
        title = unquote(really_unicode(title))
        page_model = c.app.artifacts['page']['model']
        controller = c.app.artifacts['page']['controller']
        page = page_model.query.get(
            app_config_id=c.app.config._id, title=title)
        return controller(page, title), remainder


class PageController(BaseArtifactController, WikiContentBaseController):

    class Widgets(WikiContentBaseController.Widgets):
        thread = ThreadWidget(
            page=None, limit=None, page_size=None, count=None, style='linear')
        attachment_list = AttachmentList()
        markdown_editor = MarkdownEdit()
        label_list = LabelListWidget()
        label_edit = LabelEdit()
        menu_bar = WikiPageMenuBar()
        page_attachment = Attachment()
        related_artifacts = RelatedArtifactsWidget()
        attachments_field = RepeatedAttachmentField(label="Attach Files")
        hide_attachments_field = ew.Checkbox(name="hide_attachments",
                                             label="Hide Attachments")
        rename_descendants_field = ew.Checkbox(name="rename_descendants",
                                               label="Rename Subpages")
        featured_field = ew.Checkbox(name="featured", label="Featured")

    def __init__(self, artifact, title):
        BaseArtifactController.__init__(self, artifact)
        self.title = title
        c.wikipage = self.page = Page.query.get(
            app_config_id=c.app.config._id, title=self.title)
        if self.page is not None:
            self.attachment = WikiAttachmentsController(self.page)
            self.title = self.artifact.title
        c.create_page_lightbox = self.Widgets.create_page_lightbox
        setattr(self, 'feed.atom', self.feed)
        setattr(self, 'feed.rss', self.feed)

    def _check_security(self):
        if self.page:
            g.security.require_access(self.page, 'read')
            if self.page.deleted:
                g.security.require_access(self.page, 'write')
        else:
            g.security.require_access(c.app, 'write')

    def fake_page(self):
        return dict(
            title=self.title,
            text=u'',
            labels=[],
            viewable_by=['all'],
            attachments=[],
            is_fake=True
        )

    def get_version(self, version):
        if not version:
            return self.page
        try:
            return self.page.get_version(version)
        except (ValueError, IndexError):
            return None

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'page_view.html')
    @validate(dict(version=validators.Int(if_empty=None)))
    def index(self, version=None, **kw):
        if not self.page:
            redirect('{}{}/edit'.format(
                c.app.url, urlquote(self.title)))

        c.thread_widget = self.Widgets.thread
        c.subscribe_form = self.Forms.page_subscribe_form
        c.related_artifacts_widget = self.Widgets.related_artifacts
        c.menu_bar = self.Widgets.menu_bar
        c.renderer = c.app.artifacts["page"]["renderer"]()

        page = self.get_version(version)
        if page is None:
            if version:
                redirect('.?version=%d' % (version - 1))
            else:
                redirect('.')
        elif 'all' not in page.viewable_by and \
                c.user.username not in page.viewable_by:
            raise exc.HTTPForbidden(detail="You may not view this page.")
        hide_sidebar = not (c.app.show_left_bar or
                            g.security.has_access(self.page, 'write'))
        hierarchy_items = self.get_hierarchy_items()
        return dict(
            page=page,
            subscribed=Mailbox.subscribed(artifact=page),
            hide_sidebar=hide_sidebar,
            show_meta=c.app.show_right_bar,
            version=version,
            hierarchy_items=hierarchy_items,
        )

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'page_edit.html')
    def edit(self, default_content=u'', **kw):
        page_exists = self.page
        if page_exists:
            if self.page.deleted:
                raise exc.HTTPForbidden(detail='Page is deleted')
            g.security.require_access(self.page, 'write')
            page = self.page
            attachment_context_id = str(page._id)
        else:
            page = self.fake_page()
            page['text'] = unquote(default_content)
            attachment_context_id = None
        c.markdown_editor = self.Widgets.markdown_editor
        c.attachment_list = self.Widgets.attachment_list
        c.label_edit = self.Widgets.label_edit
        c.subscribe_form = self.Forms.page_subscribe_form
        c.attachments_field = self.Widgets.attachments_field
        c.hide_attachments_field = self.Widgets.hide_attachments_field
        c.rename_descendants = self.Widgets.rename_descendants_field
        c.featured_field = self.Widgets.featured_field
        c.menu_bar = self.Widgets.menu_bar
        return {
            'page': page,
            'page_exists': page_exists,
            'attachment_context_id': attachment_context_id,
            'edit_status': self.edit_status()
        }

    @without_trailing_slash
    @expose('json')
    def edit_status(self):
        if self.page is None:
            return {
                'otherEditors': [],
                'expirationTime': -1,
                'currentVersion': None
            }
        g.security.require_access(self.page, 'write')
        expiration_time = 20
        page_key = 'wiki.editing.{}'.format(self.page._id)
        user_key_template = '{}.{{}}'.format(page_key)
        my_user_key = user_key_template.format(c.user.username)
        g.cache.sadd(page_key, c.user.username)
        g.cache.expire(page_key, expiration_time)
        g.cache.set(my_user_key, '', expiration=expiration_time)
        other_editors = set()
        for username in g.cache.smembers(page_key):
            if username == c.user.username:
                continue
            user_key = user_key_template.format(username)
            if g.cache.exists(user_key):
                other_editors.add(username)
            else:
                g.cache.srem(page_key, username)
        return {
            'otherEditors': list(other_editors),
            'expirationTime': expiration_time,
            'currentVersion': self.page.version
        }

    @without_trailing_slash
    @expose('json')
    @require_post()
    def delete(self):
        g.security.require_access(self.page, 'write')
        Shortlink.query.remove(dict(ref_id=self.page.index_id()))
        self.page.deleted = True
        self.page.deleted_time = datetime.utcnow()
        self.deleter = c.user._id
        flash('Page deleted')
        return dict(location=c.app.url + 'browse_pages')

    @without_trailing_slash
    @expose('json')
    @require_post()
    def undelete(self):
        g.security.require_access(self.page, 'write')
        self.page.deleted = False
        Shortlink.from_artifact(self.page)
        flash('Page undeleted')
        return dict(location='.')

    @without_trailing_slash
    @expose('json')
    @require_post()
    def set_as_home(self):
        g.security.require_access(self.page, 'admin')
        self.page.app.root_page_name = self.page.title
        self.page.app.upsert_root(self.page.title)
        flash('Home updated')
        return dict(location='.')

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'page_history.html')
    @validate(dict(page=validators.Int(if_empty=0),
                   limit=validators.Int(if_empty=None),
                   v1=validators.Int(),
                   v2=validators.Int()))
    def history(self, page=0, limit=None, v1=None, v2=None, **kw):
        if not self.page:
            raise exc.HTTPNotFound
        c.page_list = self.Widgets.page_list
        c.page_size = self.Widgets.page_size
        c.menu_bar = self.Widgets.menu_bar
        c.subscribe_form = self.Forms.page_subscribe_form
        limit, pagenum, start = g.handle_paging(limit, page, default=25)
        pages = self.page.history()
        count = pages.count()
        pages = pages.skip(start).limit(int(limit))
        return dict(
            title=self.title,
            pages=pages,
            limit=limit,
            count=count,
            page=page,
            artifact=self.page,
            subscribed=Mailbox.subscribed(artifact=self.page),
            v1=v1,
            v2=v2
        )

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'page_diff.html')
    @validate({'v1': validators.Int(), 'v2': validators.Int()})
    def diff(self, v1=None, v2=None, **kw):
        if not self.page:
            raise exc.HTTPNotFound
        if v1 is None or v2 is None or v1 is v2:
            flash('Incorrect version numbers specified!', 'error')
            redirect(
                c.app.url +
                really_unicode(self.page.title).encode('utf-8') +
                '/history'
            )
        try:
            p1 = self.get_version(v1)
            p2 = self.get_version(v2)
        except IndexError:
            flash('Version not found', 'error')
            redirect(
                c.app.url +
                really_unicode(self.page.title).encode('utf-8') +
                '/history'
            )
        result = diff_text(p1.text, p2.text)
        c.subscribe_form = self.Forms.page_subscribe_form
        c.menu_bar = self.Widgets.menu_bar
        return dict(
            p1=p1,
            p2=p2,
            edits=result,
            page=self.page
        )

    @without_trailing_slash
    @expose(content_type='text/plain')
    def raw(self):
        if not self.page:
            raise exc.HTTPNotFound
        return pformat(self.page)

    @without_trailing_slash
    @expose()
    @validate(dict(
            since=DateTimeConverter(if_empty=None, if_invalid=None),
            until=DateTimeConverter(if_empty=None, if_invalid=None),
            offset=validators.Int(if_empty=None),
            limit=validators.Int(if_empty=None)))
    def feed(self, since=None, until=None, offset=None, limit=None):
        if not self.page:
            raise exc.HTTPNotFound
        if request.environ['PATH_INFO'].endswith('.atom'):
            feed_type = 'atom'
        else:
            feed_type = 'rss'
        feed = Feed.feed(
            {'ref_id': self.page.index_id()},
            feed_type,
            'Recent changes to %s' % self.page.title,
            self.page.url(),
            'Recent changes to %s' % self.page.title,
            since, until, offset, limit)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        return feed.writeString('utf-8')

    @without_trailing_slash
    @expose('json')
    @require_post()
    @validate(dict(version=validators.Int(if_empty=1)))
    def revert(self, version):
        if not self.page:
            raise exc.HTTPNotFound
        g.security.require_access(self.page, 'write')
        orig = self.get_version(version)
        if orig:
            self.page.text = orig.text
        self.page.commit()
        return dict(location='.')

    def _rename_page(self, title, descendants=True):
        name_conflict = Page.query.find(dict(
            app_config_id=c.app.config._id,
            title=title,
            deleted=False
        )).first()
        if name_conflict:
            flash('There is already a page named "%s".' % title, 'error')
            return False
        if self.page.title == c.app.root_page_name:
            Globals.query.get(
                app_config_id=c.app.config._id).root = title
        old_title = self.page.title
        self.page.title = title
        if descendants:
            descendant_query_params = {
                'app_config_id': self.page.app_config_id,
                'title': {'$regex': r'^{}/'.format(old_title)},
                'deleted': False
            }
            descendant_cursor = Page.query.find(descendant_query_params)
            pattern = r'^{}'.format(old_title)
            replacement = title
            for page in descendant_cursor:
                page.title = re.sub(pattern, replacement, page.title)

    @without_trailing_slash
    @vardec
    @expose()
    @require_post()
    @validate(validators={
        'hide_attachments': validators.StringBool(if_empty=False,
                                                  if_missing=False),
        'rename_descendants': validators.StringBool(if_empty=False,
                                                    if_missing=False),
        'featured': validators.StringBool(if_empty=False,
                                          if_missing=False)
    })
    def do_edit(self, title=None, text=None, labels=None, viewable_by=None,
                new_viewable_by=None, hide_attachments=False,
                rename_descendants=True, featured=False, **kw):
        modified = False
        if not title:
            flash('You must provide a title for the page.', 'error')
            redirect('edit')
        if not self.page:
            # the page doesn't exist yet, so create it
            self.page = Page.upsert(self.title)
            self.page.viewable_by = ['all']
        else:
            g.security.require_access(self.page, 'write')

        # title
        name_conflict = None
        title = title.strip('/ \t\n')
        if self.page.title != title:
            name_conflict = self._rename_page(title, rename_descendants)
            modified = True

        # text
        if self.page.text != text:
            self.page.text = text
            modified = True

        # labels
        if labels:
            labels = labels.split(',')
        else:
            labels = []
        if self.page.labels != labels:
            self.page.labels = labels
            modified = True

        # attachments
        posted_values = variable_decode(request.POST)
        for attachment in posted_values.get('new_attachments', []):
            if not hasattr(attachment, 'file'):
                continue
            self.page.attach(
                attachment.filename,
                attachment.file,
                content_type=attachment.type
            )
            modified = True
        if modified:
            self.page.commit()
        if new_viewable_by:
            if new_viewable_by == 'all':
                self.page.viewable_by.append('all')
            else:
                user = c.project.user_in_project(str(new_viewable_by))
                if user:
                    self.page.viewable_by.append(user.username)
        if viewable_by:
            for u in viewable_by:
                if u.get('delete'):
                    if u['id'] == 'all':
                        self.page.viewable_by.remove('all')
                    else:
                        user = User.by_username(str(u['id']))
                        if user:
                            self.page.viewable_by.remove(user.username)
        self.page.hide_attachments = hide_attachments

        # featured
        if featured == 'on':  # a hack... validator is not converting the value
            featured = True
        if featured != bool(self.page.featured):
            self.page.featured = featured
            if featured:
                # put this page at the end of the list
                cursor = self.page.app.get_featured_pages_cursor(sort=False)
                last_page = cursor.sort('featured_ordinal', -1).first()
                highest_ordinal = getattr(last_page, 'featured_ordinal', 0)
                self.page.featured_ordinal = highest_ordinal + 1
            else:
                # update the featured list ordinals
                cursor = self.page.app.get_featured_pages_cursor()
                for i, page in enumerate(cursor):
                    page.featured_ordinal = i
                self.page.featured_ordinal = None
            g.cache.redis.expire('navdata', 0)

        redirect(
            really_unicode(c.app.url + self.page.title +(u'/' if not name_conflict else u'/edit')).encode('utf-8')

        )

    @expose()
    @validate_form("subscribe_form")
    def subscribe(self, subscribe=None, unsubscribe=None):
        if not self.page:
            raise exc.HTTPNotFound
        if subscribe:
            self.page.subscribe(type='direct')
        elif unsubscribe:
            self.page.unsubscribe()
        redirect(request.referer or 'index')

    def get_hierarchy_items(self, limit=10):
        # get hierarchically related pages for navigation
        hierarchy_items = []

        # get roots
        root_cursor = Page.query.find({
            'app_config_id': self.page.app_config_id,
            'title': {'$regex': '^[^/]*$'},
            'deleted': False
        })
        root_cursor.sort('title', pymongo.ASCENDING)
        root_cursor.limit(limit)
        hierarchy_items.append({
            'label': c.app.config.options.mount_label,
            'prefix': '',
            'href': c.app.url.decode('utf-8'),
            'children': root_cursor.all(),
            'child_count': root_cursor.count(),
            'more_href': (c.app.url + 'browse_pages').decode('utf-8')
        })

        # get children along path
        title_segments = self.page.title.split('/')
        for i in range(0, len(title_segments)):
            end_title = title_segments[i]
            title_prefix = ('/'.join(title_segments[:i + 1])).encode('utf-8')
            is_home = False
            if title_prefix == self.page.app.root_page_name:
                is_home = True
            child_regex = r'^{}/[^/]+$'.format(title_prefix)
            child_cursor = Page.query.find({
                'app_config_id': self.page.app_config_id,
                'title': {'$regex': child_regex},
                'deleted': False
            })
            child_cursor.sort('title', pymongo.ASCENDING)
            child_cursor.limit(limit)
            hierarchy_items.append({
                'label': end_title,
                'prefix': title_prefix,
                'href': ('{}{}'.format(c.app.url, title_prefix)).decode('utf-8'),
                'children': child_cursor.all(),
                'child_count': child_cursor.count(),
                'more_href': "{}search/search/?tool_q=title_s:*'{}'".format(
                    c.app.url, title_prefix).decode('utf-8'),
                'is_home': is_home
            })
        return hierarchy_items


class WikiAttachmentController(AttachmentController):
    AttachmentClass = WikiAttachment
    edit_perm = 'write'


class WikiAttachmentsController(AttachmentsController):
    AttachmentControllerClass = WikiAttachmentController


class RootRestController(RestController):

    artifact = ArtifactRestController()

    @expose('json:')
    def get_all(self, **kw):
        page_titles = []
        pages = Page.query.find(dict(
            app_config_id=c.app.config._id,
            deleted=False
        ))
        for page in pages:
            if g.security.has_access(page, 'read'):
                page_titles.append(page.title)
        return dict(pages=page_titles)

    @expose('json:')
    def get_one(self, title, **kw):
        page = Page.query.get(
            app_config_id=c.app.config._id,
            title=title,
            deleted=False
        )
        if page is None:
            raise exc.HTTPNotFound, title
        g.security.require_access(page, 'read')
        return dict(title=page.title, text=page.text, labels=page.labels)

    @vardec
    @expose()
    @require_post()
    def post(self, title, **post_data):
        page = Page.query.get(
            app_config_id=c.app.config._id,
            title=title,
            deleted=False)
        if not page:
            g.security.require_access(c.app, 'write')
            page = Page.upsert(title)
        else:
            g.security.require_access(page, 'write')
        page.text = post_data['text']
        if 'labels' in post_data:
            page.labels = post_data['labels'].split(',')
        page.commit()


class WikiAdminController(DefaultAdminController):

    def _check_security(self):
        g.security.require_access(self.app, 'admin')

    @with_trailing_slash
    def index(self, **kw):
        redirect('home')

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'admin_home.html')
    def home(self):
        return dict(app=self.app,
                    home=self.app.root_page_name,
                    allow_config=g.security.has_access(self.app, 'admin'))

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'admin_options.html')
    def options(self):
        return dict(app=self.app,
                    allow_config=g.security.has_access(self.app, 'admin'))

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'admin_featured.html')
    def featured(self):
        cursor = self.app.get_featured_pages_cursor()
        return {
            'app': self.app,
            'allow_config': g.security.has_access(self.app, 'admin'),
            'has_featured_pages': cursor.count() > 0,
            'featured_pages': [
                {
                    '_id': p._id,
                    'title': p.title,
                    'url': p.url,
                    'featured_label': p.featured_label
                }
                for p in cursor
            ]
        }

    @without_trailing_slash
    @expose()
    @require_post()
    def set_home(self, new_home):
        self.app.root_page_name = new_home
        self.app.upsert_root(new_home)
        flash('Home updated')
        mount_base = c.project.url() + self.app.config.options.mount_point + '/'
        url = (
            really_unicode(mount_base).encode('utf-8') +
            really_unicode(new_home).encode('utf-8') + '/'
        )
        redirect(url)

    @without_trailing_slash
    @expose()
    @require_post()
    @validate(validators={
        'show_table_of_contents': validators.StringBool(if_empty=False,
                                                        if_missing=False)
    })
    def set_options(self, show_discussion=False, show_left_bar=False,
                    show_right_bar=False, show_table_of_contents=False):
        self.app.show_discussion = show_discussion
        self.app.show_left_bar = show_left_bar
        self.app.show_right_bar = show_right_bar
        self.app.show_table_of_contents = show_table_of_contents
        flash('Wiki options updated')
        redirect(c.project.url() + 'admin/tools')

    @without_trailing_slash
    @expose()
    @require_post()
    @vardec
    def update_featured(self, featured_ordinals=None, featured_labels=None,
                        **kwargs):
        if featured_ordinals is not None:
            for _id, value in featured_ordinals.items():
                try:
                    _id = bson.ObjectId(_id)
                    value = int(value)
                except ValueError:
                    continue
                page = Page.query.get(app_config_id=self.app.config._id,
                                      _id=_id)
                if page is not None and g.security.has_access(page, 'write'):
                    page.featured_ordinal = value
        if featured_labels is not None:
            for _id, value in featured_labels.items():
                try:
                    _id = bson.ObjectId(_id)
                except ValueError:
                    continue
                page = Page.query.get(app_config_id=self.app.config._id,
                                      _id=_id)
                if page is not None and g.security.has_access(page, 'write'):
                    page.featured_label = value
        g.cache.redis.expire('navdata', 0)
        flash('Wiki featured pages updated')
        redirect(c.project.url() + 'admin/tools')


PAGE_CONTROLLER_FUNCTIONS = ['attachment'] + [
    name for name, value in PageController.__dict__.items()
    if type(value) == types.FunctionType
]
