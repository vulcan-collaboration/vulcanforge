import logging
from cStringIO import StringIO
import os

from ming.odm import session
import pkg_resources
from pylons import app_globals as g, tmpl_context as c

from vulcanforge.auth.schema import ACE
from vulcanforge.common.types import ConfigOption, SitemapEntry
from vulcanforge.discussion.model import (
    Discussion,
    DiscussionAttachment,
    Post
)
from vulcanforge.notification.model import Mailbox
from .controllers import DefaultAdminController
from vulcanforge.project.model import ProjectRole

LOG = logging.getLogger(__name__)


class Application(object):
    """
    The base VulcanForge pluggable application

    :var status: the status level of this app.  'production' apps are available
        to all projects
    :var bool searchable: toggle if the search box appears in the left menu
    :var permissions: a dictionary of named permissions used by the app, the values describe what the permissions enable
    :var sitemap: a list of :class:`SitemapEntries <vulcanforge.common.types.SitemapEntry>`
        to create an app navigation.
    :var bool installable: toggle if the app can be installed in a project
    :var Controller self.root: the root Controller used for the app
    :var Controller self.api_root: a Controller used for API access at
        /rest/<neighborhood>/<project>/<app>/
    :var Controller self.admin: a Controller used in the admin interface

    """

    __version__ = None
    config_options = [
        ConfigOption('mount_point', str, 'app'),
        ConfigOption('mount_label', str, 'app'),
        ConfigOption('ordinal', int, '0')]
    status_map = ['production', 'beta', 'alpha', 'user']
    status = 'production'
    root = None  # root controller
    api_root = None  # root rest controller
    static_dir = 'static'
    template_dir = 'templates'
    permissions = dict(
        admin='Configure this tool and its permissions',
        write='Create new artifacts or modify old ones',
        read='View tool artifacts'
    )
    sitemap = []
    searchable = False
    DiscussionClass = Discussion
    PostClass = Post
    AttachmentClass = DiscussionAttachment
    tool_label = 'Tool'
    static_folder = 'Tool'
    default_mount_label = 'Tool Name'
    default_mount_point = 'tool'
    icons = {
        24: 'images/default_tool_icons/24.png',
        32: 'images/default_tool_icons/32.png',
        48: 'images/default_tool_icons/48.png'
    }
    artifacts = {}
    # admin description
    admin_description = ""
    # used to associate actions with app instances on project admin interface
    admin_actions = {}
    # used for auto-creating references to artifacts in the app
    reference_opts = dict(
        new_uri=u'new_with_reference',
        can_reference=False,
        can_create=False,
        create_perm='write'
    )
    permission_descriptions = {
        "admin": "edit access control to this tool",
        "read": "view this tool"
    }
    default_acl = {}
    is_customizable = True
    visible_to_role = 'read'

    def __init__(self, project, app_config_object):
        self.project = project
        self.config = app_config_object
        self.admin = DefaultAdminController(self)
        self.url = self.config.url()

    @classmethod
    def _iter_path_spec(cls, attr):
        for cls_ in filter(lambda _c: issubclass(_c, Application), cls.mro()):
            path = getattr(cls_, attr, None)
            if path and not path.startswith('/'):  # relative path
                parent_module = '.'.join(cls_.__module__.rsplit('.', 1)[:-1])
                path = pkg_resources.resource_filename(parent_module, path)
            if os.path.exists(path):
                yield path

    @classmethod
    def static_directories(cls):
        folders = []
        for folder in cls._iter_path_spec('static_dir'):
            folders.insert(0, folder)
        return folders

    @classmethod
    def template_directories(cls):
        return list(cls._iter_path_spec('template_dir'))

    @classmethod
    def can_create(cls, artifact):
        return True

    @classmethod
    def icon_url(cls, size, ep_name):
        icon_resource = cls.icons.get(size)
        if icon_resource:
            return g.resource_manager.absurl(
                icon_resource.format(ep_name=ep_name))

    @property
    def acl(self):
        return self.config.acl

    def parent_security_context(self):
        return self.config.parent_security_context()

    @classmethod
    def status_int(cls):
        return cls.status_map.index(cls.status)

    def has_access(self, user, topic):
        """Whether the user has access to send email to the given topic"""
        return False

    def is_visible_to(self, user):
        """Whether the user can view the app."""
        #return has_access(self, 'read')(user=user)
        raise DeprecationWarning()

    def subscribe_admins(self):
        admins = g.security.credentials.userids_with_named_role(
            self.project._id, 'Admin')
        for uid in admins:
            Mailbox.subscribe(
                type='direct',
                user_id=uid,
                project_id=self.project._id,
                app_config_id=self.config._id)

    @classmethod
    def default_options(cls):
        """:return: the default config options"""
        return dict(
            (co.name, co.default)
                for co in cls.config_options)

    def set_acl(self, acl_spec=None):
        """Install default acl. Note that we cannot modify the config acl
        directly, because ming does not note the change.

        """
        if acl_spec is None:
            acl_spec = self.default_acl
        acl = []
        for role, permissions in acl_spec.iteritems():
            pr = ProjectRole.by_name(role)
            if pr is not None:
                for permission in permissions:
                    acl.append(ACE.allow(pr._id, permission))
            else:
                LOG.warning(
                    'project role %s not found on %s', role, repr(self))
        self.config.acl = acl
        if acl:
            self.config.clean_acl()

    def install(self, project, acl=None):
        """Whatever logic is required to initially set up a tool"""

        # Create the discussion object
        discussion = self.DiscussionClass(
            shortname=self.config.options.mount_point,
            name='{} Discussion'.format(self.config.options.mount_point),
            description='Forum for {} comments'.format(
                self.config.options.mount_point)
        )
        session(discussion).flush()
        self.config.discussion_id = discussion._id
        self.config.visible_to_role = self.visible_to_role
        self.config.reference_opts = self.reference_opts.copy()
        self.subscribe_admins()
        self.set_acl(acl)

    def uninstall(self, project=None, project_id=None):
        """Whatever logic is required to tear down a tool"""
        from vulcanforge.artifact.model import ArtifactReference, Shortlink
        if project_id is None:
            project_id = project._id
            # De-index all the artifacts belonging to this tool in one fell
            # swoop
        g.solr.delete(q='project_id_s:"%s" AND mount_point_s:"%s"' % (
            project_id, self.config.options['mount_point']))
        discussions = Discussion.query.find({
            'project_id': project_id,
            'app_config_id': self.config._id})
        for d in discussions:
            d.delete()
        ArtifactReference.query.remove({
            'artifact_reference.app_config_id': self.config._id
        })
        Shortlink.query.remove({'app_config_id': self.config._id})
        self.config.delete()
        session(self.config).flush()

    def main_menu(self):
        """
        Apps should provide their entries to be added to the main nav
        :return: a list of :class:`SitemapEntries <vulcanforge.common.types.SitemapEntry>`

        """
        return self.sitemap

    def sidebar_menu(self):
        """
        Apps should override this to provide their menu
        :return: a list of :class:`SitemapEntries <vulcanforge.common.types.SitemapEntry>`
        """
        return []

    def admin_menu(self):
        """
        Apps may override this to provide additional admin menu items
        :return: a list of :class:`SitemapEntries <vulcanforge.common.types.SitemapEntry>`
        """
        admin_url = c.project.url() + 'admin/' +\
                    self.config.options.mount_point + '/'
        links = []

        if self.permissions and g.security.has_access(c.project, 'admin'):
            links.append(
                SitemapEntry(
                    'Permissions',
                    admin_url + 'permissions',
                    className='nav_child'
                )
            )
        if len(self.config_options) > 3:
            links.append(
                SitemapEntry(
                    'Options',
                    admin_url + 'options',
                    className='admin_modal'
                )
            )
        return links

    def handle_message(self, topic, message):
        """Handle incoming email msgs addressed to this tool"""
        pass

    def handle_artifact_message(self, artifact, message):
        # Find ancestor comment
        in_reply_to = message.get('in_reply_to', [])
        if in_reply_to:
            parent_id = in_reply_to[0]
        else:
            parent_id = None
        thd = artifact.get_discussion_thread(message)
        # Handle attachments
        message_id = message['message_id']
        if message.get('filename'):
            # Special case - the actual post may not have been created yet
            LOG.info('Saving attachment %s', message['filename'])
            fp = StringIO(message['payload'])
            self.AttachmentClass.save_attachment(
                message['filename'], fp,
                content_type=message.get(
                    'content_type', 'application/octet-stream'),
                discussion_id=thd.discussion_id,
                thread_id=thd._id,
                post_id=message_id,
                artifact_id=message_id)
            return
            # Handle duplicates
        post = self.PostClass.query.get(_id=message_id)
        if post:
            LOG.info(
                'Existing message_id %s found - saving this as text attachment'
                % message_id
            )
            fp = StringIO(message['payload'])
            post.attach(
                'alternate', fp,
                content_type=message.get(
                    'content_type', 'application/octet-stream'),
                discussion_id=thd.discussion_id,
                thread_id=thd._id,
                post_id=message_id)
        else:
            text = message['payload'] or '--no text body--'
            post = thd.post(
                message_id=message_id,
                parent_id=parent_id,
                text=text,
                subject=message['headers'].get('Subject', 'no subject'))

    def get_markdown(self):
        """
        App definitions can override this method to use a different markdown
        setup.

        @status: Implemented to consolidate which markdown logic to the
        application instance for markdown preview mode. Not used consistently
        throughout codebase.

        @return: an instance of markdown ready to use for conversion
        """
        return g.markdown

    def get_calendar_events(self, date_start, date_end):
        """Apps can provide events to the Calendar App"""
        return []
