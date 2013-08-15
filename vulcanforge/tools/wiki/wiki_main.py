# -*- coding: utf-8 -*-
#-*- python -*-
import logging
from pprint import pformat
import re
from urllib import unquote, quote
from datetime import datetime
import types

# Non-stdlib imports
from tg import expose, validate, redirect, response, flash
from tg.decorators import with_trailing_slash, without_trailing_slash
from tg.controllers import RestController
from pylons import app_globals as g, tmpl_context as c, request
from formencode import validators
from formencode.variabledecode import variable_decode
from webob import exc
import pymongo
from ming.odm import session
import ew as ew_core
import ew.jinja2_ew as ew

from vulcanforge.auth.model import User
from vulcanforge.common.app import (
    Application,
    DefaultAdminController,
    DefaultSearchController
)
from vulcanforge.common.controllers.decorators import (
    require_post,
    validate_form,
    vardec
)
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.helpers import urlquote, really_unicode, diff_text
from vulcanforge.common.util import push_config
from vulcanforge.common.util.decorators import exceptionless
from vulcanforge.common.types import SitemapEntry
from vulcanforge.common.validators import DateTimeConverter, HTMLEscapeValidator
from vulcanforge.common.widgets.form_fields import (
    AttachmentList,
    MarkdownEdit,
    LabelEdit,
    RepeatedAttachmentField,
    Attachment
)
from vulcanforge.common.widgets.util import PageList, PageSize
from vulcanforge.artifact.model import Shortlink
from vulcanforge.artifact.controllers import ArtifactRestController, \
    AttachmentController, AttachmentsController
from vulcanforge.artifact.model import Feed
from vulcanforge.artifact.widgets import (
    LabelListWidget,
    RelatedArtifactsWidget
)
from vulcanforge.artifact.widgets.subscription import SubscribeForm
from vulcanforge.discussion.controllers import AppDiscussionController
from vulcanforge.discussion.model import Post
from vulcanforge.discussion.widgets import ThreadWidget
from vulcanforge.notification.model import Mailbox
from vulcanforge.resources import Icon

# Local imports
from .version import __version__
from .model import Page, WikiAttachment, Globals
from .widgets.wiki import CreatePageWidget

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.tools.wiki:templates/'
HOME_TEMPLATE = """
Welcome to your wiki!

This is the default page, edit it as you see fit. To add a page simply \
reference it within brackets, e.g.: [SamplePage].

The wiki uses [Markdown]({}) syntax.
"""


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


class ForgeWikiApp(Application):
    """This is the Wiki app for PyForge"""
    __version__ = __version__
    permissions = ['configure', 'read', 'create', 'edit', 'delete',
                   'unmoderated_post', 'post', 'moderate', 'admin']
    searchable = True
    tool_label = 'Wiki'
    static_folder = 'Wiki'
    default_mount_label = 'Wiki'
    default_mount_point = 'wiki'
    default_root_page_name = u'Wiki Home'
    icons = {
        24: 'images/wiki_24.png',
        32: 'images/wiki_32.png',
        48: 'images/wiki_48.png'
    }
    # whether its artifacts are referenceable from the repo browser
    reference_opts = dict(Application.reference_opts,
        can_reference=True,
        can_create=True,
        create_perm='create'
    )
    admin_description = (
        "The wiki is a veritable content management system for your project. "
        "You can create wiki-based documentation and discuss these shared "
        "documents, or create beautiful content for presentation to potential "
        "contributors."
    )
    admin_actions = {
        "Add Page": {
            "url": "New%20Wiki%20Page",
            "permission": "create"
        },
        "View Wiki": {"url": ""},
    }
    permission_descriptions = dict(
        Application.permission_descriptions,
        moderate="moderate new content",
        unmoderated_post="add content without moderation",
        create="create new pages",
        edit="edit existing pages",
        delete="delete pages"
    )
    default_acl = {
        'Admin': permissions,
        'Developer': ['delete', 'moderate'],
        'Member': ['create', 'edit'],
        '*authenticated': ['post', 'unmoderated_post'],
        '*anonymous': ['read']
    }
    artifacts = {
        "page": Page
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = RootController(self)
        self.api_root = RootRestController()
        self.admin = WikiAdminController(self)

    def has_access(self, user, topic):
        return g.security.has_access(c.app, 'post', user=user)

    def handle_message(self, topic, message):
        LOG.info('Message from %s (%s)',
                 topic, self.config.options.mount_point)
        LOG.info('Headers are: %s', message['headers'])
        try:
            page = Page.upsert(topic)
        except Exception:
            LOG.exception('Error getting artifact %s', topic)
        self.handle_artifact_message(page, message)

    def _get_root_page_name(self):
        globals_ = Globals.query.get(app_config_id=self.config._id)
        if globals_ is not None:
            page_name = globals_.root
        else:
            page_name = self.default_root_page_name
        return page_name

    def _set_root_page_name(self, new_root_page_name):
        globals_ = Globals.query.get(app_config_id=self.config._id)
        if globals_ is not None:
            globals_.root = new_root_page_name
        elif new_root_page_name != self.default_root_page_name:
            globals_ = Globals(
                app_config_id=self.config._id, root=new_root_page_name
            )
        if globals_ is not None:
            session(globals_).flush()

    root_page_name = property(_get_root_page_name, _set_root_page_name)

    def _get_show_discussion(self):
        return self.config.options.get('show_discussion', False)

    def _set_show_discussion(self, show):
        self.config.options['show_discussion'] = bool(show)

    show_discussion = property(_get_show_discussion, _set_show_discussion)

    def _get_show_left_bar(self):
        return self.config.options.get('show_left_bar', True)

    def _set_show_left_bar(self, show):
        self.config.options['show_left_bar'] = bool(show)

    show_left_bar = property(_get_show_left_bar, _set_show_left_bar)

    def _get_show_right_bar(self):
        return self.config.options.get('show_right_bar', True)

    def _set_show_right_bar(self, show):
        self.config.options['show_right_bar'] = bool(show)

    show_right_bar = property(_get_show_right_bar, _set_show_right_bar)

    def _get_show_table_of_contents(self):
        return self.config.options.get('show_table_of_contents', True)

    def _set_show_table_of_contents(self, show):
        self.config.options['show_table_of_contents'] = bool(show)

    show_table_of_contents = property(_get_show_table_of_contents,
                                      _set_show_table_of_contents)

    def main_menu(self):
        """
        Apps should provide their entries to be added to the main nav
        :return: a list of :class:`SitemapEntries <vulcanforge.common.types.SitemapEntry>

        """
        return [SitemapEntry(self.config.options.mount_label.title(), '.')]

    def get_markdown(self):
        return g.markdown_wiki

    @property
    @exceptionless([], LOG)
    def sitemap(self):
        menu_id = self.config.options.mount_label.title()
        with push_config(c, app=self):
            page_query = Page.query.find(dict(
                app_config_id=self.config._id,
                deleted=False
            ))
            pages = [SitemapEntry(p.title, p.url()) for p in page_query]
            return [SitemapEntry(menu_id, '.')[SitemapEntry('Pages')[pages]]]

    def admin_menu(self):
        admin_url = c.project.url() + 'admin/' + \
                    self.config.options.mount_point + '/'
        links = [
            SitemapEntry(
                'Set Home',
                admin_url + 'home', className='admin_modal'
            ),
            SitemapEntry(
                'Options', admin_url + 'options', className='admin_modal')
        ]
        if self.permissions and g.security.has_access(self, 'configure'):
            links.append(
                SitemapEntry(
                    'Permissions',
                    admin_url + 'permissions',
                    className='nav_child'
                )
            )
        return links

    def sidebar_menu(self):
        links = []
        if g.security.has_access(self, 'create'):
            links.extend([
                SitemapEntry(
                    'Create Page',
                    self.url,
                    ui_icon=Icon('', 'ico-plus'),
                    className='add_wiki_page'
                ),
                SitemapEntry('')
            ])
        links.extend([
            SitemapEntry(
                'Wiki Home', c.app.url, ui_icon=Icon('', 'ico-home')
            ),
            SitemapEntry(
                'Browse Pages',
                c.app.url + 'browse_pages/',
                ui_icon=Icon('', 'ico-book_alt2')
            ),
            SitemapEntry(
                'Browse Labels',
                c.app.url + 'browse_tags/'
            )
        ])
        discussion = c.app.config.discussion
        if discussion:
            pending_mod_count = Post.query.find({
                'discussion_id': discussion._id, 'status': 'pending'}).count()
        else:
            pending_mod_count = 0
        if pending_mod_count and g.security.has_access(discussion, 'moderate'):
            links.append(SitemapEntry(
                'Moderate',
                discussion.url() + 'moderate',
                ui_icon='ico-moderate',
                small=pending_mod_count
            ))
        links.extend([
            SitemapEntry(''),
            SitemapEntry(
                'Markdown Syntax',
                c.app.url + 'markdown_syntax/',
                ui_icon=Icon('', 'ico-info'),
                className='nav_child'
            )
        ])
        return links

    def install(self, project, acl=None):
        """Set up any default permissions and roles here"""
        self.config.options['project_name'] = project.name
        self.config.options['show_right_bar'] = True
        super(ForgeWikiApp, self).install(project, acl=acl)

        root_page_name = self.default_root_page_name
        Globals(app_config_id=c.app.config._id, root=root_page_name)
        self.upsert_root(root_page_name)

    def upsert_root(self, new_root):
        p = Page.query.get(
            app_config_id=self.config._id,
            title=new_root,
            deleted=False
        )
        if p is None:
            with push_config(c, app=self):
                p = Page.upsert(new_root)
                p.viewable_by = ['all']
                url = c.app.url + 'markdown_syntax' + '/'
                p.text = HOME_TEMPLATE.format(url)
                p.commit()

    def uninstall(self, project=None, project_id=None):
        """Remove all the tool's artifacts from the database"""
        WikiAttachment.query.remove(dict(app_config_id=self.config._id))
        Page.query.remove(dict(app_config_id=self.config._id))
        Globals.query.remove(dict(app_config_id=self.config._id))
        super(ForgeWikiApp, self).uninstall(project=project,
                                            project_id=project_id)


def get_page_title_from_request(req_url=None, prefix=None):
    if req_url is None:
        req_url = request.path_info
    if prefix is None:
        prefix = c.app.url
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

    def __init__(self, app):
        setattr(self, 'feed.atom', self.feed)
        setattr(self, 'feed.rss', self.feed)
        c.create_page_lightbox = self.Widgets.create_page_lightbox
        self._discuss = AppDiscussionController()
        self.new_with_reference = ReferenceController()
        self.search = WikiSearchController()
        self.page_controller_cls = PageController

    def _check_security(self):
        g.security.require_access(c.app, 'read')

    @with_trailing_slash
    @expose()
    def index(self, **kw):
        redirect(really_unicode(c.app.root_page_name).encode('utf-8') + '/')

    # Instantiate a Page object, and continue dispatch there
    @expose()
    def _lookup(self, pname, *remainder):
        # HACK: The TG request extension machinery will strip off the end of
        # a dotted wiki page name if it matches a known file extension. Here,
        # we reassemble the original page name.
        pname, remainder = get_page_title_from_request()
        return self.page_controller_cls(pname), remainder

    @expose()
    def new_page(self, title):
        redirect(quote(really_unicode(title).encode('utf-8') + '/'))

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
        c.subscribe_form = self.Forms.page_subscribe_form
        limit, pagenum, start = g.handle_paging(limit, page, default=25)
        pages = []
        criteria = dict(app_config_id=c.app.config._id)
        can_delete = g.security.has_access(c.app, 'delete')
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
                updated=page.last_updated
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
    @validate(dict(
            since=DateTimeConverter(if_empty=None, if_invalid=None),
            until=DateTimeConverter(if_empty=None, if_invalid=None),
            offset=validators.Int(if_empty=None),
            limit=validators.Int(if_empty=None)))
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


class PageController(WikiContentBaseController):

    class Widgets(WikiContentBaseController.Widgets):
        thread = ThreadWidget(
            page=None, limit=None, page_size=None, count=None, style='linear')
        attachment_list = AttachmentList()
        markdown_editor = MarkdownEdit()
        label_list = LabelListWidget()
        label_edit = LabelEdit()
        page_attachment = Attachment()
        related_artifacts = RelatedArtifactsWidget()
        attachments_field = RepeatedAttachmentField(label="Attach Files")
        hide_attachments_field = ew.Checkbox(name="hide_attachments",
                                             label="Hide Attachments")
        rename_descendants_field = ew.Checkbox(name="rename_descendants",
                                               label="Rename Subpages")

    def __init__(self, title):
        self.title = unquote(really_unicode(title))
        self.page = Page.query.get(
            app_config_id=c.app.config._id, title=self.title)
        if self.page is not None:
            self.attachment = WikiAttachmentsController(self.page)
        c.create_page_lightbox = self.Widgets.create_page_lightbox
        setattr(self, 'feed.atom', self.feed)
        setattr(self, 'feed.rss', self.feed)

    def _check_security(self):
        if self.page:
            g.security.require_access(self.page, 'read')
            if self.page.deleted:
                g.security.require_access(self.page, 'delete')
        else:
            g.security.require_access(c.app, 'create')

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

    @expose()
    def _lookup(self, pname, *remainder):
        page = Page.query.get(app_config_id=c.app.config._id, title=pname)
        if page:
            redirect(page.url())
        else:
            raise exc.HTTPNotFound

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'page_view.html')
    @validate(dict(version=validators.Int(if_empty=None)))
    def index(self, version=None, **kw):
        if not self.page:
            redirect('{}{}/edit'.format(
                c.app.url, urlquote(self.title)))

        c.thread = self.Widgets.thread
        c.attachment_list = self.Widgets.attachment_list
        c.attachment_widget = self.Widgets.page_attachment
        c.subscribe_form = self.Forms.page_subscribe_form
        c.related_artifacts_widget = self.Widgets.related_artifacts
        c.label_list = self.Widgets.label_list
        page = self.get_version(version)
        if page is None:
            if version:
                redirect('.?version=%d' % (version - 1))
            else:
                redirect('.')
        elif 'all' not in page.viewable_by and \
                c.user.username not in page.viewable_by:
            raise exc.HTTPForbidden(detail="You may not view this page.")
        cur = page.version
        if cur > 1:
            prev = cur - 1
        else:
            prev = None
        next_ = cur + 1
        hide_sidebar = not (c.app.show_left_bar or
                            g.security.has_access(self.page, 'edit'))
        page_html = self.page.get_rendered_html()
        hierarchy_items = self.get_hierarchy_items()
        return dict(
            page=page,
            cur=cur,
            prev=prev,
            next=next_,
            subscribed=Mailbox.subscribed(artifact=page),
            hide_sidebar=hide_sidebar,
            show_meta=c.app.show_right_bar,
            version=version,
            page_html=page_html,
            hierarchy_items=hierarchy_items,
        )

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'page_edit.html')
    def edit(self, default_content=u'', **kw):
        page_exists = self.page
        if page_exists:
            g.security.require_access(self.page, 'edit')
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
        return {
            'page': page,
            'page_exists': page_exists,
            'attachment_context_id': attachment_context_id
        }

    @without_trailing_slash
    @expose('json')
    @require_post()
    def delete(self):
        g.security.require_access(self.page, 'delete')
        Shortlink.query.remove(dict(ref_id=self.page.index_id()))
        self.page.deleted = True
        self.page.deleted_time = datetime.utcnow()
        self.deleter = c.user._id
        return dict(location=c.app.url + 'browse_pages')

    @without_trailing_slash
    @expose('json')
    @require_post()
    def undelete(self):
        g.security.require_access(self.page, 'delete')
        self.page.deleted = False
        Shortlink.from_artifact(self.page)
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
    @validate(dict(
            v1=validators.Int(),
            v2=validators.Int()))
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
        g.security.require_access(self.page, 'edit')
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
        'title': HTMLEscapeValidator(),
        'hide_attachments': validators.StringBool(if_empty=False,
                                                  if_missing=False),
        'rename_descendants': validators.StringBool(if_empty=False,
                                                    if_missing=False)
    })
    def update(self, title=None, text=None, labels=None, viewable_by=None,
               new_viewable_by=None, hide_attachments=False,
               rename_descendants=True, **kw):
        if not title:
            flash('You must provide a title for the page.', 'error')
            redirect('edit')
        if not self.page:
            # the page doesn't exist yet, so create it
            self.page = Page.upsert(self.title)
            self.page.viewable_by = ['all']
        else:
            g.security.require_access(self.page, 'edit')
        name_conflict = None
        if self.page.title != title:
            name_conflict = self._rename_page(title, rename_descendants)
        self.page.text = text
        if labels:
            self.page.labels = labels.split(',')
        else:
            self.page.labels = []

        posted_values = variable_decode(request.POST)
        for attachment in posted_values.get('new_attachments', []):
            if not hasattr(attachment, 'file'):
                continue
            self.page.attach(
                attachment.filename,
                attachment.file,
                content_type=attachment.type
            )
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

        redirect(
            c.app.url + really_unicode(self.page.title).encode('utf-8') +
            ('/' if not name_conflict else '/edit')
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
            'href': c.app.url,
            'children': root_cursor.all(),
            'child_count': root_cursor.count(),
            'more_href': c.app.url + 'browse_pages'
        })

        # get children along path
        title_segments = self.page.title.split('/')
        for i in range(0, len(title_segments)):
            end_title = title_segments[i]
            title_prefix = '/'.join(title_segments[:i + 1])
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
                'href': '{}{}'.format(c.app.url, title_prefix),
                'children': child_cursor.all(),
                'child_count': child_cursor.count(),
                'more_href': "{}search/search/?tool_q=title_s:*'{}'".format(
                    c.app.url, title_prefix)
            })
        return hierarchy_items


class WikiAttachmentController(AttachmentController):
    AttachmentClass = WikiAttachment
    edit_perm = 'edit'


class WikiAttachmentsController(AttachmentsController):
    AttachmentControllerClass = WikiAttachmentController


MARKDOWN_EXAMPLE = '''
# First-level heading

Some *emphasized* and **strong** text

#### Fourth-level heading

'''


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
            g.security.require_access(c.app, 'create')
            page = Page.upsert(title)
        else:
            g.security.require_access(page, 'edit')
        page.text = post_data['text']
        if 'labels' in post_data:
            page.labels = post_data['labels'].split(',')
        page.commit()


class WikiAdminController(DefaultAdminController):

    def _check_security(self):
        g.security.require_access(self.app, 'configure')

    @with_trailing_slash
    def index(self, **kw):
        redirect('home')

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'admin_home.html')
    def home(self):
        return dict(app=self.app,
                    home=self.app.root_page_name,
                    allow_config=g.security.has_access(self.app, 'configure'))

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'admin_options.html')
    def options(self):
        return dict(app=self.app,
                    allow_config=g.security.has_access(self.app, 'configure'))

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


PAGE_CONTROLLER_FUNCTIONS = ['attachment'] + [
    name for name, value in PageController.__dict__.items()
    if type(value) == types.FunctionType
]
