from formencode.variabledecode import variable_decode
from ming.odm import ThreadLocalODMSession
from tg import config

from vulcanforge.command import base
from vulcanforge.common.util.filesystem import import_object
from vulcanforge.visualize.model import VisualizerConfig


class SyncVisualizersCommand(base.Command):
    summary = 'Initialize Default Visualizers in the Database'
    parser = base.Command.standard_parser(verbose=True)
    parser.add_option(
        '-s', '--shortname', dest='shortname',
        help="shortname of visualizer to sync (defaults to all)")
    parser.add_option(
        '-u', '--update_existing', dest='update_existing', action="store_true",
        help="Update existing visualizers with options on default_options "
             "attribute of Visualizer class")

    def command(self):
        self.basic_setup()
        decoded = variable_decode(config)
        visopts = decoded['visualizer']
        for shortname, path in visopts.items():
            if self.options.shortname and shortname != self.options.shortname:
                continue
            visualizer_obj = import_object(path)
            model_inst = VisualizerConfig.query.get(shortname=shortname)
            if model_inst:
                if self.options.update_existing:
                    model_inst.visualizer = {
                        "classname": visualizer_obj.__name__,
                        "module": visualizer_obj.__module__
                    }
                    for key, value in visualizer_obj.default_options.items():
                        setattr(model_inst, key, value)
            else:
                VisualizerConfig.from_visualizer(visualizer_obj, shortname)
        ThreadLocalODMSession.flush_all()
