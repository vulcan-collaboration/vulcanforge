#-*- python -*-
import logging
import urllib
from itertools import islice

import pymongo
from webhelpers.text import truncate
from pylons import app_globals as g, tmpl_context as c, request
from tg import expose, redirect, flash
from tg.decorators import with_trailing_slash
from bson import ObjectId
from ming import schema

from vulcanforge.common.controllers.decorators import (
    require_post, validate_form, vardec)
from vulcanforge.common.app import (
    Application, DefaultAdminController)
from vulcanforge.common.types import SitemapEntry, ConfigOption
from vulcanforge.common.util import push_config
from vulcanforge.common.util.decorators import exceptionless
from vulcanforge.auth.model import User
from vulcanforge.resources import Icon
from vulcanforge.tools.forum import model as DM, util, version
from .controllers import RootController, RootRestController, TEMPLATE_DIR
from widgets.admin import OptionsAdmin, AddForum

LOG = logging.getLogger(__name__)


class ForgeDiscussionApp(Application):
    __version__ = version.__version__
    permissions = [
        'configure', 'read', 'unmoderated_post', 'post', 'moderate', 'admin'
    ]
    config_options = Application.config_options + [
        ConfigOption(
            'PostingPolicy',
            schema.OneOf('ApproveOnceModerated', 'ModerateAll'),
            'ApproveOnceModerated'
        )]
    PostClass = DM.ForumPost
    AttachmentClass = DM.ForumAttachment
    searchable = True
    tool_label = 'Discussion'
    static_folder = 'ForgeForum'
    default_mount_label = 'Discussion'
    default_mount_point = 'discussion'
    icons = {
        24: 'images/forums_24.png',
        32: 'images/forums_32.png',
        48: 'images/forums_48.png'
    }
    reference_opts = dict(Application.reference_opts,
        can_reference=True,
        can_create=True,
        create_perm='post'
    )
    admin_description = (
        "The forums provide a locale to initiate conversations relevant to "
        "your project. To use the forums, create a couple of forums, post "
        "introductory messages, and check out the spam control and post "
        "moderation options."
    )
    admin_actions = {
        "Create Forum": {
            "url": "?new_forum=True",
            "permission": "post"
        },
        "View Forums": {"url": ""}
    }
    permission_descriptions = dict(Application.permission_descriptions,
        post="create new posts",
        moderate="moderate new content",
        unmoderated_post="add content without moderation"
    )
    default_acl = {
        'Admin': permissions,
        'Developer': ['moderate'],
        '*authenticated': ['post', 'unmoderated_post'],
        '*anonymous': ['read']
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = RootController()
        self.api_root = RootRestController()
        self.admin = ForumAdminController(self)
        self.default_forum_preferences = dict(
            subscriptions={})

    def has_access(self, user, topic):
        f = DM.Forum.query.get(shortname=topic.replace('.', '/'),
                               app_config_id=self.config._id)
        return g.security.has_access(f, 'post', user=user)

    def handle_message(self, topic, message):
        LOG.info('Message from %s (%s)',
                 topic, self.config.options.mount_point)
        LOG.info('Headers are: %s', message['headers'])
        shortname=urllib.unquote_plus(topic.replace('.', '/'))
        forum = DM.Forum.query.get(
            shortname=shortname, app_config_id=self.config._id)
        if forum is None:
            LOG.error("Error looking up forum: %r", shortname)
            return
        self.handle_artifact_message(forum, message)

    def main_menu(self):
        """
        Apps should provide their entries to be added to the main nav
        :return: a list of :class:`SitemapEntries <vulcanforge.common.types.SitemapEntry>`

        """
        return [ SitemapEntry(
                self.config.options.mount_label.title(),
                '.')]

    @property
    @exceptionless([], LOG)
    def sitemap(self):
        menu_id = self.config.options.mount_label.title()
        with push_config(c, app=self):
            return [
                SitemapEntry(menu_id, '.')[self.sidebar_menu()] ]

    @property
    def forums(self):
        cursor = DM.Forum.query.find(dict(app_config_id=self.config._id))
        cursor.sort('ordinal', pymongo.ASCENDING)
        return cursor.all()

    @property
    def top_forums(self):
        return self.subforums_of(None)

    def subforums_of(self, parent_id):
        cursor = DM.Forum.query.find(dict(
                app_config_id=self.config._id,
                parent_id=parent_id,
                ))
        cursor.sort('ordinal', pymongo.ASCENDING)
        return cursor.all()

    def admin_menu(self):
        admin_url = c.project.url()+'admin/'+self.config.options.mount_point+'/'
        links = super(ForgeDiscussionApp, self).admin_menu()
        if g.security.has_access(self, 'configure'):
            links.append(SitemapEntry('Forums', admin_url + 'forums'))
        return links

    def sidebar_menu(self):
        try:
            l = []
            moderate_link = None
            forum_links = []
            forums = self.top_forums
            if forums:
                for f in forums:
                    if f.url() in request.url and g.security.has_access(f, 'moderate'):
                        moderate_link = SitemapEntry(
                            'Moderate',
                            "%smoderate/" % f.url(),
                            ui_icon='ico-moderate',
                            small=DM.ForumPost.query.find({
                                'discussion_id': f._id,
                                'status': {'$ne': 'ok'}
                            }).count()
                        )
                    forum_links.append(
                        SitemapEntry(
                            f.name,
                            f.url(),
                            ui_icon=Icon('', 'ico-chat'),
                            className='nav_child'
                        )
                    )
            if g.security.has_access(c.app, 'post'):
                l.append(
                    SitemapEntry(
                        'Create Topic',
                        c.app.url + 'create_topic',
                        ui_icon=Icon('', 'ico-plus')
                    )
                )
            if g.security.has_access(c.app, 'configure'):
                l.append(
                    SitemapEntry(
                        'Add Forum',
                        c.app.url + 'new_forum',
                        ui_icon=Icon('', 'ico-plus')
                    )
                )
                l.append(
                    SitemapEntry(
                        'Admin Forums',
                        c.project.url() + 'admin/' + \
                            self.config.options.mount_point + '/forums',
                        ui_icon=Icon('', 'ico-cog')
                    )
                )
            if moderate_link:
                l.append(moderate_link)
            # if we are in a thread and not anonymous, provide placeholder links to use in js
            if '/thread/' in request.url and c.user not in (None, User.anonymous()):
                l.append(SitemapEntry(
                        'Mark as Spam', 'flag_as_spam',
                        ui_icon=Icon('','ico-star'), className='sidebar_thread_spam'))
            # Get most recently-posted-to-threads across all discussions in this app
            recent_threads = (
                thread for thread in (
                    DM.ForumThread.query.find(
                        dict(app_config_id=self.config._id))
                    .sort([
                            ('last_post_date', pymongo.DESCENDING),
                            ('mod_date', pymongo.DESCENDING)])
                    ))
            recent_threads = (
                t for t in recent_threads 
                if (g.security.has_access(t, 'configure') or
                    not t.discussion.deleted))
            recent_threads = ( t for t in recent_threads if t.status == 'ok' )
            # Limit to 3 threads
            recent_threads = list(islice(recent_threads, 3))
            # Add to sitemap
            if recent_threads:
                l.append(SitemapEntry('Recent Topics'))
                l += [
                    SitemapEntry(
                        truncate(thread.subject, 72),
                        thread.url(),
                        className='nav_child', small=thread.post_count)
                    for thread in recent_threads ]
            if forum_links:
                l.append(SitemapEntry('Forums'))
                l.append(
                    SitemapEntry(
                        'Show All',
                        c.app.url,
                        ui_icon=Icon('','ico-list')))
                l = l + forum_links
            l.append(SitemapEntry('Help'))
            l.append(
                SitemapEntry(
                    'Markdown Syntax',
                    c.app.url + 'markdown_syntax',
                    ui_icon=Icon('','ico-info'),
                    className='nav_child'))
            return l
        except Exception: # pragma no cover
            LOG.exception('sidebar_menu')
            return []

    def install(self, project, acl=None):
        """Set up any default permissions and roles here"""
        # Don't call super install here, as that sets up discussion for a tool
        self.set_acl(acl)
        self.config.reference_opts = self.reference_opts
        util.create_forum(self, new_forum=dict(
            shortname='general',
            create='on',
            name='General Discussion',
            description='Forum about anything you want to talk about.',
            parent=''))

    def uninstall(self, project):
        """Remove all the tool's artifacts from the database"""
        DM.Forum.query.remove(dict(app_config_id=self.config._id))
        DM.ForumThread.query.remove(dict(app_config_id=self.config._id))
        DM.ForumPost.query.remove(dict(app_config_id=self.config._id))
        super(ForgeDiscussionApp, self).uninstall(project)


class ForumAdminController(DefaultAdminController):

    class Forms(DefaultAdminController.Forms):
        options_admin = OptionsAdmin()
        add_forum = AddForum()

    def _check_security(self):
        g.security.require_access(self.app, 'admin')

    @with_trailing_slash
    def index(self, **kw):
        redirect('forums')

    @expose(TEMPLATE_DIR + 'admin_options.html')
    def options(self):
        c.options_admin = self.Forms.options_admin
        return dict(
            app=self.app,
            form_value=dict(
                PostingPolicy=self.app.config.options.get('PostingPolicy')
        ))

    @expose(TEMPLATE_DIR + 'admin_forums.html')
    def forums(self, add_forum=None, **kw):
        c.add_forum = self.Forms.add_forum
        return dict(
            app=self.app,
            allow_config=g.security.has_access(self.app, 'configure'),
            add_forum=add_forum
        )

    @vardec
    @expose()
    @require_post()
    def update_forums(self, forum=None, **kw):
        if forum is None:
            forum = []
        for f in forum:
            forum = DM.Forum.query.get(_id=ObjectId(str(f['id'])))
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
        f = util.create_forum(self.app, add_forum)
        redirect(f.url())
