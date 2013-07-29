from ming import schema as S
from ming.odm import FieldProperty

from .base import BaseMappedClass
from vulcanforge.common.model.session import main_orm_session
from vulcanforge.common.util.model import pymongo_db_collection


class ForgeGlobals(BaseMappedClass):
    """Singleton Container for global persisted information for a deployment"""

    class __mongometa__:
        name = 'forge_globals'
        session = main_orm_session

    _id = FieldProperty(S.ObjectId)
    user_counter = FieldProperty(int, if_missing=1)
    taskd_tester = FieldProperty(S.Object({
        'counter': S.Int(if_missing=0),
        'args': [],
        'kwargs': None
    }))

    @classmethod
    def inc_user_counter(cls):
        """Get current user counter and increment by 1"""
        _, coll = pymongo_db_collection(cls)
        doc = coll.find_and_modify(update={"$inc": {"user_counter": 1}})
        return doc["user_counter"]
