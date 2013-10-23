from vulcanforge.auth.model import User
from vulcanforge.neighborhood.model import Neighborhood

from . import base


class CreateNeighborhoodCommand(base.Command):
    min_args = 3
    max_args = None
    usage = '<ini file> <neighborhood_shortname> <admin1> [<admin2>...]'
    summary = 'Create a new neighborhood with the listed admins'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        admins = [User.by_username(un) for un in self.args[2:]]
        shortname = self.args[1]
        n = Neighborhood(
            name=shortname,
            url_prefix='/' + shortname + '/')
        n.register_neighborhood_project(admins)
