from vulcanforge.common.app import Application
from vulcanforge.common.app import DefaultAdminController
from vulcanforge.tools.calendar.controllers import CalendarRootController


class ForgeCalendarApp(Application):
    __version__ = '0.1'
    tool_label = 'Calendar'
    default_mount_label = 'Calendar'
    default_mount_point = 'calendar'
    admin_description = 'Plan your life!'
    default_acl = {
        'Admin': Application.permissions.keys(),
        'Developer': ['read', 'write'],
        'Member': ['read']
    }
    icons = {
        24: '{ep_name}/images/calendar-icon_24.png',
        32: '{ep_name}/images/calendar-icon_32.png',
        48: '{ep_name}/images/calendar-icon_48.png'
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = CalendarRootController()
        self.admin = DefaultAdminController(self)
