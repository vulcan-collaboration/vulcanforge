#-*- python -*-
import logging
import urllib
import datetime
from itertools import islice

from bson import ObjectId
import pymongo
from webhelpers.text import truncate
from pylons import app_globals as g, tmpl_context as c, request
from tg import expose
from ming import schema

from vulcanforge.common.app import (
    Application, DefaultAdminController)
from vulcanforge.common.tool import SitemapEntry, ConfigOption
from vulcanforge.common.util import push_config
from vulcanforge.common.util.exception import exceptionless
from vulcanforge.common.util.counts import get_history_info
from vulcanforge.resources import Icon
from vulcanforge.tools.forum import model as DM, util, version
from .controllers import RootController, RootRestController, TEMPLATE_DIR
from widgets.admin import OptionsAdmin

LOG = logging.getLogger(__name__)


class ForgeDiscussionApp(Application):
    __version__ = version.__version__
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
        24: '{ep_name}/images/forums_24.png',
        32: '{ep_name}/images/forums_32.png',
        48: '{ep_name}/images/forums_48.png'
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

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = RootController()
        self.api_root = RootRestController()
        self.admin = ForumAdminController(self)
        self.default_forum_preferences = dict(
            subscriptions={})

    @classmethod
    def artifact_counts_by_kind(cls, app_configs, app_visits, tool_name,
                                trefs=[]):
        db, coll = DM.ForumPostHistory.get_pymongo_db_and_collection()
        return get_history_info(coll, app_configs, app_visits, tool_name,
                                trefs)

    @classmethod
    def permissions(cls):
        perms = super(ForgeDiscussionApp, cls).permissions()
        perms['admin'] = 'Create forums and admin them'
        return perms

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

    def admin_menu(self):
        admin_url = c.project.url() + 'admin/' + \
                    self.config.options.mount_point + '/'
        links = []
        permissions = self.permissions()
        if permissions and g.security.has_access(self, 'admin'):
            links.extend([
                SitemapEntry(
                    'Permissions',
                    admin_url + 'permissions',
                    className='nav_child')
            ])
        return links

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

    def sidebar_menu(self):
        l = []

        l.append(SitemapEntry('Forums'))
        l.append(
            SitemapEntry(
                'Show All',
                c.app.url,
                ui_icon=Icon('','ico-list')))
        if g.security.has_access(c.app, 'admin'):
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
                    c.app.url + 'forums',
                    ui_icon=Icon('', 'ico-cog')
                )
            )

        if hasattr(c, "discussion"):
            l.append(SitemapEntry(c.discussion.name))
            l.append(
                SitemapEntry(
                    'Show Topics',
                    c.discussion.url(),
                    ui_icon=Icon('', 'ico-list')))
            if g.security.has_access(c.app, 'post') and not c.discussion.deleted:
                l.append(
                    SitemapEntry(
                        'Create Topic',
                        c.discussion.url() + 'create_topic',
                        ui_icon=Icon('', 'ico-plus')
                    )
                )
            if g.security.has_access(c.discussion, 'moderate') and \
                            c.app.config.options.get('PostingPolicy') != 'ApproveAll':
                l.append(
                    SitemapEntry(
                        'Moderate',
                        c.discussion.url() + 'moderate',
                        ui_icon='ico-moderate',
                        small=DM.ForumPost.query.find({
                            'discussion_id': c.discussion._id,
                            'status': {'$ne': 'ok'}
                        }).count()
                    )
                )

        # Get most recently-posted-to-threads across all discussions in
        # this app
        recent_threads = (
            thread for thread in (
            DM.ForumThread.query.find(
                dict(app_config_id=self.config._id))
                .sort([
                ('last_post_date', pymongo.DESCENDING),
                ('mod_date', pymongo.DESCENDING)])
        ))
        recent_threads = (t for t in recent_threads if t.status == 'ok' and not t.discussion.deleted)
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
                for thread in recent_threads]

        l.append(SitemapEntry('Help'))
        l.append(
            SitemapEntry(
                'Markdown Syntax',
                c.app.url + 'markdown_syntax',
                ui_icon=Icon('','ico-info'),
                className='nav_child'))
        return l

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

    def artifact_counts(self, since=None):
        # Rely on page history object only

        db, history_coll = DM.ForumPostHistory.get_pymongo_db_and_collection()

        new_history_count = history_count = total_size = 0
        history_objs = list(history_coll.aggregate([
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
        ]))

        if history_objs:
            history_count = history_objs[0]['count']
        if since is not None and isinstance(since, datetime.datetime) :
            new_history_objs = list(history_coll.aggregate([
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
            ]))
            if new_history_objs:
                new_history_count = new_history_objs[0]['count']

        db, attachment_coll = \
            DM.ForumAttachment.get_pymongo_db_and_collection()
        file_aggregate = list(attachment_coll.aggregate([
            {'$match': {
                'app_config_id': self.config._id,
            }},
            {'$group': {
                '_id': 1,
                'total_size': {'$sum': '$length'}
            }}
        ]))
        if file_aggregate:
            total_size = file_aggregate[0]['total_size']

        return dict(
            new=new_history_count,
            all=history_count,
            total_size=total_size
        )


class ForumAdminController(DefaultAdminController):

    class Forms(DefaultAdminController.Forms):
        options_admin = OptionsAdmin()

    def _check_security(self):
        g.security.require_access(self.app, 'admin')

    @expose(TEMPLATE_DIR + 'admin_options.html')
    def options(self):
        c.options_admin = self.Forms.options_admin
        return dict(
            app=self.app,
            form_value=dict(
                PostingPolicy=self.app.config.options.get('PostingPolicy')
        ))
