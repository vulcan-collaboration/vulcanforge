
import IPython
import tg

from base import Command


class VulcanForgeShellCommand(Command):

    min_args = 0
    max_args = 1

    summary = "Start an interactive iPython shell with VF goodies preloaded"

    parser = Command.standard_parser(verbose=True)

    def command(self):
        if not self.args:
            raise RuntimeError("Must specify a config file")
        self.basic_setup()
        locs = {'__name__': 'vshell'}
        exec 'from pylons import tmpl_context as c, app_globals as g' in locs
        from ming.odm import session, ThreadLocalODMSession
        from datetime import datetime, timedelta
        import bson
        pkg = tg.config['package']
        locs.update({
            'session': session,
            'ThreadLocalODMSession': ThreadLocalODMSession,
            'datetime': datetime,
            'timedelta': timedelta,
            'bson': bson,
            'h': pkg.lib.helpers,
            'M': pkg.model
        })
        IPython.embed(user_ns=locs)
