import os
import logging
from datetime import datetime, timedelta
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

from vulcanforge.auth.exceptions import (
    PasswordAlreadyUsedError,
    PasswordCannotBeChangedError
)
from vulcanforge.common import exceptions, helpers as h
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import vardec
from vulcanforge.common.tool import SitemapEntry
from vulcanforge.common.util import push_config, nonce
from vulcanforge.common.util.exception import exceptionless
from vulcanforge.common.util.notifications import get_user_notifications
from vulcanforge.common.app import Application
from vulcanforge.common.validators import DateTimeConverter
from vulcanforge.auth.controllers import PreferencesController, AuthController
from vulcanforge.auth.schema import ACE
from vulcanforge.auth.model import WorkspaceTab
from vulcanforge.auth.validators import validate_password
from vulcanforge.artifact.widgets import short_artifact_link_data
from vulcanforge.messaging.model import ConversationStatus
from vulcanforge.neighborhood.marketplace.model import UserAdvertisement
from vulcanforge.notification.model import Notification
from vulcanforge.project.widgets import ProjectListWidget
from vulcanforge.project.model import Project, ProjectFile, MembershipRequest, \
    MembershipInvitation, ProjectRole
from vulcanforge.notification.widgets import ActivityFeed
from vulcanforge.resources import Icon
from vulcanforge.tools.home import model as PHM
from vulcanforge.tools.home.project_main import ProjectHomeController
from .widgets import EditProfileForm
from vulcanforge.common.controllers.decorators import (
    require_post, validate_form)


LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.tools.profile:templates/'


class UserProfileApp(Application):
    has_chat = False

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

    def sidebar_menu(self):
        is_mine = c.user._id == self.user._id

        menu = []

        if is_mine:
            reg_nbhd = c.user.registration_neighborhood()
            if reg_nbhd and reg_nbhd.user_can_register():
                menu.extend([
                    SitemapEntry(
                        'Start a {}'.format(reg_nbhd.project_cls.type_label),
                        reg_nbhd.url() + 'add_project',
                        ui_icon=Icon('', 'ico-plus')
                    ),
                    SitemapEntry('')
                ])
            menu.append(SitemapEntry('Activity Feed',
                                     '/dashboard/activity_feed',
                                     ui_icon=Icon('', 'ico-activity')))

        menu.append(SitemapEntry('Profile', self.url,
                                 ui_icon=Icon('', 'ico-user')))

        if is_mine:
            menu.append(SitemapEntry('Conversations', '/dashboard/messages',
                                     ui_icon=Icon('', 'ico-inbox')))

        if g.security.has_access(c.project, 'admin'):
            menu.extend([
                SitemapEntry(''),
                SitemapEntry('Settings'),
                SitemapEntry('Edit Profile Info', self.url + 'edit_profile',
                             ui_icon=Icon('', 'ico-edit'))
            ])
        if is_mine:
            menu.extend([
                SitemapEntry('Preferences', '/auth/prefs/',
                             ui_icon=Icon('', 'ico-settings')),
                SitemapEntry('Subscriptions', "/auth/prefs/subscriptions",
                             ui_icon=Icon('', 'ico-mail'))
            ])
        return menu

    def admin_menu(self):
        return []

    def install(self, project, **kw):
        pr = c.project.project_role(self.user)
        if pr:
            self.config.acl = [
                ACE.allow(pr._id, perm) for perm in self.permissions()]

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

        artifact = g.artifact.get_artifact_by_index_id(ref_id)

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
        return {'user': self.user,
                'lastLog': self.user.last_login}

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
        defaults = {
            'display_name': profile_info['fullName'],
            'mission': profile_info['mission'],
            'interests': profile_info['interests'],
            'expertise': profile_info['expertise'],
            'public': self.user.public
        }
        user_fields_info = {x: self.user.user_fields.get(x, "")
                            for x in ('company', 'position', 'telephone')}
        defaults.update(user_fields_info)
        return dict(
            action=c.app.url + 'update_profile',
            defaults=defaults,
            user=self.user
        )

    @expose()
    @require_post()
    @validate_form("edit_profile_form", error_handler=edit_profile)
    def update_profile(self, display_name=None, mission="", interests="",
                       expertise="", public="", avatar=False,
                       remove_avatar=False, **kw):

        g.security.require_access(c.project, 'admin')
        LOG.info("Update profile: {}".format(kw))

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
        self.user.mission = mission
        self.user.interests = interests
        self.user.expertise = expertise

        # user_fields
        user_fields = ('company', 'position', 'telephone')
        for f in user_fields:
            if f in kw:
                self.user.user_fields[f] = kw[f]

        # public/private
        if not asbool(config.get('all_users_public', 'false')):
            if public:
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
        profile_info['email'] = self.user.get_email_address()
        return profile_info

    @expose('json')
    def get_user_trust_history(self, **kw):
        return dict(history=self.user.get_trust_history())

    @expose()
    @require_post()
    def invite_to_project(self, project, text='', **kw):
        project = Project.query_get(_id=bson.ObjectId(project))
        if not project:
            raise exc.HTTPNotFound
        g.security.require_access(project, 'admin')
        invite = MembershipInvitation.from_user(
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
        project = Project.by_shortname(project_shortname)
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

    @expose('json')
    def userinfo(self, **kw):
        uinfo = self.user.get_profile_info()
        uf = self.user.user_fields
        my_user = c.user.username == self.user.username
        info = {
            'name': uinfo['fullName'],
            'interests': uinfo['interests'],
            'username': self.user.username,
            'mission': uinfo['mission'],
            'expertise': self.user.expertise,
            'icon': self.user.icon_url(),
            'email': self.user.get_email_address(),
            'joined': self.user._id.generation_time.isoformat(),
            'telephone': uf.get('telephone', None),
            'position': uf.get('position', None),
            'company': uf.get('company', None),
            'disabled': self.user.disabled,
            'forge_name': config.get("forge_name"),
            'canEdit': my_user,
            'twofactor_notice': (my_user and g.auth_two_factor and
                                 not c.user.get_pref('two_factor_auth')),
            'url': self.user.url()
        }
        return info

    @expose('json')
    def activity(self, from_dt=None, to_dt=None, **kw):
        """returns the project's recent activity via notifications"""
        limit = 25
        results = get_user_notifications(
            self.user, c.user, from_dt, to_dt, limit=limit, **kw)
        has_more = 'true' if results.hits > limit else 'false'
        json = '{{"notifications":[{notifications}],' \
               '"more":{more},"project_id":"{project_id}"}}'.format(
            notifications=','.join(d['json_ni'] for d in results.docs),
            more=has_more, project_id=str(c.project._id)
        )
        return Markup(json)

    @expose('json')
    def checkpassword(self, value, **kwargs):
        validate = g.auth_provider.validate_password
        match = validate(c.user, value)
        return {
            'match': match
        }

    def setpassword(self, new, current):
        check = validate_password(new, current)
        if check != 'success':
            return {
                'error': check
            }
        try:
            c.user.set_password(new, current)
            return {
                'success': True
            }
        except PasswordAlreadyUsedError, e:
            return {
                'error': 'Password has already been used.'
            }
        except PasswordCannotBeChangedError, e:
            return {
                'error': 'Password minimum lifetime not yet exceeded'
            }
        except Exception, e:
            return {
                'error': 'Bad password change attempt'
            }

    @require_post()
    @expose('json')
    def changeSecurity(self, changepass=False, newpass=None, curpass=None,
                       twofactor=False, delacc=False):
        if delacc == 'true':
            c.user.disabled = True
            g.auth_provider.logout()
            redirect(g.post_logout_url)
        if changepass == 'true' and newpass and curpass:
            resp = self.setpassword(newpass, curpass)
            if resp.get('error', None):
                return resp
        c.user.set_pref('two_factor_auth', twofactor == 'true')
        return {"success": 'Security settings updated'}

    @expose('json')
    def getsecurity(self, **kwargs):
        p = PreferencesController()
        p.config_test()
        min_hours = int(config.get('auth.pw.min_lifetime.hours', 24))
        can_change = True
        if c.user.password_set_at:
            age = datetime.utcnow() - c.user.password_set_at
            if age < timedelta(hours=min_hours):
                can_change = False
        return {
            'platformtf': g.auth_two_factor,
            'usertf': c.user.get_pref('two_factor_auth'),
            'tfkey': c.user.user_fields['totp'],
            'canchange': can_change,
            'minhours': min_hours
        }

    @expose('json')
    def getTFValue(self, **kwargs):
        pfc = PreferencesController()
        return pfc.config_test()

    @expose('json')
    def getprojects(self, **kw):
        projects = [x for x in self.user.my_projects()
                    if x.is_real() and not x.deleted
                    and g.security.has_access(x, "read", c.user)]
        project_info = []
        for project in projects:
            named_roles = project.named_roles_in(self.user)
            user_roles = ", ".join(sorted([x.name for x in named_roles]))
            q = dict(project_id=project._id, user_id=self.user._id)
            project_role = ProjectRole.query.get(**q)
            member_since = None
            if project_role:
                member_since = project_role._id.generation_time
            p = {
                "name": project.name,
                "icon_url": project.icon_url,
                "url": project.url(),
                "roles": user_roles,
                "joined": datetime.isoformat(member_since)
            }
            project_info.append(p)
        return {'projects': project_info}