from copy import deepcopy
from collections import OrderedDict

from pylons import app_globals as g

from vulcanforge.common.util.filesystem import import_object

TOOLS_DIR = 'vulcanforge.tools.'


class ToolManager(object):

    # order determines display in admin section, but can be overriden by
    # `available_tools` config param
    default_tools = OrderedDict({
        "discussion": {
            "app_path": TOOLS_DIR + "forum.forum_main:ForgeDiscussionApp",
            "installable": True,
            "is_customizable": True
        },
        "downloads": {
            "app_path": TOOLS_DIR + "downloads.app:ForgeDownloadsApp",
            "installable": True,
            "is_customizable": True
        },
        "tickets": {
            "app_path": TOOLS_DIR + "tickets.tracker_main:ForgeTrackerApp",
            "installable": True,
            "is_customizable": True
        },
        "wiki": {
            "app_path": TOOLS_DIR + "wiki.wiki_main:ForgeWikiApp",
            "installable": True,
            "is_customizable": True
        },
        "visualize": {
            "app_path": "vulcanforge.visualize.manage_tool.app:ForgeVisualizeApp",
            "installable": False
        },
        "profile": {
            "app_path": TOOLS_DIR + "profile.user_main:UserProfileApp",
            "installable": False,
            "required": True
        },
        "admin": {
            "app_path": TOOLS_DIR + "admin.admin_main:AdminApp",
            "installable": False,
            "required": True
        },
        "home": {
            "app_path": TOOLS_DIR + "home.project_main:ProjectHomeApp",
            "installable": False,
            "required": True
        },
        "neighborhood_home": {
            "app_path": TOOLS_DIR + "neighborhood_home.app:NeighborhoodHomeApp",
            "installable": False,
            "required": True
        },
        "calendar": {
            "app_path": TOOLS_DIR + 'calendar.app:ForgeCalendarApp',
            "installable": True
        }
    })

    def __init__(self, config=None):
        if config:
            self.parse_config(config)
            self.import_apps()

    def parse_config(self, config):
        self.tools = deepcopy(self.default_tools)
        tool_cls = self.tools.__class__
        if 'available_tools' in config:
            keys = filter(None, [k.strip() for k in config['available_tools']])
            for name, spec in self.tools.items():
                if spec.get("required") and name not in keys:
                    keys.append(name)
            self.tools = tool_cls({k: self.tools[k] for k in keys})
        if 'installable_tools' in config:
            installable = filter(
                None, [k.strip() for k in config['installable_tools']])
            for k, v in self.tools.items():
                v['installable'] = k in installable

    def import_apps(self):
        for name, spec in self.tools.items():
            spec["app"] = import_object(spec["app_path"])

    def installable_tools_for(self, project):
        tools = []
        for name, spec in self.tools.items():
            installable = spec.get('installable', False)
            app = spec.get('app', None)
            app_status = getattr(app, 'status', None)
            if installable and app_status in project.allowed_tool_status:

                icon_resource = spec["app"].icon_url(32, name)

                tools.append({
                    "name": name,
                    "app": spec["app"],
                    "icon_url": icon_resource
                })
        return tools

    def is_installable(self, ep_name):
        if self.tools.get(ep_name.lower(), {}).get('installable'):
            return True
        return False

    def is_customizable(self, ep_name):
        if self.tools.get(ep_name.lower(), {}).get('is_customizable'):
            return True
        return False
