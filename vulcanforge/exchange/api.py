import logging

from paste.deploy.converters import asbool

from vulcanforge.auth.schema import ACE, EVERYONE
from vulcanforge.common.util.filesystem import import_object
from vulcanforge.exchange.importer import ArtifactImporter
from vulcanforge.exchange.model import ExchangeNode

LOG = logging.getLogger(__name__)
DEFAULT_ROOT = 'vulcanforge.exchange.controllers.root:DataTableRootController'
DEFAULT_REST = 'vulcanforge.exchange.controllers.rest:ExchangeRestController'
DEFAULT_PUBLISH = 'vulcanforge.exchange.controllers.publish:' + \
                  'ArtifactPublishController'
DEFAULT_VIEW = 'vulcanforge.exchange.controllers.view:ArtifactViewController'


class Exchange(object):
    """Interface for an individual exchange"""
    def __init__(self, config):
        self.config = config

    def url(self):
        return '/exchange/{}/'.format(self.config['uri'])

    def rest_url(self):
        return '/rest/exchange/{}/'.format(self.config['uri'])

    def get_config_for_artifact(self, app_config, artifact_cls):
        tool_name = app_config.tool_name.lower()
        for name, a_spec in self.config["artifacts"].items():
            if a_spec['tool_name'] == tool_name and \
                    a_spec["artifact"] == artifact_cls:
                return a_spec
        return None

    @property
    def acl(self):
        """Not currently supported due to eccentricities of the auth system"""
        return [
            ACE.allow(EVERYONE, 'read')
        ]


class _ArtifactConfigParser(object):
    """Parses artifact-specific options for a given exchange"""
    def __init__(self, tool_manager, artifact_path, xcng_name, xcng_config,
                 default_publish_controller, default_node):
        self.xcng_name = xcng_name
        self.xcng_config = xcng_config
        self.default_publish_controller = default_publish_controller
        self.default_node = default_node
        self.tool_name, self.artifact_name = artifact_path.split('.')
        self.tool = tool_manager.tools[self.tool_name]['app']
        self.artifact = self.tool.artifacts[self.artifact_name]['model']
        self.a_conf = xcng_config.get(self.tool_name, {}).get(
            self.artifact_name, {})

    @property
    def mount_point(self):
        return self.tool_name + '_' + self.artifact_name

    def get_view_controller(self):
        if 'view_controller' in self.a_conf:
            view_controller = import_object(self.a_conf['view_controller'])
        else:
            view_controller = self.tool.artifacts[self.artifact_name].get(
                'exchange_controller',
                DEFAULT_VIEW
            )
            if isinstance(view_controller, basestring):
                view_controller = import_object(view_controller)
        return view_controller

    def get_publish_controller(self):
        if 'publish_controller' in self.a_conf:
            publish_path = self.a_conf['publish_controller']
            if publish_path != 'null':
                publish_controller = import_object(publish_path)
            else:
                publish_controller = None
        else:
            publish_controller = self.default_publish_controller
        return publish_controller

    def get_import_controller(self):
        from vulcanforge.exchange.controllers.importer import ImportController
        import_controller = self.tool.artifacts[self.artifact_name].get(
            "import_controller", ImportController)
        return import_controller

    def get_artifact_spec(self):
        a_spec = {
            'tool_name': self.tool_name,
            'artifact_name': self.artifact_name,
            'publish_url': None,
            'artifact': self.artifact,
            'tool': self.tool,
            'importer': self.tool.artifacts[self.artifact_name].get(
                'importer', ArtifactImporter)
        }

        # load the artifact renderer widget
        if 'renderer' in self.a_conf:
            renderer = import_object(self.a_conf['renderer'])
        else:
            renderer = self.tool.artifacts[self.artifact_name]['renderer']
        a_spec['renderer'] = renderer

        # node model
        a_spec['node'] = self.a_conf.get('node_model', self.default_node)

        # determine artifact publish_url
        if 'publish_url' in self.a_conf:
            a_spec['publish_url'] = self.a_conf['publish_url']
        elif self.get_publish_controller():
            a_spec['publish_url'] = '/exchange/{}/{}/publish'.format(
                self.xcng_name, self.mount_point)

        # publish icon
        if 'publish_icon' in self.a_conf:
            a_spec['publish_icon'] = self.a_conf['publish_icon']
        elif 'publish_icon' in self.xcng_config:
            a_spec['publish_icon'] = self.xcng_config['publish_icon']

        return a_spec


class ExchangeManager(object):
    """Interface to interact with all exchanges for the application"""

    def __init__(self, config, tool_manager):
        self.exchanges = []
        self.publish_controllers = {}
        self.tool_manager = tool_manager
        self._parse_config(config)

    def _parse_config(self, config):
        for name, xcng in config.items():
            if asbool(xcng.pop('disabled', False)):
                continue
            artifact_paths = filter(
                None, xcng.pop('artifacts', '').strip().split(','))
            if not artifact_paths:
                LOG.warn('No artifacts specified for exchange %s', name)
                continue

            xcng.update({
                'uri': name,
                'artifacts': {},
            })
            xcng.setdefault('name', name.capitalize() + ' Exchange')
            xcng.setdefault(
                "icon", "images/forge_toolbar_icons/components_icon_on.png")

            # Initialize Exchange Interface
            if 'interface' in xcng:
                xcng_cls = import_object(xcng['interface'])
            else:
                xcng_cls = Exchange
            exchange = xcng_cls(xcng)

            # xcng root controller
            root_path = xcng.pop('root_controller', DEFAULT_ROOT)
            root_controller = import_object(root_path)(exchange)
            xcng['root_controller'] = root_controller

            # xcng rest controller
            rest_path = xcng.pop('rest_controller', DEFAULT_REST)
            if rest_path != 'null':
                rest_controller = import_object(rest_path)
                xcng['rest_controller'] = rest_controller()

            # default publish controller for an xcng
            publish_path = xcng.pop('publish_controller', DEFAULT_PUBLISH)
            if publish_path != 'null':
                default_publish_controller = import_object(publish_path)
            else:
                default_publish_controller = None

            # default node model
            if 'node_model' in xcng:
                node_model = import_object(xcng['node_model'])
            else:
                node_model = ExchangeNode
            xcng['node'] = node_model

            # artifact specific config
            for ap in artifact_paths:
                parser = _ArtifactConfigParser(
                    self.tool_manager, ap, name, xcng,
                    default_publish_controller, node_model)

                # mount the controllers to xcng root
                a_spec = parser.get_artifact_spec()
                root_controller.mount_artifact_controller(
                    parser.mount_point,
                    a_spec,
                    parser.get_view_controller(),
                    parser.get_publish_controller(),
                    parser.get_import_controller())

                xcng['artifacts'][parser.mount_point] = a_spec

            self.exchanges.append(exchange)

    def get_exchanges(self, app_config, artifact):
        """Return list of tuples [(exchange, artifact_config), ...]"""
        xcngs = []
        if not isinstance(artifact, type):
            artifact = artifact.__class__
        for exchange in self.exchanges:
            a_config = exchange.get_config_for_artifact(app_config, artifact)
            if a_config:
                xcngs.append((exchange, a_config))
        return xcngs

    def get_exchange_by_uri(self, uri):
        for xcng in self.exchanges:
            if xcng.config["uri"] == uri:
                return xcng

    def exchange_enabled_for_tool(self, tool):
        for xcng in self.exchanges:
            for name, a_spec in xcng.config["artifacts"].items():
                if tool == a_spec["tool"]:
                    return True
        return False
