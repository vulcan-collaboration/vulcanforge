import logging

from ming.odm.odmsession import ThreadLocalODMSession

from vulcanforge.migration.base import BaseMigration
from vulcanforge.neighborhood.model import (
    Neighborhood,
    VulcanNeighborhood,
    UserNeighborhood
)
from vulcanforge.project.model import (
    Project,
    VulcanProject,
    UserProject
)

LOG = logging.getLogger(__name__)


class FixProjectKindsAndNeighborhoods(BaseMigration):

    def _kind(self, cls):
        return cls.__mongometa__.polymorphic_identity

    def _fix_project(self, project):
        base = self._kind(Project)
        ukind, pkind = self._kind(UserProject), self._kind(VulcanProject)
        if project.shortname == "--init--":
            project.kind = base
            msg = "Setting neighbodhood project '{}' to kind '{}'."
            self.write_output(msg.format(project.name, project.kind))
        elif project.kind == base:
            project.kind = ukind if project.is_user_project() else pkind


    def run(self):
        self.write_output('Modifying project kinds and neighborhoods...')

        # neighborhoods
        hoods = {'Users': self._kind(UserNeighborhood),
                 'Projects': self._kind(VulcanNeighborhood)}
        base_kind = self._kind(Neighborhood)
        for n in hoods:
            hood = Neighborhood.query.get(name=n)
            if hood.kind == base_kind:
                hood.kind = hoods[n]

        # projects
        map(self._fix_project, Project.query_find())
        ThreadLocalODMSession.flush_all()

        self.write_output('Finished modifying projects and neighborhoods.')
