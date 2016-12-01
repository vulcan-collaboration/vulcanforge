import logging

from tg.decorators import Decoration

from vulcanforge.tools.downloads import model as FDM

LOG = logging.getLogger(__name__)


class log_access(object):

    def __init__(self, access_type='', permission_needed="read", extra_information=None, access_denied_only=False):
        self.access_type = access_type
        self.permission_needed = permission_needed
        self.extra_information = extra_information
        self.access_denied_only = access_denied_only

    def __call__(self, func):
        decoration = Decoration.get_decoration(func)
        decoration.register_hook('before_render', self.before_render)
        return func

    def before_render(self, remainder, params, output):
        FDM.ForgeDownloadsLogEntry.insert(self.access_type, self.permission_needed, self.extra_information, access_denied_only=self.access_denied_only)
