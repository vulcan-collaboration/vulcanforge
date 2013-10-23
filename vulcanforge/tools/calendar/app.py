from vulcanforge.common.app import Application
from vulcanforge.tools.calendar.controllers import (
    CalendarRootController,
    ForgeCalendarAdminController
)


class ForgeCalendarApp(Application):
    __version__ = '0.1'
    permissions = ['read', 'write', 'admin']
    tool_label = 'Calendar'
    default_mount_label = 'Calendar'
    default_mount_point = 'calendar'
    admin_description = 'Plan your life!'
    default_acl = {
        'Admin': permissions,
        'Developer': ['read', 'write'],
        'Member': ['read']
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = CalendarRootController()
        self.admin = ForgeCalendarAdminController(self)
