from copy import deepcopy
from collections import OrderedDict

from paste.deploy.converters import asbool
from pylons import app_globals as g

from vulcanforge.common.util.filesystem import import_object

TOOLS_DIR = 'vulcanforge.tools.'


class ToolManager(object):

    # order determines display in admin section, but can be overriden by
    # `available_tools` config param
    default_tools = OrderedDict({
        "discussion": {
            "app_path": TOOLS_DIR + "forum.forum_main:ForgeDiscussionApp",
            "installable": True
        },
        "downloads": {
            "app_path": TOOLS_DIR + "downloads.app:ForgeDownloadsApp",
            "installable": True
        },
        "tickets": {
            "app_path": TOOLS_DIR + "tickets.tracker_main:ForgeTrackerApp",
            "installable": True
        },
        "wiki": {
            "app_path": TOOLS_DIR + "wiki.app:ForgeWikiApp",
            "installable": True
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
        },
        "chat": {
            "app_path": TOOLS_DIR + 'chat.app:ForgeChatApp',
            "installable": False,
            "required": True
        }
    })

    def __init__(self, config=None):
        self.tools = deepcopy(self.default_tools)
        if config:
            self.parse_config(config)
        self.import_apps()

    def parse_config(self, config):
        index = 0
        for name, spec in config.items():
            spec["installable"] = asbool(spec.get("installable", True))
            spec["required"] = asbool(spec.get("required", False))
            spec["tool_label"] = spec.get("tool_label", "")
            spec["default_mount_label"] = spec.get("default_mount_label", "")
            spec["default_mount_point"] = spec.get("default_mount_point", "")
            if name in self.tools:
                self.tools[name].update(spec)
            else:
                self.tools.insert(index, spec)
                index += 1

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
                    "tool_label": spec.get("tool_label", app.tool_label),
                    "default_mount_label": spec.get("default_mount_label", app.default_mount_label),
                    "default_mount_point": spec.get("default_mount_point", app.default_mount_point),
                    "app": spec["app"],
                    "icon_url": icon_resource,
                    "option_fields": app.get_install_option_fields(
                        project.neighborhood)
                })
        return tools

    def is_installable(self, ep_name):
        if self.tools.get(ep_name.lower(), {}).get('installable'):
            return True
        return False
