import logging

from datetime import datetime
from ming import schema as S
from ming.odm import (
    FieldProperty,
    ForeignIdProperty
)

from vulcanforge.common.model.base import BaseMappedClass
from vulcanforge.common.model.session import main_orm_session

LOG = logging.getLogger(__name__)


class ExchangeVisit(BaseMappedClass):

    class __mongometa__:
        name = 'app_visit'
        session = main_orm_session
        indexes = [('user_id', 'app_config_id')]

    _id = FieldProperty(S.ObjectId)
    user_id = ForeignIdProperty('User', if_missing=None)
    exchange_uri = FieldProperty(str, if_missing=None)

    last_visit = FieldProperty(datetime, if_missing=None)

    @classmethod
    def upsert(cls, user_id, exchange_uri):
        visit = cls.query.get(user_id=user_id, exchange_uri=exchange_uri)
        if not visit:
            visit = cls(user_id=user_id, exchange_uri=exchange_uri)

        visit.last_visit = datetime.utcnow()
        visit.flush_self()

        return visit