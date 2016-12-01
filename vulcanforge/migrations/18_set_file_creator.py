import logging

from pylons import app_globals as g

from vulcanforge.notification.model import Notification
from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.downloads.model import ForgeDownloadsLogEntry


LOG = logging.getLogger(__name__)


class SetFileCreator(BaseMigration):

    def run(self):
        self.write_output('Setting file creator...')
        cursor = Notification.query.find({
            'subject':{'$regex':'created File'}
        })
        for notification in cursor:
            # We only want downloads files
            if notification.app_config and notification.app_config.app and \
               notification.app_config.app.tool_label != 'Downloads':
                continue

            fd_file = notification.artifact
            if fd_file is None:
                continue

            if notification.author() is not None:
                fd_file.creator_id = notification.author()._id

                log_entry = ForgeDownloadsLogEntry.query.get(file_id=fd_file._id)
                if log_entry is None:
                    app_context = g.context_manager.push(
                        app_config_id=notification.app_config._id)
                    with app_context:
                        log_entry = ForgeDownloadsLogEntry.insert('create', downloads_obj=fd_file)
                        log_entry.timestamp = fd_file._id.generation_time
                        if notification.author() is not None:
                            log_entry.user_id = notification.author()._id
                            log_entry.username = notification.author().username
                            log_entry.display_name = notification.author().get_pref('display_name')

        self.write_output('Finished setting the creator for files.')
