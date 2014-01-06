import os
import logging
from datetime import datetime
from pprint import pformat
import urllib
import bson
from markupsafe import Markup
import pkg_resources

import pymongo
from paste.deploy.converters import asbool
from webob import exc
from pylons import app_globals as g, tmpl_context as c, request
from formencode import validators
from tg import expose, redirect, validate, response, config
from tg.flash import flash
from tg.controllers import RestController

from vulcanforge.common import exceptions, helpers as h
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import vardec
from vulcanforge.common.types import SitemapEntry
from vulcanforge.common.util import push_config, nonce
from vulcanforge.common.util.decorators import exceptionless
from vulcanforge.common.app import Application
from vulcanforge.common.validators import DateTimeConverter
from vulcanforge.auth.schema import ACE
from vulcanforge.auth.model import WorkspaceTab
from vulcanforge.artifact.model import ArtifactReference
from vulcanforge.artifact.widgets import short_artifact_link_data
from vulcanforge.messaging.model import ConversationStatus
from vulcanforge.neighborhood.marketplace.model import UserAdvertisement
from vulcanforge.notification.model import Notification
from vulcanforge.project.widgets import ProjectListWidget
from vulcanforge.project.model import Project, ProjectFile
from vulcanforge.notification.widgets import ActivityFeed
from vulcanforge.tools.admin import model as AM
from vulcanforge.tools.home import model as PHM
from vulcanforge.tools.home.project_main import ProjectHomeController
from .widgets import EditProfileForm
from vulcanforge.common.controllers.decorators import (
    require_post, validate_form)

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.tools.profile:templates/'


class UserProfileApp(Application):

    def __init__(self, user_project, config):
        Application.__init__(self, user_project, config)
        users = user_project.users()
        # user_project will have no users for a brief period during install
        if users:
            self.user = user_project.users()[0]  # assumes no other members
        else:
            self.user = c.user
        self.root = UserProfileController(self.user)

    @property
    @exceptionless([], LOG)
    def sitemap(self):
        return []

    @exceptionless([], LOG)
    def sidebar_menu(self):
        menu = []
        if g.security.has_access(c.project, 'admin'):
            menu.extend([
                SitemapEntry('Profile', self.url),
                SitemapEntry('Settings'),
                SitemapEntry('Edit Profile Info', self.url + 'edit_profile')
            ])
        if c.user._id == self.user._id:
            menu.extend([
                SitemapEntry('Preferences', '/auth/prefs/'),
                SitemapEntry('Subscriptions', "/auth/prefs/subscriptions")
            ])
        return menu

    def admin_menu(self):
        return []

    def install(self, project, **kw):
        pr = c.project.project_role(self.user)
        if pr:
            self.config.acl = [
                ACE.allow(pr._id, perm) for perm in self.permissions]

    def uninstall(self, project):  # pragma no cover
        raise NotImplementedError("uninstall")


class WorkspaceTabController(RestController):

    @expose('json')
    def get_all(self):
        g.security.require_access(c.project, 'read')
        results = WorkspaceTab.query.find(dict(user_id=c.user._id))
        return {'results': [t.__json__() for t in results]}

    # Create
    @expose('json')
    def post(self, href=None, title=None, type=None, order=0, state=None,
             **kw):
        g.security.require_access(c.project, 'write')
        if href is None or title is None:
            raise exceptions.AJAXMethodNotAllowed(
                'Not enough arguments supported')

        if WorkspaceTab.query.get(user_id=c.user._id, href=href):
            raise exceptions.AJAXMethodNotAllowed(
                'Tab duplication is not allowed')

        new_tab = WorkspaceTab(
            user_id=c.user._id,
            title=title,
            type=type,
            href=href,
            order=int(order),
            state=state
        )

        return new_tab.__json__()

    # Update
    @expose()
    def put(self, object_id, operation, value, **kwargs):
        g.security.require_access(c.project, 'write')
        tab = WorkspaceTab.query.get(
            _id=bson.ObjectId(object_id), user_id=c.user._id)
        if not tab:
            raise exceptions.AJAXNotFound('Tab not found')

        if operation == 'SET_TITLE':
            tab.title = value

    @expose()
    @require_post()
    def reorder(self, tab_ids, **kw):
        tab_ids = tab_ids.split(',')
        for order, tab_id in enumerate(tab_ids):
            tab = WorkspaceTab.query.get(
                _id=bson.ObjectId(tab_id), user_id=c.user._id)
            if tab:
                tab.order = order

    @expose()
    def post_delete(self, object_id, **kwargs):
        g.security.require_access(c.project, 'write')
        tab = WorkspaceTab.query.get(
            _id=bson.ObjectId(object_id), user_id=c.user._id)
        if not tab:
            raise exceptions.AJAXNotFound('Tab not found')

        tab.delete()


class ReferenceBinController(RestController):

    _custom_actions = ['delete_reference']

    @expose('json')
    def get_all(self):
        g.security.require_access(c.project, 'read')
        return c.user.get_workspace_references()

    # Create
    @expose('json')
    def post(self, ref_id=None, last_mod='0', **kwargs):
        g.security.require_access(c.project, 'write')
        if not ref_id:
            raise exceptions.AJAXMethodNotAllowed(
                'Not enough arguments supported')

        ref_id = urllib.unquote(ref_id)
        if ref_id not in c.user.workspace_references:

            current_last_mod_str = h.stringify_datetime(
                c.user.workspace_references_last_mod)
            if last_mod >= current_last_mod_str:
                c.user.workspace_references.append(ref_id)
                c.user.workspace_references_last_mod = datetime.utcnow()
            else:
                raise exceptions.AJAXNotAcceptable('Link bin was out of sync')

        artifact = ArtifactReference.artifact_by_index_id(ref_id)

        return {
            'link_descriptor': short_artifact_link_data(artifact),
            'last_mod': h.stringify_datetime(
                c.user.workspace_references_last_mod)
        }

    @expose('json')
    @require_post()
    def delete_reference(self, ref_id=None, last_mod=None, **kwargs):
        if not last_mod:
            last_mod = '0'
        g.security.require_access(c.project, 'write')
        if not ref_id:
            raise exceptions.AJAXMethodNotAllowed(
                'Not enough arguments supported')
        ref_id = h.urlunquote(ref_id)
        try:
            current_last_mod_str = h.stringify_datetime(
                c.user.workspace_references_last_mod)
            if last_mod >= current_last_mod_str:
                c.user.workspace_references.remove(ref_id)
                c.user.workspace_references_last_mod = datetime.utcnow()
                return {
                    'last_mod': h.stringify_datetime(
                        c.user.workspace_references_last_mod)
                }
            else:
                raise exceptions.AJAXNotAcceptable('Link bin was out of sync')

        except ValueError:
            raise exceptions.AJAXNotFound(
                'Error during linkbin reference removal')


class UserProfileController(BaseController):

    workspace_tabs = WorkspaceTabController()
    reference_bin = ReferenceBinController()

    class Widgets(BaseController.Widgets):
        project_list = ProjectListWidget()
        activity_feed = ActivityFeed()

    class Forms(BaseController.Forms):
        edit_profile_form = EditProfileForm()

    def __init__(self, user, **kw):
        super(UserProfileController, self).__init__(**kw)
        self.home_controller = ProjectHomeController()
        self.user = user

    def _check_security(self):
        g.security.require_access(c.project, 'read')

    @expose(TEMPLATE_DIR + 'user_index.html')
    def index(self, **kw):
        c.project_list = self.Widgets.project_list
        c.activity_feed = self.Widgets.activity_feed
        is_self = self.user._id == c.user._id

        # projects in which user has named role
        projects = []
        for p in self.user.my_projects():
            if p.is_real() and not p.private_project_of() and \
                    g.security.has_access(p, 'read'):
                p_dict = p.index()
                p_dict['status'] = ', '.join(
                    pr.name for pr in p.named_roles_in(self.user))
                if is_self and p.home_ac:
                    if p.user_requested_leave(self.user):
                        p_dict['status'] += ' - renouncement under evaluation'
                    elif not g.security.has_access(c.project, 'admin'):
                        p_dict.update({
                            'cancel_url': (
                                p.home_ac.url() + 'renounce_membership'),
                            'cancel_text': 'Renounce Membership'
                        })
                projects.append(p_dict)

        # projects to which user has requested membership
        mem_reqs = AM.MembershipRequest.query.find({'user_id': self.user._id})
        for mem_req in mem_reqs:
            if g.security.has_access(mem_req.project, 'read'):
                p_dict = mem_req.project.index()
                p_dict['status'] = 'Membership Request Under Evaluation'
                if is_self:
                    p_dict.update({
                        'cancel_url': (
                            mem_req.project.home_ac.url() + 'cancel_request'),
                        'cancel_text': 'Cancel Membership Request'
                    })
                projects.append(p_dict)

        # projects to which user has been invited
        vites = AM.MembershipInvitation.query.find({'user_id': self.user._id})
        for vite in vites:
            if is_self or g.security.has_access(vite.project, 'read'):
                p_dict = vite.project.index()
                p_dict['status'] = 'Invited'
                if is_self:
                    if vite.project.neighborhood.user_can_register(self.user):
                        p_dict.update({
                            'cancel_url': '{}accept_membership/{}'.format(
                                c.app.url,
                                vite.project.shortname
                            ),
                            'cancel_text': 'Accept Invitation'
                        })
                    else:
                        reject_msg = 'must leave current team to accept'
                        p_dict['status'] += ' - ' + reject_msg
                projects.append(p_dict)

        # For inviting the user to a project
        admin_opts = []
        if not is_self:
            for p in c.user.my_projects():
                if g.security.has_access(p, 'admin') and \
                p.is_real() and \
                not p.user_in_project(self.user.username) and \
                not p.user_invited(self.user):
                    admin_opts.append(
                        '{{project_id:"{}",project_name:"{}"}}'.format(
                            str(p._id), p.name.replace('"', '\\"')
                        ))

        # get activity feed notifications
        read_roles = ' OR '.join(g.security.get_user_read_roles())
        solr_params = {
            'q': 'author_id_s:{}'.format(self.user._id),
            'fq': [
                'type_s:Notification',
                'read_roles:({})'.format(read_roles),
            ],
            'sort': 'pubdate_dt desc',
            'rows': 10,
        }
        solr_results = g.solr.search(**solr_params)
        # convert to list of actual notification instances to use existing
        # activity feed widgets
        notification_ids = [d['notification_id_s'] for d in solr_results.docs]
        notification_cursor = Notification.query.find({
            '_id': {'$in': notification_ids},
        })
        notification_cursor.sort('pubdate', pymongo.DESCENDING)
        notifications = notification_cursor.all()

        return {
            'user': self.user,
            'is_self': is_self,
            'project_opts': '[' + ','.join(admin_opts) + ']'
                            if admin_opts else None,
            'notifications': notifications,
            'projects': projects
        }

    @expose(TEMPLATE_DIR + 'user_dashboard_configuration.html')
    def configuration(self):
        return dict(user=self.user)

    @expose()
    @validate(dict(
            since=DateTimeConverter(if_empty=None),
            until=DateTimeConverter(if_empty=None),
            page=validators.Int(if_empty=None),
            limit=validators.Int(if_empty=None)))
    def feed(self, since=None, until=None, page=None, limit=None):
        if request.environ['PATH_INFO'].endswith('.atom'):
            feed_type = 'atom'
        else:
            feed_type = 'rss'
        title = 'Recent posts by %s' % self.user.display_name
        feed = Notification.feed(
            {'author_id': self.user._id},
            feed_type,
            title,
            c.project.url(),
            title,
            since, until, page, limit)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        return feed.writeString('utf-8')

    @vardec
    @expose()
    @require_post()
    def update_configuration(self, divs=None, layout_class=None, new_div=None,
                             **kw):
        g.security.require_access(c.project, 'write')
        config = PHM.PortalConfig.current()
        config.layout_class = layout_class
        # Handle updated and deleted divs
        if divs is None:
            divs = []
        new_divs = []
        for div in divs:
            LOG.info('Got div update:%s', pformat(div))
            if div.get('del'):
                continue
            new_divs.append(div)
        # Handle new divs
        if new_div:
            new_divs.append(dict(name=nonce(), content=[]))
        config.layout = []
        for div in new_divs:
            content = []
            for w in div.get('content', []):
                if w.get('del'):
                    continue
                mp, wn = w['widget'].split('/')
                content.append(dict(mount_point=mp, widget_name=wn))
            if div.get('new_widget'):
                content.append(dict(
                    mount_point='profile',
                    widget_name='welcome'
                ))
            config.layout.append(dict(
                    name=div['name'],
                    content=content))
        redirect('configuration')

    @expose(TEMPLATE_DIR + 'edit_profile.html')
    def edit_profile(self, **kw):
        g.security.require_access(c.project, 'admin')
        c.edit_profile_form = self.Forms.edit_profile_form
        profile_info = self.user.get_profile_info()
        ad_text = None
        user_ad = UserAdvertisement.query.get(user_id=c.user._id)
        if user_ad:
            ad_text = user_ad.text_content
        return dict(
            action=c.app.url + 'update_profile',
            defaults={
                'user_ad': ad_text,
                'display_name': profile_info['fullName'],
                'skype_name': profile_info['skypeName'],
                'mission': profile_info['mission'],
                'interests': profile_info['interests'],
                'expertise': profile_info['expertise'],
                'public': self.user.public
            },
            user=self.user
        )

    @expose()
    @require_post()
    @validate_form("edit_profile_form", error_handler=edit_profile)
    def update_profile(self, display_name=None, skype_name=None, mission="",
                       interests="", expertise="", public="", avatar=False,
                       user_ad=None, remove_ad=False, remove_avatar=False):
        g.security.require_access(c.project, 'admin')

        # avatar
        def invalidate_avatar_cache():
            if g.cache:
                cache_keys = [
                    '{}.avatar'.format(v) for v in
                    [self.user.username] + self.user.email_addresses]
                g.cache.delete(*cache_keys)

        if remove_avatar:
            ProjectFile.remove({
                'project_id': c.project._id,
                'category': 'icon',
            })
            invalidate_avatar_cache()
        elif avatar is not None and hasattr(avatar, 'filename'):
            if c.project.icon:
                ProjectFile.remove({
                    'project_id': c.project._id,
                    'category': 'icon'
                })
            ProjectFile.save_image(
                avatar.filename,
                avatar.file,
                content_type=avatar.type,
                square=True,
                thumbnail_size=(128, 128),
                thumbnail_meta={
                    'project_id': c.project._id,
                    'category': 'icon'
                }
            )
            invalidate_avatar_cache()

        # profile info
        if display_name:
            self.user.display_name = display_name
        if skype_name:
            self.user.skype_name = skype_name
        self.user.mission = mission
        self.user.interests = interests
        self.user.expertise = expertise

        # user ad
        ad = UserAdvertisement.query.get(user_id=self.user._id)
        if remove_ad:
            if ad:
                ad.delete()
        elif user_ad:
            if ad is None:
                UserAdvertisement(
                    user_id=self.user._id,
                    text_content=user_ad
                )
            elif ad.text_content != user_ad:
                ad.text_content = user_ad
                ad.pub_date = datetime.utcnow()

        # public/private
        if not asbool(config.get('all_users_public', 'false')):
            public = bool(public)
            if public:
                self.user.make_public()
            else:
                self.user.make_private()

        redirect('index')

    @expose('json:')
    def permissions(self, repo_path=None, **kw):
        """Expects repo_path to be a filesystem path like
            <tool>/<project>.<neighborhood>/reponame[.git]
        unless the <neighborhood> is 'p', in which case it is
            <tool>/<project>/reponame[.git]

        Returns JSON describing this user's permissions on that repo.
        """
        if not repo_path:
            return {"error": "no path specified"}
        disallow = dict(
            allow_read=False,
            allow_write=False,
            allow_create=False
        )

        # strip the tool name
        parts = [p for p in repo_path.split(os.path.sep) if p]
        parts = parts[1:]
        if '.' in parts[0]:
            project, neighborhood = parts[0].split('.')
        else:
            project, neighborhood = parts[0], 'p'
        parts = [neighborhood, project] + parts[1:]
        project_path = '/' + '/'.join(parts)
        project, rest = Project.by_url_path(project_path)
        if project is None:
            LOG.info("Can't find project at %s from repo_path %s",
                     project_path, repo_path)
            return disallow
        mount_point = os.path.splitext(rest[0])[0]
        c.project = project
        c.app = project.app_instance(mount_point)
        if c.app is None:
            LOG.info("Can't find repo at %s on repo_path %s",
                     mount_point, repo_path)
            return disallow
        return dict(
            allow_read=g.security.has_access(c.app, 'read', user=self.user),
            allow_write=g.security.has_access(c.app, 'write', user=self.user),
            allow_create=g.security.has_access(c.app, 'write', user=self.user)
        )

    @expose('json')
    def get_user_profile(self, **kw):
        profile_info = self.user.get_profile_info()
        profile_info['profileImage'] = Markup(profile_info['profileImage'])

        return profile_info

    @expose('json')
    def get_user_trust_history(self, **kw):
        return dict(history=self.user.get_trust_history())

    @expose()
    @require_post()
    def invite_to_project(self, project, text='', **kw):
        project = Project.query.get(_id=bson.ObjectId(project))
        if not project:
            raise exc.HTTPNotFound
        g.security.require_access(project, 'admin')
        invite = AM.MembershipInvitation.from_user(
            self.user,
            project=project,
            text=text
        )
        invite.send()
        flash('Invitation sent to {}'.format(self.user.display_name))
        redirect('index')

    @expose('json')
    @require_post()
    def accept_membership(self, project_shortname, **kw):
        project = Project.query.get(shortname=project_shortname)
        app = project.app_instance(project.home_ac)
        with push_config(c, project=project, app=app):
            result = self.home_controller.accept_membership()
        return result

    @expose()
    @require_post()
    def set_state_preference(self, name, value, **kw):
        if not c.user._id == self.user._id:
            raise exc.HTTPForbidden()
        c.user.state_preferences[name] = value

    @expose()
    def get_state_preference(self, name, **kw):
        if not c.user._id == self.user._id:
            raise exc.HTTPForbidden()
        return dict(name=c.user.state_preferences.get(name))

    @expose('json')
    def updates_dispatcher(self):
        if not c.user._id == self.user._id:
            raise exc.HTTPForbidden()

        unread_count = ConversationStatus.unread_count_for_user_id(
            c.user._id)
        response = {
            'dashboard_unread_count': unread_count,
            'workspace_references_last_mod': h.stringify_datetime(
                c.user.workspace_references_last_mod)
        }

        return response
