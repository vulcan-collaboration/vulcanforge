import logging
from pprint import pformat

from ming.odm import session
from webob import exc
from pylons import tmpl_context as c, app_globals as g
from tg import expose, redirect
from tg.decorators import with_trailing_slash

from vulcanforge.common.app import Application
from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import require_post, vardec
from vulcanforge.common.helpers import ago
from vulcanforge.common.types import SitemapEntry
from vulcanforge.common.util import nonce
from vulcanforge.neighborhood.exceptions import RegistrationError
from vulcanforge.tools.home.model import PortalConfig
from vulcanforge.tools.admin.admin_main import PROJECT_ADMIN_DESCRIPTION
from vulcanforge.tools.admin.model.membership import (
    MembershipRequest,
    MembershipInvitation,
    MembershipCancelRequest,
    MembershipRemovalRequest
)

LOG = logging.getLogger(__name__)

TEMPLATE_HOME = 'jinja:vulcanforge.tools.home:templates/'


class ProjectHomeApp(Application):
    installable = False
    tool_label = 'home'
    static_folder = 'home'
    default_mount_label = 'Project Home'
    icons = {
        24: 'images/home_24.png',
        32: 'images/home_32.png',
        48: 'images/home_48.png'
    }
    permissions = ['read']
    default_acl = {
        '*anonymous': ['read']
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = ProjectHomeController()
        self.api_root = RootRestController()

    def is_visible_to(self, user):
        """Whether the user can view the app."""
        return True

    def main_menu(self):
        """Apps should provide their entries to be added to the main nav
        :return: a list of :class:`<vulcanforge.common.types.SitemapEntry>`

        """
        return [SitemapEntry(self.config.options.mount_label.title(), '.')]

    @property
    def sitemap(self):
        return [SitemapEntry('Home', '.')]

    def sidebar_menu(self):
        menu_info = [
            SitemapEntry('Team info'),
            SitemapEntry("About", self.url),
        ]

        if c.project.user_in_project(user=c.user):
            menu_info.append(
                SitemapEntry(
                    "My Permissions",
                    c.app.url + "my_permissions"
                )
            )

        return menu_info

    def admin_menu(self):
        return []


class ProjectHomeController(BaseController):

    def _check_security(self):
        g.security.require_access(c.project, 'read')

    @with_trailing_slash
    @expose(TEMPLATE_HOME + 'project_index.html')
    def index(self, **kw):
        # project news/description
        if c.project.short_description:
            project_description = g.markdown.convert(
                c.project.short_description)
        else:
            project_description = ''

        # current members, by role
        members_by_role = {}
        for user in c.project.users():
            for role in c.project.named_roles_in(user):
                members_by_role.setdefault(role.display_name, []).append(user)

        # current membership status
        membership_status = c.project.get_membership_status(c.user)

        return dict(
            project_description=project_description,
            members_by_role=members_by_role,
            membership_status=membership_status,
            project_since=ago(c.project.registration_datetime),
            is_admin=g.security.has_access(c.project, 'admin')
        )

    @with_trailing_slash
    @expose(TEMPLATE_HOME + 'my_permissions.html')
    def my_permissions(self, **kw):
        tool_setups = []
        if g.security.has_access(c.project, 'admin'):
            tool_setups.append(dict(
                title="Project Setup",
                base_url=c.project.url(),
                description=PROJECT_ADMIN_DESCRIPTION,
                icon=dict(
                    url=c.project.icon_url,
                    class_name=""
                ),
                actions={
                    "Update Metadata": c.project.url() + 'admin/overview'
                },
                perm_descriptions=['You can administer this project']
            ))
        for ac in c.project.app_configs:
            if ac.is_visible_to(c.user) and ac.options.mount_point != 'home':
                App = ac.load()
                if App.admin_description or App.admin_actions:
                    app = App(c.project, ac)
                    # permission descriptions
                    perm_descriptions = []
                    for p in app.permissions:
                        if g.security.has_access(app, p):
                            if p in app.permission_descriptions:
                                perm_descriptions.append(
                                    'You can {}'.format(
                                        app.permission_descriptions[p])
                                )
                            else:
                                perm_descriptions.append(
                                    'You have the {} permission'.format(p))
                    # tool infos
                    tool_actions = {
                        k: ac.url() + v['url']
                        for k, v in app.admin_actions.iteritems()
                        if not v.get('permission') or
                        g.security.has_access(app, v['permission'])
                    }
                    tool_setups.append(dict(
                        title=ac.options.mount_label,
                        base_url=ac.url(),
                        description=app.admin_description,
                        icon=dict(
                            url=app.icon_url(48),
                            class_name=''
                        ),
                        actions=tool_actions,
                        perm_descriptions=perm_descriptions
                    ))
        return dict(tool_setups=tool_setups)

    @require_post()
    @expose('json')
    def renounce_membership(self, force_moderate=False, **kw):
        if force_moderate or c.project.moderated_renounce:
            if not MembershipCancelRequest:
                raise exc.HTTPNotFound
            MembershipCancelRequest.upsert(text=kw.get('text', ''))
        else:
            c.project.user_leave_project(c.user, notify=True)
        return dict(success=True)

    @require_post()
    @expose('json')
    def accept_membership(self, **kw):
        invite = MembershipInvitation.query.find({
            'user_id': c.user._id,
            'project_id': c.project._id
        }).first()
        if not invite:
            raise exc.HTTPForbidden(
                "You have not been invited to this project")
        try:
            c.project.user_join_project(c.user, notify=True)
        except RegistrationError:
            return dict(error="You do not have permission")
        return dict(location=c.app.url)

    @require_post()
    @expose('json')
    def deny_membership(self, **kw):
        MembershipInvitation.query.remove({
            'user_id': c.user._id,
            'project_id': c.project._id
        })
        return dict(location=c.app.url)

    @require_post()
    @expose()
    def request_membership(self, text='', **kw):
        if not MembershipRequest:
            raise exc.HTTPNotFound
        with g.context_manager.push(c.project.shortname, 'admin'):
            MembershipRequest.upsert(text=text)
            session(MembershipRequest).flush()
        redirect("index/")

    @require_post()
    @expose('json')
    def cancel_request(self, **kw):
        if not MembershipRequest:
            raise exc.HTTPNotFound
        MembershipRequest.query.remove({
            'project_id': c.project._id,
            'user_id': c.user._id
        })
        session(MembershipRequest).flush()
        return dict(location=c.app.url)

    @require_post()
    @expose('json')
    def cancel_leave_request(self, **kw):
        if not MembershipCancelRequest:
            raise exc.HTTPNotFound
        MembershipCancelRequest.query.remove({
            'project_id': c.project._id,
            'user_id': c.user._id
        })
        session(MembershipCancelRequest).flush()
        return dict(location=c.app.url)

    @require_post()
    @expose('json')
    def accept_removal(self, **kw):
        if not MembershipRemovalRequest:
            raise exc.HTTPNotFound
        removal = MembershipRemovalRequest.query.get(
            project_id=c.project._id,
            user_id=c.user._id
        )
        if not removal:
            raise exc.HTTPNotFound
        c.project.user_leave_project(
            c.user,
            removed_by_id=removal.initiator_id,
            notify=True
        )
        MembershipRemovalRequest.query.remove({
            'project_id': c.project._id,
            'user_id': c.user._id
        })
        return dict(location=c.user.landing_url())

    @require_post()
    @expose('json')
    def deny_removal(self, text='', **kw):
        if not MembershipRemovalRequest:
            raise exc.HTTPNotFound
        removal = MembershipRemovalRequest.query.get(
            project_id=c.project._id,
            user_id=c.user._id
        )
        if not removal:
            raise exc.HTTPNotFound
        removal.reject(text=text)
        return dict(location=c.app.url)

    @expose(TEMPLATE_HOME + 'project_dashboard_configuration.html')
    def configuration(self):
        config = PortalConfig.current()
        mount_points = [
            (ac.options.mount_point, ac.load())
            for ac in c.project.app_configs]
        widget_types = [
            dict(mount_point=mp, widget_name=w)
            for mp, app_class in mount_points
            for w in app_class.widget.widgets
        ]
        return dict(
            layout_class=config.layout_class,
            layout=config.layout,
            widget_types=widget_types)

    @vardec
    @expose()
    @require_post()
    def update_configuration(self, divs=None, layout_class=None, new_div=None,
                             **kw):
        g.security.require_access(c.project, 'update')
        config = PortalConfig.current()
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
                content.append(dict(mount_point='home', widget_name='welcome'))
            config.layout.append(dict(name=div['name'], content=content))
        redirect('configuration')


class RootRestController(BaseController):

    def _check_security(self):
        g.security.require_access(c.project, 'read')

    @expose('json:')
    def index(self, **kwargs):
        return dict(shortname=c.project.shortname)
