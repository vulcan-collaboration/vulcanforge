from pylons import app_globals as g
from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.tickets.tasks import add_tickets


class IndexSortableTicketAssignee(BaseMigration):
    def run(self):
        result = g.search('type_s:Ticket AND NOT assigned_to_name_s')
        ref_ids = [d['id'] for d in result.docs]
        add_tickets(ref_ids)
        self.write_output('Reindexed {} tuckets'.format(len(ref_ids)))
