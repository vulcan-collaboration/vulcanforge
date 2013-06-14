from datetime import datetime

from ming import schema
from ming.odm import session
from ming.odm.property import FieldProperty
from pymongo.errors import DuplicateKeyError

from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.common.model.session import main_orm_session
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.migration.util import iter_migrations


class MigrationLog(BaseMappedClass):
    """Keeps track of the migrations run for a deployment"""

    class __mongometa__:
        session = main_orm_session
        name = 'migration_log'
        unique_indexes = ['name']

    _id = FieldProperty(schema.ObjectId)
    name = FieldProperty(str)
    # status is pending, warn, error, noop, etc..
    status = FieldProperty(str, if_missing='pending')
    started_dt = FieldProperty(datetime, if_missing=datetime.utcnow)
    ended_dt = FieldProperty(datetime, if_missing=None)
    notes = FieldProperty(str)

    INIT_NAME = 'INIT_DEPLOYMENT'

    @classmethod
    def init_deployment(cls):
        db, coll = pymongo_db_collection(cls)
        try:
            coll.insert({
                'name': cls.INIT_NAME,
                'status': 'noop',
                'started_dt': datetime.utcnow()
            })
        except DuplicateKeyError:  # pragma no cover
            return

        for mig in iter_migrations():
            cls.from_migration(mig, status='noop')

        session(cls).flush()

    @classmethod
    def has_init(cls):
        if cls.query.get(name=cls.INIT_NAME):
            return True

    @classmethod
    def upsert_init(cls):
        if not cls.has_init():
            cls.init_deployment()
            return True
        return False

    @classmethod
    def from_migration(cls, mig, **kwargs):
        return cls(name=mig.name, **kwargs)