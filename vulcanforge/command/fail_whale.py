import logging

from pylons import app_globals as g

from .base import Command


LOG = logging.getLogger(__name__)


class TurnFailWhaleOnCommand(Command):

    min_args = 1
    max_args = 1

    usage = "ini_file"
    summary = "Turns the fail whale on"

    parser = Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        if g.cache:
            g.cache.set('fail_whale', 'on')


class TurnFailWhaleOffCommand(Command):

    min_args = 1
    max_args = 1

    usage = "ini_file"
    summary = "Turns the fail whale off"

    parser = Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        if g.cache:
            g.cache.delete('fail_whale')
