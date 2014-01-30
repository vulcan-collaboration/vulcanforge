from ming.odm import session, ThreadLocalODMSession

from vulcanforge.auth.model import User
from vulcanforge.common.util.filesystem import import_object
from vulcanforge.neighborhood.model import Neighborhood

from . import base


class CreateNeighborhoodCommand(base.Command):
    min_args = 3
    max_args = None
    usage = '<ini file> <neighborhood_shortname> <admin1> [<admin2>...]'
    summary = 'Create a new neighborhood with the listed admins'
    parser = base.Command.standard_parser(verbose=True)
    parser.add_option(
        '-c', '--class', dest='nbhd_cls',
        help='Use neighborhood of specified class (path.to.module:ClassName)')
    parser.add_option(
        '-n', '--name', dest='name', help='Display name of the neighborhood')

    def command(self):
        self.basic_setup()
        admins = [User.by_username(username) for username in self.args[2:]]
        shortname = self.args[1]
        if self.options.nbhd_cls:
            nbhd_cls = import_object(self.options.nbhd_cls)
        else:
            nbhd_cls = Neighborhood
        name = self.options.name or shortname
        n = nbhd_cls(name=name, url_prefix='/' + shortname + '/')
        session(nbhd_cls).flush(n)
        n.register_neighborhood_project(admins, allow_register=True)
        ThreadLocalODMSession.flush_all()
