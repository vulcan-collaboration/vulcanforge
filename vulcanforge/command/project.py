import logging

from ming.odm.odmsession import ThreadLocalODMSession
from pylons import tmpl_context as c

from . import base
from vulcanforge.auth.schema import ACE
from vulcanforge.auth.model import User
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.model import Project, ProjectRole, AppConfig

log = logging.getLogger(__name__)


class EnsureProjectCreationCommand(base.Command):
    min_args = 1
    max_args = 1
    usage = '<ini file>'
    summary = 'Ensure that authenticated users can create projects'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        projects = Neighborhood.query.get(name="Projects")
        nproject = projects.neighborhood_project
        root_project_id = nproject.root_project._id
        role_auth = ProjectRole.upsert(name='*authenticated',
                                         project_id=root_project_id)
        for perm in nproject.acl:
            if (perm['permission'] == 'register' and
                perm['access'] == 'ALLOW' and
                perm['role_id'] == role_auth._id):
                break
        else:
            nproject.acl.append(ACE.allow(role_auth._id, 'register'))
            ThreadLocalODMSession.flush_all()
            ThreadLocalODMSession.close_all()


class InstallTool(base.Command):
    min_args = 5
    max_args = 6
    usage = '<ini_file> <neighborhood_prefix> <project_shortname> ' \
            '<entry_point> <mount_point> [<mount_label>]'
    summary = 'Install an instance of a tool into the specified project'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        # parse args
        neighborhood_prefix = self.args[1]
        project_shortname = self.args[2]
        entry_point = self.args[3]
        mount_point = self.args[4]
        mount_label = self.args[5] if len(self.args) == 6 else None
        # load neighborhood
        neighborhood = Neighborhood.by_prefix(neighborhood_prefix)
        assert neighborhood is not None, \
            "Could not find neighborhood '{}'".format(neighborhood_prefix)
        # load project
        project_kwargs = {
            'neighborhood_id': neighborhood._id,
            'shortname': project_shortname,
        }
        project = Project.query.get(**project_kwargs)
        assert project is not None, \
            "Could not find project '{}' in neighborhood '{}'".format(
                project_shortname, neighborhood_prefix)
        # check mount point
        app_instance = project.app_instance(mount_point)
        assert app_instance is None, \
            "Mount point '{}' already exists in project '{}'".format(
                mount_point, project_shortname)
        # install app
        project.install_app(entry_point, mount_point, mount_label)
        log.info("Installing '%s' tool at '%s:%s:%s'", entry_point,
                 neighborhood_prefix, project_shortname, mount_point)
        # wrap up
        ThreadLocalODMSession.flush_all()
        ThreadLocalODMSession.close_all()


class PurgeProject(base.Command):
    min_args = 2
    max_args = 2
    usage = '<ini_file> <project_shortname>'
    summary = "Purge a project, it's tools, and it's artifacts... use wisely."
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        project_shortname = self.args[1]
        project = Project.query.get(shortname=project_shortname)
        assert project is not None, "Project not found."
        assert project.deleted, "Project has not been deleted."
        map(self.purge_app_config, self.iter_app_configs(project._id))
        project.delete()
        ThreadLocalODMSession.flush_all()

    def iter_app_configs(self, project_id):
        for app_config in AppConfig.query.find({'project_id': project_id}):
            yield app_config

    def purge_app_config(self, app_config):
        query_params = {
            '$or': [
                {'project_id': app_config.project_id},
                {'app_config_id': app_config._id}
            ]
        }
        app = app_config.instantiate()
        for cls in app.iter_mapped_classes():
            cls.query.remove(query_params)
        app_config.delete()


class AddUserToProject(base.Command):
    min_args = 3
    max_args = 3
    usage = '<ini_file> <project_shortname> <username>'
    summary = 'Grant a user a role on a project'
    parser = base.Command.standard_parser(verbose=True)
    parser.add_option('-r', '--role', dest='role', default="Member",
                      help="User's role within the project")
    parser.add_option('-n', '--neighborhood', dest='neighborhood',
                      help="specify mount point of neighborhood")

    def command(self):
        self.basic_setup()
        shortname = self.args[1]
        username = self.args[2]
        proj_query = {"shortname": shortname}
        if self.options.neighborhood:
            nbhd = Neighborhood.by_prefix(self.options.neighborhood)
            assert nbhd is not None, "Neighborhood not found."
            proj_query["neighborhood_id"] = nbhd._id
        c.project = Project.query.get(**proj_query)
        assert c.project is not None, "Project not found."

        c.user = User.by_username(username)
        assert c.user is not None, "User not found."

        c.project.add_user(c.user, [self.options.role])
        ThreadLocalODMSession.flush_all()
