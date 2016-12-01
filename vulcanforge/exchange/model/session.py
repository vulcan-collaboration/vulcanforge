import logging

from ming import Session
from ming.odm.odmsession import ThreadLocalODMSession

from vulcanforge.common.model.session import ArtifactSessionExtension


LOG = logging.getLogger(__name__)


class ExchangeNodeSession(ArtifactSessionExtension):
    def index_new(self, new_ref_ids, mod_dates=None):
        super(ExchangeNodeSession, self).index_new(new_ref_ids, mod_dates)


exchange_session = Session.by_name('exchange')
exchange_orm_session = ThreadLocalODMSession(exchange_session)
exchange_node_session = ThreadLocalODMSession(
    doc_session=exchange_session,
    extensions=[ExchangeNodeSession])