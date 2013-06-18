from datetime import datetime

from ming import schema
from ming.odm.property import FieldProperty
from pymongo.errors import DuplicateKeyError

from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.common.model.session import main_orm_session
from vulcanforge.common.util.model import pymongo_db_collection


class MigrationLog(BaseMappedClass):
    """Keeps track of the migrations run for a deployment"""

    class __mongometa__:
        session = main_orm_session
        name = 'migration_log'
        unique_indexes = ['name']

    _id = FieldProperty(schema.ObjectId)
    name = FieldProperty(str)
    # status is pending, warn, error, noop, success, etc..
    status = FieldProperty(str, if_missing='pending')
    started_dt = FieldProperty(datetime, if_missing=datetime.utcnow)
    ended_dt = FieldProperty(datetime, if_missing=None)
    output = FieldProperty([str])

    INIT_NAME = 'INIT_DEPLOYMENT'

    @classmethod
    def create_init(cls):
        db, coll = pymongo_db_collection(cls)
        try:
            coll.insert({
                'name': cls.INIT_NAME,
                'status': 'noop',
                'started_dt': datetime.utcnow()
            })
        except DuplicateKeyError:  # pragma no cover
            return False

        return True

    @classmethod
    def has_init(cls):
        if cls.query.get(name=cls.INIT_NAME):
            return True

    @classmethod
    def upsert_init(cls):
        if not cls.has_init():
            return cls.create_init()
        return False

    @classmethod
    def create_from_migration(cls, mig, **kwargs):
        return cls(name=mig.get_name(), **kwargs)

    @classmethod
    def get_from_migration(cls, mig):
        return cls.query.get(name=mig.get_name())

    @classmethod
    def upsert_from_migration(cls, mig, **kwargs):
        miglog = cls.get_from_migration(mig)
        if miglog:
            for key, value in kwargs.items():
                setattr(miglog, key, value)
        else:
            miglog = cls.create_from_migration(mig, **kwargs)
        return miglog
