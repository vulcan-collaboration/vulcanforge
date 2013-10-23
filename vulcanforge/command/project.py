import logging

from ming.odm.odmsession import ThreadLocalODMSession

from . import base
from vulcanforge.auth.schema import ACE
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.model import Project, ProjectRole

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
