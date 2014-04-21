from collections import defaultdict
from datetime import datetime
import logging
from itertools import ifilter

from bson import ObjectId
from ming.odm import ThreadLocalODMSession, state, session
import pymongo
from webob import exc
from formencode import validators as fev, Invalid
from pylons import tmpl_context as c, app_globals as g
from tg import expose, redirect, flash, config
from tg.decorators import with_trailing_slash, without_trailing_slash

import vulcanforge
from vulcanforge.common.app import (
    Application,
    DefaultAdminController
)
from vulcanforge.common.exceptions import ToolError
from vulcanforge.common.types import SitemapEntry
from vulcanforge.common.controllers.base import BaseController
from vulcanforge.common.controllers.decorators import (
    validate_form, require_post, vardec)
from vulcanforge.common.tasks.index import add_global_objs
from vulcanforge.auth.model import User, UsersDenied
from vulcanforge.auth.schema import ACL, ACE
from vulcanforge.auth.validators import UserIdentifierValidator
from vulcanforge.common.widgets.util import LightboxWidget
from vulcanforge.common.widgets.form_fields import MarkdownEdit, LabelEdit
from vulcanforge.project.model import (
    Project, ProjectFile, ProjectCategory, ProjectRole, AppConfigFile)
from vulcanforge.project.tasks import update_project_indexes
from vulcanforge.project.validators import MOUNTPOINT_VALIDATOR
from vulcanforge.neighborhood.exceptions import RegistrationError
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.neighborhood.marketplace.model import ProjectAdvertisement
from vulcanforge.resources import Icon
from vulcanforge.common.util.exception import exceptionless
from vulcanforge.notification import tasks as mail_tasks
from vulcanforge.notification.util import gen_message_id
from vulcanforge.messaging.model import Conversation

from . import widgets as aw
from . import model as AM


LOG = logging.getLogger(__name__)

PROJECT_ADMIN_DESCRIPTION = """
The first thing to do to setup your project is to create a solid
description, so folks coming to your page can figure out what the
project is all about. You may also want to edit the UserGroups and permissions
to customize the access control to suit your project's needs.
"""
TEMPLATE_DIR = 'jinja:vulcanforge.tools.admin:templates/'


class ProjectAdminController(BaseController):

    class Widgets(BaseController.Widgets):
        label_edit = LabelEdit()
        markdown_editor = MarkdownEdit()
        mount_delete = LightboxWidget(
            name='mount_delete', trigger='a.mount_delete')
        admin_modal = LightboxWidget(name='admin_modal',
                                     trigger='a.admin_modal')
        install_modal = LightboxWidget(
            name='install_modal', trigger='a.install_trig')
        customize_modal = LightboxWidget(
            name='customize_modal', trigger='a.customize-button')

    class Forms(BaseController.Forms):
        project_overview_form = aw.ProjectOverviewForm()
        member_agreement_form = aw.ProjectMemberAgreementForm()
        customize_tool_form = aw.CustomizeToolForm()

    def _check_security(self):
        g.security.require_access(c.project, 'admin')

    def __init__(self):
        self.permissions = PermissionsController()
        self.groups = GroupsController()
        self.roles = RolesController()

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'project_admin.html')
    def index(self, **kw):
        tool_setups = [dict(
            title="Project Setup",
            base_url=c.project.url(),
            description=PROJECT_ADMIN_DESCRIPTION,
            icon=dict(
                url=c.project.icon_url,
                class_name=""
            ),
            actions={
                "Update Metadata": c.project.url() + 'admin/overview'
            }
        )]
        for ac in c.project.app_configs:
            if ac.tool_name != 'home':
                app = ac.load()
                if app.admin_description or app.admin_actions:
                    tool_setups.append(dict(
                        title=ac.options.mount_label,
                        base_url=ac.url(),
                        description=app.admin_description,
                        icon=dict(
                            url=ac.icon_url(48),
                            class_name=''
                        ),
                        actions=dict(
                            (k, ac.url() + v['url'])
                            for k, v in app.admin_actions.iteritems()
                        )
                    ))
        return dict(tool_setups=tool_setups)

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'project_invitations.html')
    def invitations(self):
        return dict()

    @without_trailing_slash
    @expose('jinja:vulcanforge:common/templates/form/generic_form.html')
    def overview(self, **kwargs):
        c.form = self.Forms.project_overview_form
        project = c.project
        title = '{} Overview'.format(project.name)
        message = ''
        if project.deleted:
            message = "This project has been deleted."
        project_ad = ProjectAdvertisement.query.get(project_id=c.project._id)
        ad_text = getattr(project_ad, 'text_content', '')
        return {
            'page_title': title,
            'page_header': title,
            'pre_content': message,
            'form_display_params': {
                'action': 'overview_update',
                'value': {
                    'name': project.name,
                    'shortname': project.shortname,
                    'short_description': project.short_description,
                    'description': project.description,
                    'support_page_url': project.support_page_url,
                    'ad_text': ad_text,
                }
            }
        }

    @expose()
    @validate_form("project_overview_form", error_handler=overview)
    def overview_update(self, **kwargs):
        if not c.project.deleted and kwargs.get('delete', False):
            if c.project.neighborhood.moderate_deletion:
                self._do_request_deletion()
            else:
                c.project.delete_project()
                flash("Project %s deleted" % c.project.shortname)
                redirect('overview')
        if c.project.deleted and kwargs.get('undelete', False):
            c.project.undelete_project()
            flash("Project %s undeleted" % c.project.shortname)

        def _apply(field_name, attr_name=None):
            if attr_name is None:
                attr_name = field_name
            val = kwargs.get(field_name, None)
            old_val = getattr(c.project, attr_name)
            if val is not None and val != old_val:
                setattr(c.project, attr_name, val)

        _apply('removal')
        _apply('name')
        _apply('short_description')
        _apply('description')
        _apply('support_page_url')

        reindex = False
        icon = kwargs.get('icon', None)
        if icon is not None and icon != '':
            if c.project.icon:
                ProjectFile.remove(dict(
                    project_id=c.project._id,
                    category='icon'
                ))
            ProjectFile.save_image(
                icon.filename,
                icon.file,
                content_type=icon.type,
                square=True,
                thumbnail_size=(48, 48),
                thumbnail_meta=dict(project_id=c.project._id, category='icon'))
            reindex = True
            session(ProjectFile).flush()
            g.cache.redis.expire('navdata', 0)

        if kwargs.get('delete_icon', False):
            ProjectFile.remove(dict(
                project_id=c.project._id,
                category='icon'
            ))
            reindex = True
            session(ProjectFile).flush()
            g.cache.redis.expire('navdata', 0)

        ad_text = kwargs.get('ad_text', None)
        unpublish_ad = kwargs.get('unpublish_ad', False)
        ad = ProjectAdvertisement.query.get(project_id=c.project._id)
        if ad_text and not unpublish_ad:
            if ad is None:
                ad = ProjectAdvertisement(project_id=c.project._id)
            if ad.text_content != ad_text:
                ad.text_content = ad_text
                ad.pub_date = datetime.utcnow()
        else:
            if ad is not None:
                ad.delete()

        g.post_event('project_updated')
        if reindex and state(c.project).status != "dirty":
            add_global_objs.post([c.project.index_id()])
        flash("Changes saved", "success")
        return redirect('overview')

    #@without_trailing_slash
    @expose(TEMPLATE_DIR + 'members.html')
    def members(self):
        c.form = self.Forms.member_agreement_form
        members = []
        for user in c.project.users():
            roles = [role.display_name
                     for role in c.project.named_roles_in(user)]
            members.append({
                'user': user,
                'roles': ', '.join(roles),
                'is_admin': 'Admin' in roles,
                'is_self': user.username == c.user.username,
                'status': c.project.get_membership_status(user)
            })

        def filter_mems(q, user_in=False):
            """Delete obj if user is [not] in project, otherwise yield"""
            r = []
            for m in q:
                if not m.user_id or \
                bool(c.project.user_in_project(m.user.username)) == user_in:
                    r.append(m)
                else:
                    m.delete()
            return r

        r_q = AM.MembershipRequest.query.find({
            'project_id': c.project._id
        })
        requests = filter_mems(r_q)
        inv_q = AM.MembershipInvitation.query.find({
            'project_id': c.project._id
        })
        invitations = filter_mems(inv_q)
        c_q = AM.MembershipCancelRequest.query.find({
            'project_id': c.project._id
        })
        cancellations = filter_mems(c_q, True)

        return dict(
            members=members,
            requests=requests,
            invitations=invitations,
            cancellations=cancellations,
            base_url=c.app.admin_url(),
            can_make_admin=g.security.has_access(c.project, 'admin'),
            form_params={}
        )

    @require_post()
    @expose()
    @validate_form("member_agreement_form", error_handler=members)
    def update_member_agreement(self, member_agreement=None,
                                delete_member_agreement=None, **kwargs):
        if member_agreement is not None and member_agreement != '':
            if c.project.member_agreement:
                ProjectFile.remove(
                    {'project_id': c.project._id,
                     'category': 'member_agreement'})
            ProjectFile.from_stream(
                member_agreement.filename,
                member_agreement.file,
                project_id=c.project._id,
                category='member_agreement')
        if delete_member_agreement:
            ProjectFile.remove({
                'project_id': c.project._id,
                'category': 'member_agreement'})
        return redirect('members')

    @expose('json')
    @require_post()
    def remove_member(self, username, **kw):
        user = User.by_username(username)
        if user:
            # For Julie, my heart's content
            if c.project.moderated_renounce and \
                    not c.project.user_requested_leave(user):
                AM.MembershipRemovalRequest.upsert(
                    user=user, initiator_id=c.user._id
                )
                flash("Membership Withdraw Request Initiated")
            else:
                c.project.user_leave_project(
                    user, removed_by_id=c.user._id, notify=True, banished=True)
                flash("User removed")
        return dict(success=True)

    @expose('json')
    @require_post()
    def rescind_remove(self, username, **kw):
        user = User.by_username(username)
        if user:
            AM.MembershipRemovalRequest.query.remove({
                'project_id': c.project._id,
                'user_id': user._id
            })
        return dict(success=True)

    @expose('json')
    @require_post()
    def admin_member(self, username, **kw):
        user = c.project.user_in_project(username)
        if not user:
            raise exc.HTTPForbidden('User must be a member of the project')

        pr = c.project.project_role(user)
        role = ProjectRole.by_display_name('Admin')
        if role._id not in pr.roles:
            pr.roles.append(role._id)
        return dict(success=True)

    @expose('json')
    @require_post()
    def allow_leave(self, username, **kw):
        user = User.by_username(username)
        if user:
            c.project.user_leave_project(
                user, removed_by_id=c.user._id, notify=True)
        return dict(success=True)

    @expose('json')
    @require_post()
    def accept_member(self, username, **kw):
        user = User.by_username(username)
        if user and not c.project.user_in_project(username):
            c.project.user_join_project(
                user, notify=True, added_by_id=c.user._id)
        return dict(success=True)

    @expose('json')
    @require_post()
    def deny_member(self, username, **kw):
        user = User.by_username(username)
        if user:
            AM.MembershipRequest.query.remove({
                'project_id': c.project._id,
                'user_id': user._id
            })
        return dict(success=True)

    @expose()
    @require_post()
    def invite_new(self, users="", text="", **kw):
        uid_validator = UserIdentifierValidator()
        unfound = []
        for unstripped in users.split(','):
            u_id = unstripped.strip()
            if u_id:
                try:
                    formatted, user, id_type = uid_validator.to_python(
                        u_id, None)
                except fev.Invalid:
                    unfound.append(u_id)
                else:
                    if id_type == 'email':
                        invite = AM.MembershipInvitation.from_email(
                            formatted, text=text
                        )
                        if user:
                            invite.user_id = user._id
                    else:
                        invite = AM.MembershipInvitation.from_user(
                            user, text=text
                        )
                    invite.send()
        if unfound:
            flash("User(s) not found: {}".format(', '.join(unfound)), "error")
        redirect("members")

    @expose('json')
    @require_post()
    def rescind_invite(self, invite_id=None, **kw):
        if not invite_id:
            raise exc.HTTPNotFound
        invite = AM.MembershipInvitation.query.get(_id=ObjectId(invite_id))
        if not invite:
            raise exc.HTTPNotFound
        invite.delete()
        return dict(success=True)

    @expose('admin/user_registration.html')
    def registration(self, status='tbd', **kw):
        if not c.project.can_register_users:
            raise exc.HTTPNotFound
        requests = []
        request_fields = ['name', 'email']
        reg_reqs = AM.RegistrationRequest.query.find({
            'project_id': c.project._id,
            'status': status
        })
        for reg_req in reg_reqs:
            d = {
                'name': reg_req.name,
                'email': reg_req.email
            }
            d.update(reg_req.user_fields)
            d['id'] = str(reg_req._id)
            requests.append(d)
            for field in reg_req.user_fields.keys():
                if field not in request_fields:
                    request_fields.append(field)
        return dict(
            requests=requests,
            request_fields=request_fields,
            status=status,
            base_url=c.app.admin_url()
        )

    @expose('json')
    @require_post()
    def accept_new_user(self, req_id, **kw):
        if not c.project.can_register_users:
            raise exc.HTTPNotFound
        req = AM.RegistrationRequest.query.get(_id=ObjectId(req_id))
        if not req:
            flash("Registration Request not found", "error")
        elif req.status == "tbd":
            req.accept()
            flash("User approved. Sending registration consummation email.")
        else:
            flash("User already {}".format(req.status), "warn")
        return dict(success=True)

    @expose('json')
    @require_post()
    def deny_new_user(self, req_id, send_mail="yes", **kw):
        if not c.project.can_register_users:
            raise exc.HTTPNotFound
        req = AM.RegistrationRequest.query.get(_id=ObjectId(req_id))
        if not req:
            flash("Registration Request not found", "error")
        elif req.status != "tbd":
            flash("User already {}".format(req.status), "warn")
        else:
            if send_mail != "no":
                template = g.jinja2_env.get_template(
                    'admin/mail/deny_new_user.txt')
                text = template.render({
                    "forge_name": config.get('forge_name', 'the forge')
                })
                mail_tasks.sendmail.post(
                    fromaddr=g.forgemail_return_path,
                    destinations=[req.email],
                    reply_to='',
                    subject="{} Registration Request".format(
                        config.get('forge_name', 'Forge')),
                    message_id=gen_message_id(),
                    text=text
                )
            UsersDenied(email=req.email)
            req.status = "denied"
            flash("Registration Request Denied")
        return dict(success=True)

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'project_tools.html')
    def tools(self, **kw):
        c.markdown_editor = self.Widgets.markdown_editor
        c.label_edit = self.Widgets.label_edit
        c.mount_delete = self.Widgets.mount_delete
        c.customize_modal = self.Widgets.customize_modal
        c.admin_modal = self.Widgets.admin_modal
        c.install_modal = self.Widgets.install_modal
        mounts = c.project.ordered_mounts()
        return dict(
            mounts=mounts,
            installable_tools=g.tool_manager.installable_tools_for(c.project),
            roles=ProjectRole.query.find(dict(
                project_id=c.project.root_project._id)).sort('_id').all(),
            categories=ProjectCategory.query.find(dict(
                parent_id=None)).sort('label').all()
        )

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'customize_tool.html')
    def customize_tool(self, mount_point, **kw):
        c.form = self.Forms.customize_tool_form
        c.mount_point = mount_point
        c.ac = c.project.app_config(c.mount_point)
        c.icon_url = c.ac.icon_url(32)
        c.app_label = c.ac.options['mount_label']
        return dict(
            mount_point=mount_point
        )

    @expose()
    def update_tool(self, **kwargs):
        ac = c.project.app_config(kwargs.get('mount_point'))
        icon = kwargs.get('icon')
        mount_label = kwargs.get('mount_label')
        if ac is not None and ac.app.is_customizable:
            if mount_label and ac.options.mount_label != mount_label:
                ac.options.mount_label = mount_label
                flash("Tool Label uploaded", "success")

            if hasattr(icon, 'file'):
                AppConfigFile.remove(dict(
                    app_config_id=ac._id,
                    category='icon'
                ))
                AppConfigFile.save_image(
                    icon.filename,
                    icon.file,
                    content_type=icon.type,
                    square=True,
                    thumbnail_size=(32, 32),
                    thumbnail_meta=dict(
                        app_config_id=ac._id, category='icon', size=32))
                flash("New icon uploaded", "success")
                g.cache.redis.expire('navdata', 0)
            elif kwargs.get('delete_icon'):
                old_icon = ac.get_icon()
                if old_icon:
                    AppConfigFile.remove(dict(
                        app_config_id=ac._id,
                        category='icon'
                    ))
                    flash("Custom icon deleted", "success")
                    g.cache.redis.expire('navdata', 0)
                else:
                    flash("There was no custom icon to delete", "error")

        return redirect('tools')

    @expose()
    @require_post()
    def update_labels(self, labels=None, labels_old=None, **kw):
        c.project.labels = labels.split(',')
        redirect('trove')

    @without_trailing_slash
    @expose()
    def clone(self, repo_type=None, source_url=None, mount_point=None,
              mount_label=None, **kw):
        if repo_type is None:
            return (
                '<form method="get">'
                '<input name="repo_type" value="Git">'
                '<input name="source_url">'
                '<input type="submit">'
                '</form>')
        ep = repo_type.lower()
        if repo_type not in g.tool_manager.tools:
            raise exc.HTTPNotFound
        c.project.install_app(
            ep,
            mount_point=mount_point,
            mount_label=mount_label,
            init_from_url=source_url)
        redirect('tools')

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'project_permissions.html')
    def groups(self, **kw):
        return dict()

    @expose()
    def _lookup(self, name, *remainder):
        app = c.project.app_instance(name)
        if app is None:
            raise exc.HTTPNotFound(name)
        return app.admin, remainder

    @expose()
    @require_post()
    def join_neighborhood(self, nid):
        if not nid:
            n = Neighborhood.query.get(name='Projects')
            c.project.neighborhood_id = n._id
            flash('Joined %s' % n.name)
            redirect(c.project.url() + 'admin/')
        nid = ObjectId(str(nid))
        if nid not in c.project.neighborhood_invitations:
            flash('No invitation to that neighborhood', 'error')
            redirect('.')
        c.project.neighborhood_id = nid
        n = Neighborhood.query.get(_id=nid)
        flash('Joined %s' % n.name)
        redirect('invitations')

    @vardec
    @expose('json')
    @require_post()
    def update_mount_order(self, subs=None, tools=None, **kw):
        if subs:
            for sp in subs:
                p = Project.query.get(shortname=sp['shortname'])
                p.ordinal = int(sp['ordinal'])
        if tools:
            for p in tools:
                ac = c.project.app_config(p['mount_point'])
                ac.options.ordinal = int(p['ordinal'])
        return {'success': True}

    @vardec
    @expose()
    @require_post()
    def update_mounts(self, subproject=None, tool=None, new=None, **kw):
        if subproject is None:
            subproject = []
        if tool is None:
            tool = []
        for sp in subproject:
            if sp.get('delete'):
                p = Project.query.get(shortname=sp['shortname'])
                p.delete_project()
                flash("Project %s deleted" % p.shortname)
            elif not new:
                p = Project.query.get(shortname=sp['shortname'])
                p.name = sp['name']
                p.ordinal = int(sp['ordinal'])
        for p in tool:
            if p.get('delete'):
                c.project.uninstall_app(p['mount_point'])
            elif not new:
                options = c.project.app_config(p['mount_point']).options
                options.mount_label = p['mount_label']
                options.ordinal = int(p['ordinal'])
        try:
            if new and new.get('install'):
                ep_name = new.get('ep_name', None)
                if ep_name is None:
                    raise exc.HTTPBadRequest("tool entry point name not "
                                             "specified")
                if ep_name.lower() not in map(lambda t: t['name'],
                        g.tool_manager.installable_tools_for(c.project)):
                    raise exc.HTTPForbidden('Access Denied')
                app_spec = g.tool_manager.tools.get(ep_name.lower())
                app = app_spec.get('app')
                mount_point = new['mount_point'].lower() or ep_name.lower()
                try:
                    mount_point = MOUNTPOINT_VALIDATOR.to_python(mount_point)
                except Invalid as e:
                    raise ToolError(e.msg)
                app_config_options = {
                    option.name: kw.get(option.name)
                    for option in app.config_options
                    if option.name in kw
                }
                c.project.install_app(
                    ep_name,
                    mount_point,
                    mount_label=new['mount_label'],
                    ordinal=new['ordinal'],
                    **app_config_options
                )
        except ToolError, e:
            flash('%s: %s' % (e.__class__.__name__, e.args[0]), 'error')
        g.post_event('project_updated')
        redirect('tools')

    def _do_request_deletion(self):
        tmpl = "{user.display_name} has requested removal of " \
                   "{project.name} from {project.neighborhood.name}."
        msg = tmpl.format(
            user=c.user,
            project=c.project
        )
        conversation = Conversation(subject=msg)
        conversation.add_role_id(c.project.default_role._id)
        conversation.add_user_id(c.project.neighborhood.delete_moderator_id)
        conversation.add_message(c.user._id, msg, unread_for_sender=True)
        flash("You have requested removal for {}".format(c.project.name),
              'success')
        return conversation

    @expose()
    def request_deletion(self, **kwargs):
        conversation = self._do_request_deletion()
        return redirect(conversation.get_url())


class AdminApp(Application):
    """
    Admin app for administrating tools, permissions, etc. of a project

    """
    __version__ = vulcanforge.__version__
    tool_label = 'admin'
    static_folder = "admin"
    default_mount_label = 'Admin'
    visible_to_role = 'project.admin'
    controller_cls = ProjectAdminController

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = self.controller_cls()
        self.admin = AdminAppAdminController(self)
        self.sitemap = [SitemapEntry('Admin', '.')]

    def is_visible_to(self, user):
        """Whether the user can view the app."""
        #return has_access(c.project, 'create', user=user)
        raise DeprecationWarning()

    def main_menu(self):
        """
        Apps should provide their entries to be added to the main nav
        :return: a list of
        :class:`SitemapEntries <vulcanforge.common.types.SitemapEntry>`

        """
        return [SitemapEntry(self.config.options.mount_label.title(), '.')]

    def admin_url(self):
        """
        A hack until I can figure out whether this can replace self.url

        """
        if self.project == '--init--':
            return self.project.neighborhood.url() + '_admin/'
        return self.url

    @exceptionless([], LOG)
    def sidebar_menu(self):
        admin_url = self.admin_url()
        links = []
        if g.security.has_access(c.project, 'admin'):
            if c.project.shortname == '--init--':
                n_admin_url = self.project.neighborhood.url() + '_admin/'
                links.append(
                    SitemapEntry(
                        'Overview',
                        n_admin_url + 'overview',
                        ui_icon=Icon('', 'ico-layers'),
                        className='nav_child'
                    )
                )
            else:
                links.append(
                    SitemapEntry(
                        'Overview',
                        admin_url + 'overview',
                        ui_icon=Icon('', 'ico-layers'),
                        className='nav_child'
                    )
                )
            if c.project.is_root:
                links.append(
                    SitemapEntry(
                        'Usergroups',
                        admin_url + 'groups/',
                        ui_icon=Icon('', 'ico-user'),
                        className='nav_child')
                )
            links.append(
                SitemapEntry(
                    'Permissions',
                    admin_url + 'permissions/',
                    ui_icon=Icon('', 'ico-bolt'),
                    className='nav_child'
                )
            )
        links.append(
            SitemapEntry(
                'Tools',
                admin_url + 'tools',
                ui_icon=Icon('', 'ico-wrench'),
                className='nav_child'))
        pending_str = ''
        pending = AM.MembershipRequest.query.find({
            'project_id': c.project._id
        }).count()
        if pending:
            pending_str = '({})'.format(pending)
        links.append(
            SitemapEntry(
                'Members' + pending_str,
                admin_url + 'members',
                ui_icon=Icon('', 'ico-user'),
                className='nav_child'))
        if c.project.can_register_users:
            pending_str = ''
            pending = AM.RegistrationRequest.query.find({
                'project_id': c.project._id,
                'status': 'tbd'
            }).count()
            if pending:
                pending_str = '({})'.format(pending)
            links.append(
                SitemapEntry(
                    "User Registration" + pending_str,
                    admin_url + 'registration',
                    className='nav_child'
                ))
        if len(c.project.neighborhood_invitations):
            links.append(
                SitemapEntry(
                    'Invitation(s)',
                    admin_url + 'invitations',
                    className='nav_child'))

        return links

    def admin_menu(self):
        return []

    def install(self, project, subscribe_admins=True, **kw):
        self.config.visible_to_role = self.visible_to_role
        self.config.reference_opts = Application.reference_opts
        if subscribe_admins:
            self.subscribe_admins()

    def uninstall(self, project=None, project_id=None):  # pragma no cover
        raise NotImplementedError("uninstall")


class PermissionsController(BaseController):

    class Widgets(BaseController.Widgets):
        permission_card = aw.PermissionCard()

    def _check_security(self):
        g.security.require_access(c.project, 'admin')

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'project_permissions.html')
    def index(self, **kw):
        c.card = self.Widgets.permission_card
        return dict(permissions=self._index_permissions())

    @without_trailing_slash
    @expose()
    @vardec
    @require_post()
    def update(self, card=None, **kw):
        old_acl = c.project.acl
        permissions = self._index_permissions()
        for args in card:
            perm = args['id']
            new_group_ids = args.get('new', [])
            group_ids = args.get('value', [])
            # make sure the admin group has the admin permission
            if perm == 'admin':
                pr = ProjectRole.query.get(
                    project_id=c.project._id,
                    name='Admin'
                )
                admin_group_id = str(pr._id)
                if admin_group_id not in group_ids:
                    flash(
                        'You cannot remove the admin group from the admin '
                        'permission.',
                        'warning'
                    )
                    group_ids.append(admin_group_id)
            permissions[perm] = []
            if isinstance(new_group_ids, basestring):
                new_group_ids = [new_group_ids]
            if isinstance(group_ids, basestring):
                group_ids = [group_ids]
            role_ids = map(ObjectId, group_ids + new_group_ids)
            permissions[perm] = role_ids
        c.project.acl = []
        for perm, role_ids in permissions.iteritems():
            for rid in role_ids:
                ACL.upsert(c.project.acl, ACE.allow(rid, perm))

        if self._read_aces_changed(old_acl, c.project.acl):
            session(Project).flush()
            update_project_indexes.post(c.project._id)
        g.post_event('project_updated')
        redirect('.')

    def _read_aces_changed(self, old_acl, new_acl):
        old_read_aces = [item for item in old_acl if item.permission == 'read']
        new_read_aces = [item for item in new_acl if item.permission == 'read']
        diff_list = [item for item in old_read_aces
                     if not item in new_read_aces]
        diff_list2 = [item for item in new_read_aces
                      if not item in old_read_aces]
        return diff_list or diff_list2

    def _index_permissions(self):
        permissions = dict((p, []) for p in c.project.permissions)
        for ace in c.project.acl:
            if ace.access == ACE.ALLOW:
                permissions[ace.permission].append(ace.role_id)
        return permissions


class GroupsController(BaseController):

    class Widgets(BaseController.Widgets):
        admin_modal = LightboxWidget(name='admin_modal',
                                     trigger='a.admin_modal')
        group_card = aw.GroupCard()

    class Forms(BaseController.Forms):
        new_group_settings = aw.NewGroupSettings()

    def _check_security(self):
        g.security.require_access(c.project, 'admin')

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'project_groups.html')
    def index(self, **kw):
        c.admin_modal = self.Widgets.admin_modal
        c.card = self.Widgets.group_card
        roles = c.project.named_roles
        roles.append(None)
        return dict(roles=roles)

    def _add_user_to_group(self, user, group, seen, events):
        if not user._id:
            return  # never add anon users to groups

        if not user.username in seen and not \
                c.project.user_in_project(user.username):
            try:
                events.append(
                    c.project.user_join_project(
                        user, role=group, notify=False)
                )
            except RegistrationError:
                flash('User %s does not have permission' % user.username)
                return
            seen.add(user.username)
        else:
            c.project.project_role(user).roles.append(group._id)

    @without_trailing_slash
    @expose()
    @require_post()
    @vardec
    def update(self, card=None, **kw):
        deleted_user_ids = set()  # users deleted from each role
        project_user_ids = set()  # users in project
        events = []  # for notififications

        for pr in card:
            # parse results
            group = ProjectRole.query.get(_id=ObjectId(pr['id']))
            if group.project_id != c.project._id:
                raise exc.HTTPForbidden("Security Violation")
            user_ids = pr.get('value', [])
            new_users = pr.get('new', [])
            if isinstance(user_ids, basestring):
                user_ids = [user_ids]
            if isinstance(new_users, basestring):
                new_users = [new_users]

            # Handle new users in groups
            seen = set()
            for username in new_users:
                user = User.by_username(username)
                if not user:
                    flash('User %s not found' % username, 'error')
                    continue
                self._add_user_to_group(user, group, seen, events)
                project_user_ids.add(user._id)

            # Handle users removed from groups
            user_ids = list(set(uid and ObjectId(uid) for uid in user_ids))
            project_user_ids.update(user_ids)
            deleted_roles = ProjectRole.query.find({
                'user_id': {'$nin': user_ids},
                'roles': group._id
            })
            for role in ifilter(lambda r: r.user_id, deleted_roles):
                deleted_user_ids.add(role.user_id)
                role.roles = [rid for rid in role.roles if rid != group._id]

        # Handle users leaving project
        deleted_from_project = deleted_user_ids.difference(project_user_ids)
        if c.user._id in deleted_from_project:
            ThreadLocalODMSession.close_all()
            flash('You may not remove yourself from the project')
            raise exc.HTTPForbidden(
                'You may not remove yourself from the project')
        for uid in deleted_from_project:
            user = User.query.get(_id=uid)
            if user:
                if c.project.moderated_renounce and\
                        not c.project.user_requested_leave(user):
                    AM.MembershipRemovalRequest.upsert(
                        user=user, initiator_id=c.user._id
                    )
                    flash("Membership Withdraw Request sent to {}".format(
                        user.username
                    ))
                    c.project.project_role(user).roles.append(
                        c.project.default_role._id)
                else:
                    c.project.user_leave_project(
                        user, notify=True, clean_roles=False, banished=True
                    )
        for ev in events:
            ev.notify()

        g.post_event('project_updated')
        redirect('.')

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'project_group.html')
    def new(self):
        c.form = self.Forms.new_group_settings
        return dict(
            group=None,
            show_settings=True,
            action="create")

    @expose()
    @require_post()
    @validate_form("new_group_settings")
    @vardec
    def create(self, name=None, **kw):
        if ProjectRole.by_name(name):
            flash('%s already exists' % name, 'error')
        else:
            ProjectRole(project_id=c.project._id, name=name)
        g.post_event('project_updated')
        redirect('.')

    @expose()
    def _lookup(self, name, *remainder):
        return GroupController(name), remainder


class GroupController(BaseController):

    class Forms(BaseController.Forms):
        group_settings = aw.GroupSettings()

    def __init__(self, name):
        self._group = ProjectRole.query.get(_id=ObjectId(name))

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'project_group.html')
    def index(self):
        if self._group.name in ('Admin', 'Developer', 'Member'):
            show_settings = False
            action = None
        else:
            show_settings = True
            action = self._group.settings_href + 'update'
        c.form = self.Forms.group_settings
        return dict(
            group=self._group,
            show_settings=show_settings,
            action=action)

    @expose()
    @vardec
    @require_post()
    @validate_form("group_settings")
    def update(self, _id=None, delete=None, name=None, **kw):
        pr = ProjectRole.by_name(name)
        if pr and pr._id != _id._id:
            flash('%s already exists' % name, 'error')
            redirect('..')
        if delete:
            _id.delete()
            flash('%s deleted' % name)
            redirect('..')
        _id.name = name
        flash('%s updated' % name)
        redirect('..')


class AdminAppAdminController(DefaultAdminController):
    """Administer the admin app...but WHY??"""
    pass


class RolesController(BaseController):

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'project_roles.html')
    def index(self):
        """
        TODO: client side app
            - load all permissions and roles with state hash
            - api calls
                - create role
                - delete role
                - assign role to user
                - unassign role to user
                - assign permission to role
                - unassign permission to role
        """
        return {}

    @expose('json')
    def role_graph(self):
        return {
            'roles': self._get_project_roles(c.project._id),
            'permissions': self._get_project_permissions(c.project),
            'apps': self._get_project_app_configs(c.project)
        }

    @staticmethod
    def _get_project_roles(project_id):
        cursor = ProjectRole.query.find({
            'project_id': project_id
        })
        cursor.sort('name', pymongo.DESCENDING)
        roles = {
            'named': {},
            'user': {}
        }
        for role in cursor:
            display = role.display()
            roleset = roles['user'] if display.startswith('*') else roles['named']
            roleset[str(role._id)] = {
                'id': role._id,
                'user': getattr(role.user, 'username', None),
                'role_ids': role.roles,
                'name': role.name,
                'display': display
            }
        return roles

    @staticmethod
    def _get_project_permissions(project):
        permissions = defaultdict(lambda: defaultdict(lambda: list()))
        for ace in project.acl:
            if ace.access == ACE.ALLOW:
                permissions['project'][ace.permission].append(ace.role_id)
        for app_config in project.app_configs:
            for ace in app_config.acl:
                if ace.access == ACE.ALLOW:
                    permissions[str(app_config._id)][ace.permission].append(ace.role_id)
        return permissions

    @staticmethod
    def _get_project_app_configs(project):
        return {
             str(app_config._id): {
                 'id': app_config._id,
                 'label': app_config.options.mount_label,
                 'mount': app_config.options.mount_point,
                 'url': app_config.url()
             }
             for app_config in project.app_configs
        }
