import logging

from ming.odm import ThreadLocalODMSession

from vulcanforge.common.model.session import (
    project_doc_session,
    ArtifactSessionExtension
)
from vulcanforge.tools.tickets.tasks import add_tickets

LOG = logging.getLogger(__name__)


class TicketSessionExtension(ArtifactSessionExtension):
    """Ensures bin counts are updated on flush"""

    def index_new(self, new_ref_ids):
        add_tickets.post(new_ref_ids)


ticket_orm_session = ThreadLocalODMSession(
    doc_session=project_doc_session,
    extensions=[TicketSessionExtension]
)
