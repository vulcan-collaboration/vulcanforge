import logging
import json
from datetime import datetime
from cStringIO import StringIO
from urllib2 import urlopen

from ming import schema as S
from ming.odm import (
    FieldProperty,
    ForeignIdProperty,
    ThreadLocalODMSession,
    state
)
from ming.utils import LazyProperty
from pylons import request, tmpl_context as c, app_globals as g
from vulcanforge.common.model.base import BaseMappedClass

from vulcanforge.common.model.session import main_orm_session
from vulcanforge.s3.model import File
from vulcanforge.common.util import push_config
from vulcanforge.project.exceptions import ProjectConflict
from .exceptions import RegistrationError


LOG = logging.getLogger(__name__)


class NeighborhoodFile(File):

    class __mongometa__:
        name = 'neighborhood_file'
        session = main_orm_session
        indexes = [('neighborhood_id', 'category')] + \
                  File.__mongometa__.indexes

    neighborhood_id = FieldProperty(S.ObjectId)
    category = FieldProperty(str)

    @property
    def neighborhood(self):
        return Neighborhood.query.get(_id=self.neighborhood_id)

    @property
    def default_keyname(self):
        keyname = super(NeighborhoodFile, self).default_keyname
        return '/'.join((
            'Neighborhood',
            self.neighborhood.url_prefix.strip('/'),
            keyname
        ))

    def local_url(self):
        return self.neighborhood.url() + 'icon'


class Neighborhood(BaseMappedClass):
    """Provide a grouping of related projects.

    url_prefix - location of neighborhood (may include scheme and/or host)
    css - block of CSS text to add to all neighborhood pages

    """
    class __mongometa__:
        session = main_orm_session
        name = 'neighborhood'
        polymorphic_on = 'kind'
        polymorphic_identity = 'neighborhood'
        indexes = ['name', 'url_prefix', 'allow_browse']

    _id = FieldProperty(S.ObjectId)
    name = FieldProperty(str)
    kind = FieldProperty(str, if_missing='neighborhood')
    url_prefix = FieldProperty(str)  # can be absolute or relative
    shortname_prefix = FieldProperty(str, if_missing='')
    css = FieldProperty(str, if_missing='')
    homepage = FieldProperty(str, if_missing='')
    redirect = FieldProperty(str, if_missing='')
    #projects = RelationProperty('Project')
    allow_browse = FieldProperty(bool, if_missing=True)
    site_specific_html = FieldProperty(str, if_missing='')
    project_template = FieldProperty(str, if_missing='')
    role_aliases = FieldProperty({str: str}, if_missing={})
    can_register_users = FieldProperty(bool, if_missing=False)
    enable_marketplace = FieldProperty(bool, if_missing=False)
    project_registration_enabled = FieldProperty(bool, if_missing=True)
    # extra_sidebars items should have at least name and url
    extra_sidebars = FieldProperty([{str: str}], if_missing=[])
    moderate_component_publish = FieldProperty(bool, if_missing=False)
    # moderation limits: must wait {seconds} between submission times
    moderate_component_limit_seconds = FieldProperty(int, if_missing=0)
    moderate_deletion = FieldProperty(bool, if_missing=False)
    delete_moderator_id = ForeignIdProperty('User')
    can_grant_anonymous = FieldProperty(bool, if_missing=True)

    # for neighborhood project
    _default_neighborhood_apps = [
        ('neighborhood_home', 'home', 'Home'),
        ('admin', 'admin', 'Admin')
    ]

    @classmethod
    def by_prefix(cls, prefix):
        """Prefix without slashes (e.g. projects)"""
        return cls.query.get(url_prefix='/' + prefix + '/')

    @classmethod
    def get_user_neighborhood(cls):
        return cls.by_prefix('u')

    def parent_security_context(self):
        return None

    @LazyProperty
    def neighborhood_project(self):
        return self.project_cls.query.get(
            neighborhood_id=self._id,
            shortname='--init--'
        )

    @LazyProperty
    def projects(self):
        from vulcanforge.project.model import Project
        return self.project_cls.query.find(
            {'neighborhood_id': self._id}
        ).all()

    @property
    def delete_moderator(self):
        if self.delete_moderator_id:
            user_cls = self.__class__.delete_moderator_id.related
            return user_cls.query.get(_id=self.delete_moderator_id)

    @property
    def acl(self):
        return self.neighborhood_project.acl

    def url(self):
        url = self.url_prefix
        if url.startswith('//'):
            try:
                return request.scheme + ':' + url
            except TypeError:  # pragma no cover
                return 'http:' + url
        else:
            return url

    @property
    def project_cls(self):
        from vulcanforge.project.model import Project
        return Project

    @property
    def neighborhood_project_cls(self):
        return self.project_cls

    @property
    def user_cls(self):
        from vulcanforge.auth.model import User
        return User

    @property
    def controller_class(self):
        return g.default_nbhd_controller

    @property
    def rest_controller_class(self):
        return g.default_nbhd_rest_controller

    def user_can_register(self, user=None):
        """
        Whether a user can register on a team project

        """
        return self.project_registration_enabled

    def assert_user_can_register(self, user=None):
        if not self.user_can_register(user=user):
            raise RegistrationError('User cannot register')

    def register_project(self, shortname, user=None, project_name=None,
                         user_project=False, private_project=False, apps=None,
                         **kw):
        """Register a new project in the neighborhood.  The given user will
        become the project's superuser.  If no user is specified, c.user is
        used.

        """
        from vulcanforge.project.model import ProjectFile
        if project_name is None:
            project_name = shortname
        if user is None:
            user = getattr(c, 'user', None)

        default_home_text = "Welcome to your new project."
        if project_name is not None:
            default_home_text = "Welcome to the %s Project." % project_name
        if self.project_template:
            project_template = json.loads(self.project_template)
            if private_project is None and 'private' in project_template:
                private_project = project_template['private']
        else:
            project_template = {'home_text': default_home_text}

        p = self.project_cls.query.get(shortname=shortname)
        if p:
            raise ProjectConflict()

        try:
            p = self.project_cls(
                neighborhood_id=self._id,
                shortname=shortname,
                name=project_name,
                short_description='',
                description=('You can edit this description in the admin page'),
                homepage_title=shortname,
                database_uri=self.project_cls.default_database_uri(shortname),
                last_updated=datetime.utcnow(),
                is_root=True,
                **kw
            )
            p.configure_project(
                users=[user],
                is_user_project=user_project,
                is_private_project=private_project,
                apps=apps)

            offset = int(p.ordered_mounts()[-1]['ordinal']) + 1

            if not apps and 'tools' in project_template:
                for i, tool in enumerate(project_template['tools'].keys()):
                    tool_config = project_template['tools'][tool]
                    with push_config(c, project=p, user=user):
                        app = c.project.install_app(
                            tool,
                            mount_label=tool_config['label'],
                            mount_point=tool_config['mount_point'],
                            ordinal=i + offset,
                            acl=project_template.get('tool_acl', {}).get(
                                tool_config['mount_point'])
                        )
                        if 'options' in tool_config:
                            app.config.options.update(tool_config['options'])
            if 'tool_order' in project_template:
                for i, tool in enumerate(project_template['tool_order']):
                    p.app_config(tool).options.ordinal = i
            if 'labels' in project_template:
                p.labels = project_template['labels']
            if 'home_options' in project_template:
                options = p.app_config('home').options
                for option in project_template['home_options'].keys():
                    options[option] = project_template['home_options'][option]
            if 'icon' in project_template:
                icon_file = StringIO(
                    urlopen(project_template['icon']['url']).read())
                ProjectFile.save_image(
                    project_template['icon']['filename'],
                    icon_file,
                    square=True,
                    thumbnail_size=(48, 48),
                    thumbnail_meta=dict(project_id=p._id, category='icon')
                )
        except:
            ThreadLocalODMSession.close_all()
            LOG.exception('Error registering project %s' % p)
            raise
        ThreadLocalODMSession.flush_all()
        with push_config(c, project=p, user=user):
            # have to add user to context, since this may occur inside auth code
            # for user-project reg, and c.user isn't set yet
            g.post_event('project_created')

        user.add_workspace_tab_for_project(p)
        if (
            p.neighborhood.kind == "competition" and
            p.neighborhood.monoconcilium and
            p.neighborhood.enable_marketplace
        ):
            url = "{url}home/market/browse_projects".format(
                url=p.neighborhood.url())
            user.delete_workspace_tab_to_url(url)

        return p

    def register_neighborhood_project(self, users, allow_register=False,
                                      apps=None):
        from vulcanforge.project.model import ProjectRole
        
        shortname = '--init--'
        p = self.neighborhood_project
        if p:
            raise ProjectConflict()
        name = 'Home Project for %s' % self.name
        database_uri = self.neighborhood_project_cls.default_database_uri(
            shortname)
        p = self.neighborhood_project_cls(
            neighborhood_id=self._id,
            neighborhood=self,
            shortname=shortname,
            name=name,
            short_description='',
            description='You can edit this description in the admin page',
            homepage_title='# ' + name,
            database_uri=database_uri,
            last_updated=datetime.utcnow(),
            is_root=True
        )
        if apps is None:
            apps = self._default_neighborhood_apps
        try:
            p.configure_project(
                users=users,
                is_user_project=False,
                apps=apps
            )
        except:
            ThreadLocalODMSession.close_all()
            LOG.exception('Error registering project %s' % p)
            raise
        if allow_register:
            role_auth = ProjectRole.authenticated(p)
            g.security.simple_grant(p.acl, role_auth._id, 'register')
            state(p).soil()
        return p

    def bind_controller(self, controller):
        controller_attr = self.url_prefix[1:-1]
        setattr(
            controller,
            controller_attr,
            self.controller_class(self.name, self.shortname_prefix)
        )

    @property
    def icon(self):
        return NeighborhoodFile.query.get(
            neighborhood_id=self._id,
            category='icon'
        )

    def icon_url(self):
        icon = self.icon
        if icon:
            return icon.url()
        else:
            return g.resource_manager.absurl('images/project_default.png')

    @LazyProperty
    def curation_ac(self):
        for ac in self.neighborhood_project.app_configs:
            if ac.tool_name.lower() == 'curation':
                return ac
        return None



