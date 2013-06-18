from datetime import datetime

from ming.odm import session

from vulcanforge.migration.model import MigrationLog


class BaseMigration(object):

    def __init__(self, miglog=None):
        super(BaseMigration, self).__init__()
        if miglog is None:
            miglog = MigrationLog.upsert_from_migration(self)
        self.miglog = miglog

    @classmethod
    def get_name(cls):
        """Used to uniquely identify a migration in the database"""
        return cls.__module__ + ':' + cls.__name__

    def is_needed(self):
        """A means of checking whether the migration script is needed for a
        given deployment. This can generally be left to return True, because
        a migration script is run only once per db, but if you need more fine-
        grained logic, override this method.

        """
        return True

    def write_output(self, msg):
        """Appends the message to the log objects output array"""
        self.miglog.output.append(msg)

    def full_run(self):
        """This is the method called by the MigrationRunner, but for most
        purposes, overriding the run method should be sufficient.

        """
        try:
            self.run()
        except Exception as err:
            self.write_output(str(err))
            self.miglog.status = 'error'
            session(self.miglog).flush(self.miglog)
            raise
        else:
            self.miglog.status = 'success'
            self.miglog.ended_dt = datetime.utcnow()

    def run(self):
        """Override this with your migration script logic"""
        pass
