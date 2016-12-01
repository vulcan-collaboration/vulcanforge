# -*- coding: utf-8 -*-
#-*- python -*-
import logging
import datetime

from bson import ObjectId
from pylons import app_globals as g, tmpl_context as c
import pymongo
from ming.odm import session

from vulcanforge.common.app import Application
from vulcanforge.common.util import push_config
from vulcanforge.common.util.exception import exceptionless
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.discussion.model import Post
from vulcanforge.resources import Icon

# Local imports
from .version import __version__
from .model import Page, WikiAttachment, Globals, PageHistory
from vulcanforge.common.util.counts import get_history_info
from vulcanforge.tools.wiki.controllers import (
    RootController,
    PageController,
    RootRestController,
    WikiAdminController
)
from vulcanforge.tools.wiki.widgets.wiki import PageRenderer

LOG = logging.getLogger(__name__)
HOME_TEMPLATE = """
Welcome to your wiki!

This is the default page, edit it as you see fit. To add a page simply \
reference it within brackets, e.g.: [SamplePage].

The wiki uses [Markdown]({}) syntax.
"""


class ForgeWikiApp(Application):
    """This is the Wiki app for PyForge"""
    __version__ = __version__
    searchable = True
    tool_label = 'Wiki'
    static_folder = 'Wiki'
    default_mount_label = 'Wiki'
    default_mount_point = 'wiki'
    default_root_page_name = u'Wiki Home'
    icons = {
        24: '{ep_name}/images/wiki_24.png',
        32: '{ep_name}/images/wiki_32.png',
        48: '{ep_name}/images/wiki_48.png'
    }
    # whether its artifacts are referenceable from the repo browser
    reference_opts = dict(Application.reference_opts,
        can_reference=True,
        can_create=True,
        create_perm='write'
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
            "permission": "write"
        },
        "View Wiki": {"url": ""},
    }
    artifacts = {
        "page": {
            "model": Page,
            "controller": PageController,
            "renderer": PageRenderer
        }
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = RootController(self)
        self.api_root = RootRestController()
        self.admin = WikiAdminController(self)

    @classmethod
    def artifact_counts_by_kind(cls, app_configs, app_visits, tool_name):
        db, coll = PageHistory.get_pymongo_db_and_collection()
        return get_history_info(coll, app_configs, app_visits, tool_name)

    @classmethod
    def permissions(cls):
        perms = super(ForgeWikiApp, cls).permissions()
        perms.update({
            "read": "View wiki pages",
            "write": "Create, modify and delete wiki pages"
        })
        return perms

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

    def get_global_navigation_data(self):
        children = [
            {
                'label': page.featured_label or page.title,
                'url': page.url()
            }
            for page in self.get_featured_pages_cursor()
            if g.security.has_access(page, 'read')
        ]
        return {
            'children': children
        }

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
                'Set Home', admin_url + 'home', className='admin_modal'),
            SitemapEntry(
                'Options', admin_url + 'options', className='admin_modal'),
            SitemapEntry(
                'Manage Featured Pages', admin_url + 'featured',
                className='admin_modal')
        ]
        permissions = self.permissions()
        if permissions and g.security.has_access(self, 'admin'):
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
        allow_write = g.security.has_access(self, 'write')
        allow_admin = g.security.has_access(self, 'admin')
        if allow_write:
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
                'Home', c.app.url, ui_icon=Icon('', 'ico-home')
            ),
            SitemapEntry(
                'Browse Pages',
                c.app.url + 'browse_pages/',
                ui_icon=Icon('', 'ico-book_alt2')
            ),
            SitemapEntry(
                'Browse Labels',
                c.app.url + 'browse_tags/',
                ui_icon=Icon('', 'ico-list')
            )
        ])
        if hasattr(c, 'wikipage') and c.wikipage:
            links.append(
                SitemapEntry(
                    'Page'
                )
            )
            links.append(
                SitemapEntry(
                    'View',
                    c.wikipage.original_url(),
                    ui_icon=Icon('', 'ico-eye')
                )
            )
            if allow_admin and not c.wikipage.is_home:
                links.append(
                    SitemapEntry(
                        'Set As Home',
                        c.wikipage.original_url() + 'set_as_home',
                        ui_icon=Icon('', 'ico-pin'),
                        className='post-link'
                    )
                )
            if allow_write:
                links.append(
                    SitemapEntry(
                        'Edit',
                        c.wikipage.original_url() + 'edit',
                        ui_icon=Icon('', 'ico-edit')
                    )
                )
                if c.wikipage.deleted:
                    links.append(
                        SitemapEntry(
                            'Undelete',
                            c.wikipage.original_url() + 'undelete',
                            ui_icon=Icon('', 'ico-undelete'),
                            className='post-link'
                        )
                    )
                elif not c.wikipage.is_home:
                    links.append(
                        SitemapEntry(
                            'Delete',
                            c.wikipage.original_url() + 'delete',
                            ui_icon=Icon('', 'ico-delete'),
                            className='post-link'
                        )
                    )

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

    def get_featured_pages_cursor(self, sort=True):
        cursor = Page.query.find({
            'app_config_id': self.config._id,
            'featured': True
        })
        if sort:
            cursor.sort('featured_ordinal', pymongo.ASCENDING)
        return cursor

    def artifact_counts(self, since=None):
        # Rely on page history object only

        db, history_coll = PageHistory.get_pymongo_db_and_collection()

        new_history_count = history_count = total_size = 0
        history_objs = history_coll.aggregate([
            {'$match': {
                'app_config_id': self.config._id,
            }},
            {'$group': {
                '_id': '$artifact_id'
            }},
            {'$group': {
                '_id': 1,
                'count': { '$sum': 1}
            }}
        ])

        if history_objs['result']:
            history_count = history_objs['result'][0]['count']
        if since is not None and isinstance(since, datetime.datetime) :
            new_history_objs = history_coll.aggregate([
                {'$match': {
                    'app_config_id': self.config._id,
                    "_id": {"$gt":ObjectId.from_datetime(since)}
                }},
                {'$group': {
                    '_id': '$artifact_id'
                }},
                {'$group': {
                    '_id': 1,
                    'count': { '$sum': 1}
                }}
            ])
            if new_history_objs['result']:
                new_history_count = new_history_objs['result'][0]['count']

        db, attachment_coll = WikiAttachment.get_pymongo_db_and_collection()
        file_aggregate = attachment_coll.aggregate([
            {'$match': {
                'app_config_id': self.config._id,
            }},
            {'$group': {
                '_id': 1,
                'total_size': {'$sum': '$length'}
            }}
        ])
        if file_aggregate['result']:
            total_size = file_aggregate['result'][0]['total_size']

        return dict(
            new=new_history_count,
            all=history_count,
            total_size=total_size
        )