import json
from os.path import isfile

from ming.odm.odmsession import ThreadLocalODMSession

from . import base
from vulcanforge.neighborhood.model import Neighborhood


class RegisterProjectTemplate(base.Command):
    min_args = 3
    max_args = 3
    usage = '<ini file> <neighborhood> <template-file>'
    summary = 'Register neighborhood project template'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        nprefix = self.args[1].lower()
        nbhd = Neighborhood.by_prefix(nprefix)
        assert nbhd is not None, "Neighborhood not found."
        path = self.args[2]
        assert isfile(path), "Template file does not exist."
        try:
            with open(path) as f:
                json.load(f)
        except:
            assert False, "Cannot parse JSON template."

        with open(path) as f:
            template = f.read()

        nbhd.project_template = template
        ThreadLocalODMSession.flush_all()
