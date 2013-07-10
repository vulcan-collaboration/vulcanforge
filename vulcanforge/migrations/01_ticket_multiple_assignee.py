from ming.odm import ThreadLocalODMSession, session
from pylons import app_globals as g, tmpl_context as c

from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.tickets.model import Ticket, Globals, Bin, TicketHistory
from vulcanforge.tools.tickets.tasks import add_tickets


class TicketMultipleAssignees(BaseMigration):
    def run(self):
        db, coll_ticket = pymongo_db_collection(Ticket)
        db, coll_ticket_history = pymongo_db_collection(TicketHistory)
        ref_ids = []
        ac_ids = set()
        ticket_count = 0
        query = {"assigned_to_id": {"$exists": 1}}
        for ticket_doc in coll_ticket.find(query):
            ticket_doc['assigned_to_ids'] = [ticket_doc.pop('assigned_to_id')]
            coll_ticket.save(ticket_doc)
            ac_ids.add(ticket_doc['app_config_id'])
            ticket = Ticket.query.get(_id=ticket_doc['_id'])
            ref_ids.append(ticket.index_id())
            ticket_count += 1

        self.write_output('Updated {} tickets'.format(ticket_count))
        ThreadLocalODMSession.flush_all()
        session(Ticket).clear()

        # repare historical dooders
        hist_count = 0
        query = {"data.assigned_to_id": {"$exists": 1}}
        for ticket_hist in coll_ticket_history.find(query):
            ticket_hist['data']['assigned_to_ids'] = [ticket_hist['data'].pop(
                'assigned_to_id')]
            coll_ticket_history.save(ticket_hist)
            hist_count += 1

        self.write_output('Updated {} ticket histories'.format(hist_count))

        bin_count = 0
        global_cur = Globals.query.find({
            "app_config_id": {"$in": list(ac_ids)}})
        for ticket_global in global_cur:
            app_context = g.context_manager.push(
                app_config_id=ticket_global.app_config_id)
            with app_context:
                bin_cur = Bin.query.find({
                    "app_config_id": c.app.config._id
                })
                for ticket_bin in bin_cur:
                    ticket_bin.terms = ticket_bin.terms.replace(
                        'assigned_to_s:', 'assigned_to:')
                    bin_count += 1
            session(Bin).flush()

        add_tickets(ref_ids)

        self.write_output('Updated {} ticket search bins'.format(bin_count))
