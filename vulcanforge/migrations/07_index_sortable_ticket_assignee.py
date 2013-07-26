from pylons import app_globals as g
from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.tickets.tasks import add_tickets


class IndexSortableTicketAssignee(BaseMigration):
    PAGE_SIZE = 500

    def run(self):
        result = None
        page = 0
        while result is None or page * self.PAGE_SIZE < result.hits:
            result = g.search(
                'type_s:Ticket AND NOT assigned_to_name_s',
                rows=self.PAGE_SIZE,
                page=page)
            ref_ids = [d['id'] for d in result.docs]
            add_tickets(ref_ids)
            page += 1
        self.write_output('Reindexed {} tuckets'.format(result.hits))
