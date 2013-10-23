from ming.odm import ThreadLocalODMSession, session
from pylons import app_globals as g, tmpl_context as c

from vulcanforge.project.model import Project
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.tools.tickets.model import Ticket, TicketHistory
from vulcanforge.tools.tickets.tracker_main import ForgeTrackerApp


class ScriptException(Exception):
    pass


def main(args):
    project_path = "/{}/{}".format(args.neighborhood, args.project)
    project, extra = Project.by_url_path(project_path)
    if project:
        tracker = project.app_instance(args.tracker)
        if tracker and type(tracker) == ForgeTrackerApp:
            for cf in tracker.globals.custom_fields:
                name, label = cf['name'], cf['label']
                if label == args.milestone and 'milestones' in cf:
                    for m in cf['milestones']:
                        if m['name'] == args.name:
                            m['name'] = args.new_name
                            break
                    else:
                        msg = "No such milestone name: " + args.name
                        raise ScriptException(msg)
                    break
            else:
                msg = "No such custom milestone field: " + args.milestone
                raise ScriptException(msg)
            # update tickets
            app_config_id = tracker.globals.app_config_id
            db, coll_ticket = pymongo_db_collection(Ticket)
            query = {"app_config_id": app_config_id}
            count = 0
            for ticket in coll_ticket.find(query):
                cfs = ticket['custom_fields']
                if name in cfs and cfs[name] == args.name:
                    count += 1
                    cfs[name] = args.new_name
            print "Modified {} tickets.".format(count)
            # update ticket history
            db, coll_ticket_history = pymongo_db_collection(TicketHistory)
            count = 0
            for ticket_history in coll_ticket_history.find(query):
                cfs = ticket_history['data']['custom_fields']
                if name in cfs and cfs[name] == args.name:
                    count += 1
                    cfs[name] = args.new_name
            print "Modified {} ticket histories.".format(count)
        else:
            raise ScriptException("No such tracker: " + args.tracker)
    else:
        raise ScriptException("No such project: " + project_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Modifies milestone label in a tracker instance'
    )
    parser.add_argument('neighborhood')
    parser.add_argument('project')
    parser.add_argument('tracker')
    parser.add_argument('milestone')
    parser.add_argument('name')
    parser.add_argument('new_name')
    args = parser.parse_args()

    main(args)

    ThreadLocalODMSession.flush_all()
