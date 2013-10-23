import argparse
from ming.odm import ThreadLocalODMSession, session
from pylons import app_globals as g, tmpl_context as c

from vulcanforge.project.model import Project
from vulcanforge.common.util.model import pymongo_db_collection
from vulcanforge.tools.tickets.model import Ticket, TicketHistory
from vulcanforge.tools.tickets.tracker_main import ForgeTrackerApp


class ScriptException(Exception):
    pass


def main(args):
    """
    Modifies a milestone label in an tracker and updates its tickets and
    ticket histories.
    """
    project_path = "/{}/{}".format(args.neighborhood, args.project)
    project, extra = Project.by_url_path(project_path)
    if project:
        tracker = project.app_instance(args.tracker)
        if tracker and type(tracker) == ForgeTrackerApp:
            # update milestone label
            for cf in tracker.globals.custom_fields:
                name, label = cf['name'], cf['label']
                if label == args.milestone and 'milestones' in cf:
                    for m in cf['milestones']:
                        if m['name'] == args.old_name:
                            m['name'] = args.new_name
                            break
                    else:
                        msg = "No such milestone name: " + args.old_name
                        raise ScriptException(msg)
                    break
            else:
                msg = "No such custom milestone field: " + args.milestone
                raise ScriptException(msg)
            msg = "Updated milestone label '{}' for field '{}'."
            print msg.format(args.old_name, name)

            # update tickets and ticket histories
            field_base = "custom_fields." + name
            collections = dict(tickets=(Ticket, field_base),
                               histories=(TicketHistory, "data." + field_base))
            for item, (cls, field) in collections.items():
                db, col = pymongo_db_collection(cls)
                query = {'app_config_id': tracker.globals.app_config_id,
                         field: args.old_name}
                update = {"$set": {field: args.new_name}}
                result = col.update(query, update, multi=True)
                print "Updated {} {}.".format(result.get('n', 0), item)
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
    parser.add_argument('old_name')
    parser.add_argument('new_name')
    args = parser.parse_args()

    main(args)

    ThreadLocalODMSession.flush_all()
