#-*- python -*-
import cgi
import logging
import re
import time
from datetime import datetime, timedelta
import urllib
import itertools
from webob import exc
import pkg_resources

# Non-stdlib importshas_access
from tg import expose, validate, redirect, flash, url
from tg.decorators import with_trailing_slash, without_trailing_slash
from pylons import tmpl_context as c, app_globals as g, request, response
from formencode import validators, ForEach
from formencode.variabledecode import variable_decode
from bson import ObjectId
from webhelpers import feedgenerator as FG
from ming.odm.odmsession import session
from ming.utils import LazyProperty
import ew.jinja2_ew as ew

from vulcanforge.common.app import (
    Application,
    DefaultAdminController
)
from vulcanforge.common.controllers.decorators import (
    require_post,
    validate_form,
    vardec
)
from vulcanforge.common import validators as V, helpers as h
from vulcanforge.common.types import SitemapEntry
from vulcanforge.common.util import push_config
from vulcanforge.common.util.exception import exceptionless
from vulcanforge.common.widgets import form_fields as ffw
from vulcanforge.common.controllers import BaseController
from vulcanforge.artifact.controllers import (
    ArtifactRestController,
    AttachmentController,
    AttachmentsController
)
from vulcanforge.artifact.model import Shortlink, Feed
from vulcanforge.artifact.tasks import add_artifacts
from vulcanforge.artifact.widgets import (
    VFArtifactLink,
    LabelListWidget,
    RelatedArtifactsWidget
)
from vulcanforge.artifact.widgets.subscription import SubscribeForm
from vulcanforge.discussion.controllers import AppDiscussionController
from vulcanforge.discussion.model import Post
from vulcanforge.discussion.widgets import ThreadWidget
from vulcanforge.notification.model import Mailbox
from vulcanforge.project.widgets import ProjectUserSelect
from vulcanforge.resources import Icon
from . import model as TM
from . import version
from vulcanforge.tools.tickets.util import changelog
from vulcanforge.tools.tickets.widgets.forms import TicketCustomField
from .validators import MilestoneSchema
from .widgets import (
    TrackerTicketForm,
    BinForm,
    TicketSearchResults,
    MassEdit,
    MassEditForm,
    TrackerFieldAdmin,
)
from .import_support import ImportSupport

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge.tools.tickets:templates/tracker/'

search_validators = dict(
    q=validators.UnicodeString(if_empty=None),
    history=validators.StringBool(if_empty=False),
    project=validators.StringBool(if_empty=False),
    limit=validators.Int(if_invalid=None),
    page=validators.Int(if_empty=0),
    sort=validators.UnicodeString(if_empty=None))


class ForgeTrackerApp(Application):
    __version__ = version.__version__
    permissions = dict(Application.permissions,
        admin='Configure this tool, add new ticket properties and configure milestones',
        read='View tickets',
        write='Create and modify tickets',
        moderate='Moderate comments',
        unmoderated_post='Add comments without moderation',
        post='Add comments',
        save_searches='Persist custom searches',
        edit_protected='Edit ticket fields marked as protected'
    )
    searchable = True
    tool_label = 'Tickets'
    static_folder = 'Tickets'
    default_mount_label = 'Tickets'
    default_mount_point = 'tickets'
    icons = {
        24: '{ep_name}/images/tickets_24.png',
        32: '{ep_name}/images/tickets_32.png',
        48: '{ep_name}/images/tickets_48.png'
    }
    # whether its artifacts are referenceable from the repo browser
    reference_opts = dict(
        Application.reference_opts,
        can_reference=True,
        can_create=True
    )
    admin_description = (
        "The issue tracker helps you to keep track of items of work that need "
        "to be done. You can assign tasks, track progress, browse completed "
        "work, and set deadlines and milestones for your project."
    )
    admin_actions = {
        "Create Issue": {
            "url": "new",
            "permission": "post"
        },
        "View Issues": {"url": ""},
        "Edit Milestones": {
            "url": "milestones",
            "permission": "admin"
        }
    }
    default_acl = {
        'Admin': permissions.keys(),
        'Developer': ['write', 'moderate', 'save_searches'],
        '*authenticated': ['post', 'unmoderated_post'],
        '*anonymous': ['read']
    }
    artifacts = {
        "ticket": TM.Ticket
    }

    def __init__(self, project, config):
        Application.__init__(self, project, config)
        self.root = RootController(self)
        self.api_root = RootRestController()
        self.admin = TrackerAdminController(self)

    @LazyProperty
    def globals(self):
        return TM.Globals.query.get(app_config_id=self.config._id)

    def has_access(self, user, topic):
        return g.security.has_access(c.app, 'post', user=user)

    def handle_message(self, topic, message):
        LOG.info('Message from %s (%s)',
                 topic, self.config.options.mount_point)
        LOG.info('Headers are: %s', message['headers'])
        try:
            ticket = TM.Ticket.query.get(
                app_config_id=self.config._id,
                ticket_num=int(topic))
        except Exception:
            LOG.exception('Error getting ticket %s', topic)
        else:
            self.handle_artifact_message(ticket, message)

    def main_menu(self):
        """Apps should provide their entries to be added to the main nav
        :return: a list of :class:`SitemapEntries
        <vulcanforge.common.types.SitemapEntry>`

        """
        return [SitemapEntry(self.config.options.mount_label.title(), '.')]

    @property
    @exceptionless([], LOG)
    def sitemap(self):
        menu_id = self.config.options.mount_label.title()
        with push_config(c, app=self):
            return [SitemapEntry(menu_id, '.')[self.sidebar_menu()]]

    def admin_menu(self):
        admin_url = c.project.url() + 'admin/' + \
            self.config.options.mount_point + '/'
        links = [SitemapEntry('Field Management', admin_url + 'fields')]
        if self.permissions and g.security.has_access(self, 'admin'):
            links.append(SitemapEntry(
                'Permissions',
                admin_url + 'permissions',
                className='nav_child'
            ))
        return links

    def sidebar_menu(self):
        search_bins = []
        milestones = []
        links = []
        ticket = request.path_info.split(self.url)[-1].split('/')[0]
        for bin in self.bins:
            label = bin.shorthand_id()
            search_bins.append(SitemapEntry(
                h.truncate(label, 72),
                bin.url(),
                className='nav_child',
                small=c.app.globals.bin_count(label)['hits']
            ))
        milestone_counts = c.app.globals.milestone_counts
        for fld in c.app.globals.milestone_fields:
            milestones.append(SitemapEntry(h.truncate(fld.label, 72)))
            sub_milestones = []
            for m in getattr(fld, "milestones", []):
                if m.complete:
                    continue
                if m.get('due_date'):
                    dt = datetime.strptime(m['due_date'], '%m/%d/%Y')
                else:
                    dt = datetime.min
                count = milestone_counts.get(fld.name, {}).get(m.name, 0)
                sub_milestones.append((
                    dt,
                    SitemapEntry(
                        h.truncate(m.name, 72),
                        self.url + fld.name[1:] + '/' + m.name + '/',
                        className='nav_child',
                        small=str(count))
                ))
            milestones.extend([
                m[1] for m in sorted(sub_milestones, key=lambda sm: sm[0])
            ])
        if ticket.isdigit():
            ticket = TM.Ticket.query.find(dict(
                app_config_id=self.config._id,
                ticket_num=int(ticket)
            )).first()
        else:
            ticket = None
        if g.security.has_access(self, 'read'):
            links.append(SitemapEntry(
                'Home',
                self.config.url(),
                ui_icon=Icon('', 'ico-home')))
            links.append(SitemapEntry(
                'My Tickets',
                self.get_user_query_url(c.user.username),
                ui_icon=Icon('', 'ico-user')))
        if g.security.has_access(self, 'write'):
            links.append(SitemapEntry(
                'Create Ticket',
                self.config.url() + 'new/',
                ui_icon=Icon('', 'ico-plus')))
        links.append(SitemapEntry(
            'View Stats',
            self.config.url() + 'stats/',
            ui_icon=Icon('', 'ico-bars')
        ))
        discussion = c.app.config.discussion
        pending_mod_count = Post.query.find({
            'discussion_id': discussion._id,
            'status': 'pending'
        }).count()
        if pending_mod_count and g.security.has_access(discussion, 'moderate'):
            links.append(SitemapEntry(
                'Moderate',
                discussion.url() + 'moderate',
                ui_icon='ico-moderate',
                small=pending_mod_count))
        if ticket:
            next_ticket = ticket.get_next_accessible_for()
            if next_ticket:
                links.append(SitemapEntry(
                    'Next',
                    next_ticket.url(),
                    ui_icon=Icon('', 'ico-next')
                ))
            prev_ticket = ticket.get_prev_accessible_for()
            if prev_ticket:
                links.append(SitemapEntry(
                    'Previous',
                    prev_ticket.url(),
                    ui_icon=Icon('', 'ico-previous')
                ))
            if ticket.super_id:
                links.append(SitemapEntry('Supertask'))
                super = TM.Ticket.query.get(
                    _id=ticket.super_id, app_config_id=c.app.config._id)
                links.append(SitemapEntry(
                    '[#{0}]'.format(super.ticket_num),
                    super.url(),
                    className='nav_child'))
            if ticket.sub_ids:
                links.append(SitemapEntry('Subtasks'))
            for sub_id in ticket.sub_ids:
                sub = TM.Ticket.query.get(
                    _id=sub_id, app_config_id=c.app.config._id)
                links.append(SitemapEntry(
                    '[#{0}]'.format(sub.ticket_num),
                    sub.url(),
                    className='nav_child'))
            #links.append(SitemapEntry(
            # 'Create New Subtask',
            # '{0}new/?super_id={1}'.format(self.config.url(), ticket._id),
            # className='nav_child'))

        if g.security.has_access(self, 'admin'):
            admin_url = c.project.url() + 'admin/' + \
                        self.config.options.mount_point + '/'
            links.extend([
                SitemapEntry('Configure'),
                SitemapEntry(
                    'Edit Fields',
                    admin_url + 'fields',
                    ui_icon=Icon('', 'ico-edit')
                ),
                SitemapEntry(
                    'Edit Milestones',
                    self.config.url() + 'milestones',
                    ui_icon=Icon('', 'ico-edit')
                ),
                SitemapEntry(
                    'Edit Searches',
                    self.config.url() + 'bins/',
                    ui_icon=Icon('', 'ico-edit')
                )
            ])

        links += milestones

        if len(search_bins):
            links.append(SitemapEntry('Searches'))
            links = links + search_bins
        links.append(SitemapEntry('Help'))
        links.append(SitemapEntry(
            'Markdown Syntax',
            self.config.url() + 'markdown_syntax',
            ui_icon=Icon('', 'ico-info'),
            className='nav_child'))
        return links

    def get_global_navigation_data(self):
        actions = []
        if g.security.has_access(self, 'read'):
            actions.append({
                'label': 'Create New Ticket',
                'url': self.url + 'new/',
                'icon': 'ico-plus'
            })
        return {
            'actions': actions
        }

    def has_custom_field(self, field):
        """Checks if given custom field is defined. (Custom field names
        must start with '_'.)

        """
        for f in self.globals.custom_fields:
            if f['name'] == field:
                return True
        return False

    def install(self, project, acl=None):
        """Set up any default permissions and roles here"""
        super(ForgeTrackerApp, self).install(project, acl=acl)
        custom_fields = [{
            'name': '_milestone',
            'label': 'Milestone',
            'type': 'milestone',
            'show_in_search': True,
            'milestones': [
                {'name': '1.0', 'complete': False, 'due_date': None},
                {'name': '2.0', 'complete': False, 'due_date': None}
            ]
        }]

        gl_kwargs = {
            'app_config_id': c.app.config._id,
            'last_ticket_num': 0,
            'open_status_names': 'open unread accepted pending',
            'closed_status_names': 'closed wont-fix',
            'custom_fields': custom_fields
        }
        self.globals = TM.Globals(**gl_kwargs)
        session(self.globals).flush()
        c.app.globals.invalidate_bin_counts()

        open_bin = TM.Bin(
            summary='Open Tickets',
            terms=self.globals.not_closed_query
        )
        open_bin.app_config_id = self.config._id
        open_bin.custom_fields = dict()
        closed_bin = TM.Bin(
            summary='Changes',
            terms=self.globals.not_closed_query,
            sort='mod_date_dt desc'
        )
        closed_bin.app_config_id = self.config._id
        closed_bin.custom_fields = dict()
        session(TM.Globals).flush()

    def uninstall(self, project):
        """Remove all the tool's artifacts from the database"""
        app_config_id = {'app_config_id': c.app.config._id}
        TM.TicketAttachment.query.remove(app_config_id)
        TM.Ticket.query.remove(app_config_id)
        TM.Bin.query.remove(app_config_id)
        # model.Comment.query.remove(app_config_id)
        TM.Globals.query.remove(app_config_id)
        super(ForgeTrackerApp, self).uninstall(project)

    @property
    def bins(self):
        return TM.Bin.query.find(dict(
            app_config_id=self.config._id)).sort('summary').all()

    def get_calendar_events(self, date_start, date_end):
        milestones = self.globals.get_milestones_between(date_start, date_end)
        milestone_counts = self.globals.get_milestone_counts(
            _milestone_s='" OR "'.join([m["name"] for m in milestones]))
        events = []
        for milestone in milestones:
            due_date = datetime.strptime(milestone["due_date"], '%m/%d/%Y')
            due_date = int(time.mktime(due_date.timetuple()))
            title = "{app_label} Milestone {milestone_name} ({num})".format(
                app_label=self.config.options.mount_label,
                milestone_name=milestone["name"],
                num=milestone_counts.get(milestone["name"], 0)
            )
            events.append({
                "id": "{app_config_id}.{milestone_name}".format(
                    app_config_id=self.config._id,
                    milestone_name=milestone["name"]
                ),
                "title": title,
                "allDay": True,
                "start": due_date,
                "url": '{app_url}milestone/{milestone_name}/'.format(
                    app_url=self.url,
                    milestone_name=milestone["name"]),
                "className": "ticket-milestone-event"
            })
        return events

    def get_user_query_url(self, username):
        template = '{base}search/search/?q=' \
                   'assigned_to_s_mv:{username}+OR+' \
                   'reported_by_s:{username}'
        return template.format(base=self.config.url(), username=username)


class BaseTrackerController(BaseController):

    class Forms(BaseController.Forms):
        ticket_search_results = TicketSearchResults()
        mass_edit_form = MassEditForm(action="../update_tickets")

    class Widgets(BaseController.Widgets):
        mass_edit = MassEdit()

    @expose()
    @require_post()
    def update_tickets(self, **post_data):
        selected = post_data.get('selected', None)
        if selected is None:
            redirect(request.referer or c.app.url)  # TODO: check

        if isinstance(selected, list):
            tickets = TM.Ticket.query.find(dict(
                _id={'$in': [ObjectId(id) for id in post_data['selected']]},
                app_config_id=c.app.config._id)).all()
        else:
            tickets = TM.Ticket.query.find({
                '_id': ObjectId(selected)
            }).all()
        for ticket in tickets:
            g.security.require_access(ticket, 'write')
        fields = set(['status'])
        values = {}
        for k in fields:
            if not c.app.globals.can_edit_field(k):
                continue
            v = post_data.get(k)
            if v:
                values[k] = v
        if c.app.globals.can_edit_field('assigned_to'):
            assigned_to = post_data.get('assigned_to')
            if assigned_to and assigned_to.strip('-'):
                values['assigned_to_ids'] = []
                for username in assigned_to.split(','):
                    username = username.strip()
                    if username:
                        user = c.project.user_in_project(username)
                        if user:
                            values['assigned_to_ids'].append(user._id)

        custom_fields = {cf.name for cf in c.app.globals.custom_fields or []}
        custom_values = {}
        for k in custom_fields:
            if not c.app.globals.can_edit_field(k):
                continue
            v = post_data.get(k)
            if v:
                custom_values[k] = v

        for ticket in tickets:
            changed = False
            for k, v in values.iteritems():
                if not c.app.globals.can_edit_field(k):
                    continue
                if getattr(ticket, k) != v:
                    setattr(ticket, k, v)
                    changed = True
            for k, v in custom_values.iteritems():
                if not c.app.globals.can_edit_field(k):
                    continue
                if ticket.custom_fields.get(k) != v:
                    ticket.custom_fields[k] = v
                    changed = True
            if changed:
                ticket.commit()

        redirect(request.referer or c.app.url)


class TrackerSearchController(BaseController):

    class Widgets(BaseController.Widgets):
        artifact_link = VFArtifactLink()

    class Forms(BaseController.Forms):
        bin_form = BinForm()
        ticket_search_results = TicketSearchResults()

    @with_trailing_slash
    @vardec
    @expose(TEMPLATE_DIR + 'search.html')
    @validate(validators=search_validators)
    def search(self, query=None, columns=None, limit=None, page=0,
               sort="ticket_num_i desc", tool_q=None, **kw):
        q = kw.pop('q', None)  # temp
        q = tool_q or query or q or '*:*'
        c.bin_form = self.Forms.bin_form
        c.ticket_search_results = self.Forms.ticket_search_results
        c.artifact_link = self.Widgets.artifact_link
        bin_ = None
        if q:
            bin_ = TM.Bin.query.find(dict(
                app_config_id=c.app.config._id,
                terms=q
            )).first()
        result = TM.Ticket.paged_query(
            q, limit=limit, page=page, sort=sort, columns=columns, **kw
        )
        result['allow_edit'] = g.security.has_access(c.app, 'write')
        result['bin'] = bin_
        return result

    @expose(content_type="text/csv")
    def csv(self, **kwargs):
        now = datetime.utcnow()
        response.headerlist.append(
            ('Content-Disposition',
             'attachment;filename={}-{}-results-{}.csv'.format(
                 c.app.project.shortname,
                 c.app.config.options.mount_point,
                 now.date().isoformat())))
        fields = [
            ('ticket_num_i', '#'),
            ('summary_t', 'Summary'),
            ('status_s', 'Status'),
            ('open_b', 'Open'),
            ('created_date_dt', 'Date Created'),
            ('last_updated_dt', 'Last Updated'),
            ('closed_date_dt', 'Date Closed'),
            ('assigned_to_s_mv', 'Assigned To'),
            ('reported_by_s', 'Reported By')
        ] + [
            (field['name'] + '_s', field['label'])
            for field in c.app.globals.sortable_custom_fields_shown_in_search()
        ]
        # yield labels
        yield self.mk_csv_row([label for key, label in fields])

        # yield rows
        solr_query = kwargs.pop('q', None)
        solr_sort = kwargs.pop('sort', None)
        if solr_sort in (None, 'None'):
            solr_sort = 'ticket_num_i asc'
        start = 0
        rows = 100
        while True:
            solr_result = g.search.search_artifact(TM.Ticket, solr_query,
                                                   sort=solr_sort, start=start,
                                                   rows=rows)
            for result in solr_result.docs:
                yield self.mk_csv_row([result.get(key, '')
                                       for key, label in fields])
            if solr_result.hits > start + rows:
                start += rows
            else:
                break

    @staticmethod
    def mk_csv_row(items):
        for i in range(len(items)):
            if isinstance(items[i], (tuple, list)):
                items[i] = ', '.join(items[i])
            if isinstance(items[i], basestring):
                items[i] = items[i].replace(r'"', r'""')
        return ','.join(['"{}"'.format(item) for item in items]) + '\n'

    @expose('json')
    def aggregate(self, q, **kwargs):
        fields = {
            'status_s': "Status",
            'open_b': "Open",
            'assigned_to_s_mv': "Assignee",
            'reported_by_s': "Reporter",
            'labels_t': "Labels"
        }
        for custom_field in c.app.globals.custom_fields:
            if not custom_field.get('show_in_search'):
                continue
            if custom_field.get('type') == 'markdown':
                continue
            fields['{}_s'.format(custom_field.name)] = custom_field.label
        facet_query = {
            'facet': 'true',
            'facet.field': fields.keys(),
            'facet.mincount': 1
        }
        solr_result = g.search.search_artifact(TM.Ticket, q, **facet_query)
        return {
            'fields': fields,
            'facets': solr_result.facets
        }


class RootController(BaseTrackerController):

    class Forms(BaseTrackerController.Forms):
        subscribe_form = SubscribeForm()
        ticket_form = TrackerTicketForm()

    class Widgets(BaseTrackerController.Widgets):
        date_field = ffw.DateField()

    def __init__(self, app):
        setattr(self, 'feed.atom', self.feed)
        setattr(self, 'feed.rss', self.feed)
        self._discuss = AppDiscussionController()
        self.bins = BinController(app=app)
        self.search = TrackerSearchController()

    def _check_security(self):
        g.security.require_access(c.app, 'read')

    @with_trailing_slash
    @vardec
    @expose(TEMPLATE_DIR + 'index.html')
    def index(self, limit=None, columns=None, page=0, sort=None, **kw):
        kw.pop('q', None)
        kw.pop('query', None)
        result = self.search.search(
            query=c.app.globals.get_default_view_query(),
            sort=sort or c.app.globals.default_ticket_sort,
            columns=columns,
            page=page,
            limit=limit,
            **kw)
        c.subscribe_form = self.Forms.subscribe_form
        result['subscribed'] = Mailbox.subscribed()
        return result

    @with_trailing_slash
    @vardec
    @expose(TEMPLATE_DIR + 'aggregated.html')
    def aggregated(self, header_field='status_s', limit=500,
                   sort='_priority_s asc', **kw):
        q = c.app.globals.not_closed_query
        results = dict()
        facet_params = {
            'facet': 'on',
            'facet.field': header_field,
            'rows': 0
        }
        facet_search = g.search.search_artifact(TM.Ticket, q, **facet_params)
        facet_iter = iter(facet_search.facets['facet_fields'][header_field])
        for value, count in zip(facet_iter, facet_iter):
            header = "{}: {} ({})".format(header_field, value, count)
            results[header] = dict(
                result=TM.Ticket.paged_solr_query(
                    q, limit=limit, fq_dict={header_field: header}, sort=sort),
                count=count
            )
        c.search_results_widget = self.Forms.ticket_search_results
        del c.csv_url
        del c.aggregate_url
        return dict(field_name=header_field, results=results, limit=limit,
                    q=q, sort=sort)

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'milestones.html')
    def milestones(self, **kw):
        g.security.require_access(c.app, 'admin')
        milestones = []
        c.date_field = self.Widgets.date_field
        for fld in c.app.globals.milestone_fields:
            if fld.name == '_milestone':
                for m in fld.milestones:
                    due_date = None
                    if m.get('due_date'):
                        due_date = datetime.strptime(m['due_date'], '%m/%d/%Y')
                    milestones.append(dict(
                        name=m.name,
                        due_date=due_date,
                        due_date_str=m.get('due_date', ''),
                        description=m.get('description'),
                        complete=m.get('complete'),
                        total=c.app.globals.milestone_counts.get(m.name, 0),
                        closed=c.app.globals.milestone_closed_counts.get(
                            m.name, 0)
                    ))
        return dict(
            milestones=sorted(milestones,
                              key=lambda m: m['due_date'] or datetime.max))

    @without_trailing_slash
    @vardec
    @expose()
    @require_post()
    @validate({
        "milestones": ForEach(MilestoneSchema())
    })
    def update_milestones(self, field_name=None, milestones=None, **kw):
        g.security.require_access(c.app, 'admin')
        update_counts = False
        # TODO: fix this mess
        for fld in c.app.globals.milestone_fields:
            if fld.name == field_name:
                for new in milestones:
                    for m in fld.milestones:
                        if m.name == new['old_name']:
                            if new['new_name'] == '':
                                flash('You must name the milestone.', 'error')
                            else:
                                m.name = new['new_name']
                                m.description = new['description']
                                m.complete = new['complete'] == 'Closed'
                                if new['old_name'] != m.name:
                                    q = '%s:"%s"' % (fld.name, new['old_name'])
                                    r = g.search.search_artifact(
                                        TM.Ticket, q, rows=10000)
                                    if r:
                                        ticket_numbers = [match['ticket_num_i']
                                                          for match in r.docs]
                                        tickets = TM.Ticket.query.find(dict(
                                            app_config_id=c.app.config._id,
                                            ticket_num={'$in': ticket_numbers}
                                        )).all()
                                        for t in tickets:
                                            t.custom_fields[field_name] = m.name
                                        update_counts = True
                                elif m.get('due_date') != new['due_date']:
                                    m.due_date = new['due_date']
                                    # reindex artifacts when date changes
                                    q = '{}:"{}" AND project_id_s:"{}"'.format(
                                        fld.name,
                                        new['old_name'],
                                        str(c.project._id)
                                    )
                                    r = g.search.search_artifact(
                                        TM.Ticket, q, rows=10000)
                                    if r:
                                        ids = [m['id'] for m in r.docs]
                                        add_artifacts.post(ids)
                    if new['old_name'] == '' and new['new_name'] != '':
                        fld.milestones.append(dict(
                            name=new['new_name'],
                            description=new['description'],
                            due_date=new['due_date'],
                            complete=new['complete'] == 'Closed'))
                        update_counts = True
        if update_counts:
            c.app.globals.invalidate_bin_counts()
        redirect('milestones')

    @with_trailing_slash
    @vardec
    @expose()
    @validate(validators=search_validators)
    def search_feed(self, q=None, query=None, project=None, columns=None,
                    page=0, sort=None, **kw):
        if query and not q:
            q = query
        result = TM.Ticket.paged_query(q, page=page, sort=sort,
                                       columns=columns, **kw)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        d = dict(
            title='Ticket search results',
            link=c.app.url,
            description='You searched for %s' % q,
            language=u'en'
        )
        if request.environ['PATH_INFO'].endswith('.atom'):
            feed = FG.Atom1Feed(**d)
        else:
            feed = FG.Rss201rev2Feed(**d)
        for t in result['tickets']:
            feed.add_item(title=t.summary,
                          link=h.absurl(t.url().encode('utf-8')),
                          pubdate=t.mod_date,
                          description=t.description,
                          unique_id=str(t._id),
                          author_name=t.reported_by.display_name,
                          author_link=h.absurl(t.reported_by.url()))
        return feed.writeString('utf-8')

    @expose()
    def _lookup(self, arg, *remainder):
        if arg.isdigit():
            return TicketController(arg), remainder
        elif remainder:
            for field in c.app.globals.milestone_fields:
                if arg != field['name'][1:]:
                    continue
                milestone = request.url.split(arg+'/', 1)[1].split('/')[0]
                controller = MilestoneController(self, arg,
                                                 urllib.unquote(milestone))
                return controller, remainder[1:]
            raise exc.HTTPNotFound
        else:
            raise exc.HTTPNotFound

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'new_ticket.html')
    def new(self, super_id=None, description='', **kw):
        g.security.require_access(c.app, 'write')
        c.ticket_form = self.Forms.ticket_form
        return {
            'action': c.app.config.url() + 'save_ticket',
            'super_id': super_id,
            'defaults': {
                'super_id': super_id,
                'description': description
            }
        }

    @expose(TEMPLATE_DIR + 'new_ticket.html')
    def new_with_reference(self, artifact_ref=None, **kw):
        if not artifact_ref:
            raise exc.HTTPNotFound()
        shortlink = Shortlink.query.get(ref_id=urllib.unquote(artifact_ref))
        if shortlink:
            default_description = shortlink.render_link()
        else:
            default_description = ''
        return self.new(description=default_description, **kw)

    @expose('jinja:vulcanforge.common:templates/markdown_syntax.html')
    def markdown_syntax(self):
        """Static page explaining markdown."""
        return dict()

    @expose(TEMPLATE_DIR + 'help.html')
    def help(self):
        """Static help page."""
        return dict()

    @without_trailing_slash
    @expose()
    @validate({
        'since': V.DateTimeConverter(if_empty=None, if_invalid=None),
        'until': V.DateTimeConverter(if_empty=None, if_invalid=None),
        'offset': validators.Int(if_empty=None),
        'limit': validators.Int(if_empty=None)
    })
    def feed(self, since=None, until=None, offset=None, limit=None):
        if request.environ['PATH_INFO'].endswith('.atom'):
            feed_type = 'atom'
        else:
            feed_type = 'rss'
        title = 'Recent changes to %s' % c.app.config.options.mount_point
        feed = Feed.feed(
            dict(project_id=c.project._id, app_config_id=c.app.config._id),
            feed_type,
            title,
            c.app.url,
            title,
            since, until, offset, limit)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        return feed.writeString('utf-8')

    @vardec
    @expose()
    @require_post()
    @validate_form("ticket_form", error_handler=new)
    def save_ticket(self, ticket_form=None, **post_data):
        # if c.app.globals.milestone_names is None:
        #     c.app.globals.milestone_names = ''
        if ticket_form is None:
            ticket_form = post_data
        posted_values = variable_decode(request.POST)
        ticket_form['new_attachments'] = posted_values.get(
            'new_attachments', [])
        ticket_num = ticket_form.pop('ticket_num', None)
        ticket_form.pop('comment', None)
        if ticket_num:
            ticket = TM.Ticket.query.get(
                app_config_id=c.app.config._id,
                ticket_num=ticket_num)
            if not ticket:
                raise Exception('Ticket number not found.')
            g.security.require_access(ticket, 'write')
        else:
            g.security.require_access(c.app, 'write')
            ticket = TM.Ticket.new()
        ticket.update(ticket_form)
        redirect(str(ticket.ticket_num) + '/')

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'mass_edit.html')
    @validate(dict(q=validators.UnicodeString(if_empty=None),
                   limit=validators.Int(if_empty=10),
                   page=validators.Int(if_empty=0),
                   sort=validators.UnicodeString(if_empty='ticket_num_i asc')))
    def edit(self, q=None, limit=None, page=None, sort=None, **kw):
        g.security.require_access(c.app, 'write')
        result = TM.Ticket.paged_query(q, sort=sort, **kw)
        # if c.app.globals.milestone_names is None:
        #     c.app.globals.milestone_names = ''
        result['globals'] = c.app.globals
        result['cancel_href'] = url(
            c.app.url + 'search/search/',
            dict(q=q, limit=limit, sort=sort))
        c.user_select = ProjectUserSelect()
        c.mass_edit = self.Widgets.mass_edit
        c.mass_edit_form = self.Forms.mass_edit_form
        return result

    def tickets_since(self, when=None):
        query = {'app_config_id': c.app.config._id}
        if when:
            query['created_date'] = {'$gte': when}
        count = TM.Ticket.query.find(query).count()
        return count

    def ticket_comments_since(self, when=None):
        q = {'discussion_id': c.app.config.discussion_id}
        if when is not None:
            q['timestamp'] = {'$gte': when}
        return Post.query.find(q).count()

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'stats.html')
    def stats(self):
        tglobals = c.app.globals
        total = TM.Ticket.query.find(dict(
            app_config_id=c.app.config._id)).count()
        open = TM.Ticket.query.find(dict(
            app_config_id=c.app.config._id,
            status={'$in': list(tglobals.set_of_open_status_names)})).count()
        closed = TM.Ticket.query.find(dict(
            app_config_id=c.app.config._id,
            status={'$in': list(tglobals.set_of_closed_status_names)})).count()
        now = datetime.utcnow()
        week = timedelta(weeks=1)
        fortnight = timedelta(weeks=2)
        month = timedelta(weeks=4)
        week_ago = now - week
        fortnight_ago = now - fortnight
        month_ago = now - month
        week_tickets = self.tickets_since(week_ago)
        fortnight_tickets = self.tickets_since(fortnight_ago)
        month_tickets = self.tickets_since(month_ago)
        comments = self.ticket_comments_since()
        week_comments = self.ticket_comments_since(week_ago)
        fortnight_comments = self.ticket_comments_since(fortnight_ago)
        month_comments = self.ticket_comments_since(month_ago)
        c.user_select = ProjectUserSelect()
        return {
            'now': str(now),
            'week_ago': str(week_ago),
            'fortnight_ago': str(fortnight_ago),
            'month_ago': str(month_ago),
            'week_tickets': week_tickets,
            'fortnight_tickets': fortnight_tickets,
            'month_tickets': month_tickets,
            'comments': comments,
            'week_comments': week_comments,
            'fortnight_comments': fortnight_comments,
            'month_comments': month_comments,
            'total': total,
            'open': open,
            'closed': closed,
            'globals': tglobals
        }

    @expose()
    @validate_form("subscribe_form")
    def subscribe(self, subscribe=None, unsubscribe=None):
        if subscribe:
            Mailbox.subscribe(type='direct')
        elif unsubscribe:
            Mailbox.unsubscribe()
        redirect(request.referer or 'index')


class BinController(BaseController):

    class Forms(BaseController.Forms):
        bin_form = BinForm()

    def __init__(self, summary=None, app=None):
        if summary is not None:
            self.summary = summary
        if app is not None:
            self.app = app

    def _check_security(self):
        g.security.require_access(self.app, 'save_searches')

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'bin.html')
    def index(self, **kw):
        count = len(self.app.bins)
        return {
            'default_query': self.app.globals.default_view_query or '',
            'bins': self.app.bins,
            'count': count,
            'app': self.app
        }

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'new_bin.html')
    def newbin(self, q=None, **kw):
        c.bin_form = self.Forms.bin_form
        return dict(
            q=q or '',
            bin=bin or '',
            modelname='Bin',
            page='New Bin',
            globals=self.app.globals
        )

    @with_trailing_slash
    @vardec
    @expose()
    @require_post()
    @validate_form("bin_form", error_handler=newbin)
    def save_bin(self, **bin_form):
        self.app.globals.invalidate_bin_counts()
        bin = bin_form['_id']
        if bin is None:
            bin = TM.Bin(app_config_id=self.app.config._id, summary='')
        else:
            g.security.require(
                lambda: bin.app_config_id == self.app.config._id)
        bin.summary = bin_form['summary']
        bin.terms = bin_form['terms']
        redirect('.')

    @with_trailing_slash
    @expose()
    @require_post()
    @validate(validators=dict(bin=V.MingValidator(TM.Bin)))
    def delbin(self, tbin=None):
        g.security.require(lambda: tbin.app_config_id == self.app.config._id)
        self.app.globals.invalidate_bin_counts()
        tbin.delete()
        redirect(request.referer or 'index')  # TODO: check

    @without_trailing_slash
    @vardec
    @expose()
    @require_post()
    def update_bins(self, bins=None, default_query=None, **kw):
        g.security.require_access(self.app, 'save_searches')
        for bin_form in bins:
            tbin = None
            if bin_form['id']:
                tbin = TM.Bin.query.find(dict(
                    app_config_id=self.app.config._id,
                    _id=ObjectId(bin_form['id']))).first()
            elif bin_form['summary'] and bin_form['terms']:
                tbin = TM.Bin(app_config_id=self.app.config._id, summary='')
            if tbin:
                if bin_form['delete'] == 'True':
                    tbin.delete()
                else:
                    tbin.summary = bin_form['summary']
                    tbin.terms = bin_form['terms']
        self.app.globals.default_view_query = default_query
        self.app.globals.query.session.flush(self.app.globals)
        self.app.globals.invalidate_bin_counts()
        redirect('.')


class TicketController(BaseTrackerController):

    class Widgets(BaseTrackerController.Widgets):
        thread = ThreadWidget(
            page=None, limit=None, page_size=None, count=None,
            style='linear')
        label_list = LabelListWidget()
        attachment_list = ffw.AttachmentList()
        ticket_custom_field = TicketCustomField
        related_artifacts = RelatedArtifactsWidget()

    class Forms(BaseTrackerController.Forms):
        ticket_update_form = TrackerTicketForm(comment=True)
        ticket_subscribe_form = SubscribeForm(thing='ticket')

    def __init__(self, ticket_num=None):
        if ticket_num is not None:
            self.ticket_num = int(ticket_num)
            self.ticket = TM.Ticket.query.get(
                app_config_id=c.app.config._id, ticket_num=self.ticket_num)
            self.attachment = TrackerAttachmentsController(self.ticket)
            # self.comments = CommentController(self.ticket)
        setattr(self, 'feed.atom', self.feed)
        setattr(self, 'feed.rss', self.feed)

    def _check_security(self):
        if self.ticket is not None:
            g.security.require_access(self.ticket, 'read')

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'ticket.html')
    @validate({'page': validators.Int(if_empty=0),
               'limit': validators.Int(if_empty=10)})
    def index(self, page=0, limit=10, **kw):
        if self.ticket is None:
            raise exc.HTTPNotFound(
                'Ticket #%s does not exist.' % self.ticket_num)
        c.thread = self.Widgets.thread
        c.attachment_list = self.Widgets.attachment_list
        c.subscribe_form = self.Forms.ticket_subscribe_form
        c.related_artifacts_widget = self.Widgets.related_artifacts
        c.label_list = self.Widgets.label_list
        tool_subscribed = Mailbox.subscribed()
        if tool_subscribed:
            subscribed = False
        else:
            subscribed = Mailbox.subscribed(artifact=self.ticket)
        post_count = self.ticket.discussion_thread.post_count
        limit, page = h.paging_sanitizer(limit, page, post_count)
        return {
            'ticket': self.ticket,
            'globals': c.app.globals,
            'allow_edit': g.security.has_access(self.ticket, 'write'),
            'tool_subscribed': tool_subscribed,
            'subscribed': subscribed,
            'page': page,
            'limit': limit,
            'count': post_count
        }

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'ticket_edit.html')
    def edit(self, **kwargs):
        c.attachment_list = self.Widgets.attachment_list
        c.ticket_update_form = self.Forms.ticket_update_form
        c.related_artifacts_widget = self.Widgets.related_artifacts
        attachment_context_id = str(self.ticket._id)
        return {
            'ticket': self.ticket,
            'attachment_context_id': attachment_context_id
        }

    @without_trailing_slash
    @expose()
    @validate({
        'since': V.DateTimeConverter(if_empty=None, if_invalid=None),
        'until': V.DateTimeConverter(if_empty=None, if_invalid=None),
        'offset': validators.Int(if_empty=None),
        'limit': validators.Int(if_empty=None)
    })
    def feed(self, since=None, until=None, offset=None, limit=None):
        if request.environ['PATH_INFO'].endswith('.atom'):
            feed_type = 'atom'
        else:
            feed_type = 'rss'
        title = 'Recent changes to %d: %s' % (
            self.ticket.ticket_num, self.ticket.summary)
        feed = Feed.feed(
            {'ref_id': self.ticket.index_id()},
            feed_type,
            title,
            self.ticket.url(),
            title,
            since, until, offset, limit)
        response.headers['Content-Type'] = ''
        response.content_type = 'application/xml'
        return feed.writeString('utf-8')

    @expose()
    @require_post()
    @vardec
    @validate_form("ticket_update_form", error_handler=edit)
    def update_ticket(self, **post_data):
        g.security.require_access(self.ticket, 'write')
        changes = changelog()
        comment = post_data.pop('comment', None)
        labels = post_data.pop('labels', None) or []
        if labels:
            changes['labels'] = self.ticket.labels
            changes['labels'] = labels
        self.ticket.labels = labels
        for k in ['summary', 'description', 'status']:
            if not c.app.globals.can_edit_field(k):
                continue
            changes[k] = getattr(self.ticket, k)
            setattr(self.ticket, k, post_data.pop(k, ''))
            changes[k] = getattr(self.ticket, k)
        if 'assigned_to' in post_data \
                and c.app.globals.can_edit_field('assigned_to'):
            changes['assigned_to'] = ','.join(
                u.display_name for u in self.ticket.assigned_to)
            assigned_to_ids = []
            old_ids = set(self.ticket.assigned_to_ids)
            for user in post_data['assigned_to']:
                if c.project.user_in_project(user=user):
                    assigned_to_ids.append(user._id)
                    if user._id not in old_ids:
                        self.ticket.subscribe(user)
            self.ticket.assigned_to_ids = assigned_to_ids
            changes['assigned_to'] = ','.join(
                u.display_name for u in self.ticket.assigned_to)
        if c.app.globals.can_edit_field('private'):
            self.ticket.private = post_data.get('private', False)

        # if c.app.globals.milestone_names is None:
        #     c.app.globals.milestone_names = ''
        posted_values = variable_decode(request.POST)
        attachments = posted_values.get('new_attachments', [])
        changes['attachments'] = ''
        attachment_changelog_items = []
        for attachment in attachments:
            if not hasattr(attachment, 'file'):
                continue
            att = self.ticket.attach(
                attachment.filename, attachment.file,
                content_type=attachment.type)
            attachment_changelog_items.append(
                '{} ({})'.format(
                    att[0].filename,
                    h.pretty_print_file_size(att[0].length))
            )
        changes['attachments'] = ', '.join(attachment_changelog_items)
        any_sums = False
        post_custom_fields = post_data.get('custom_fields', {})
        post_markdown_custom_fields = post_data.get(
            'markdown_custom_fields', {})
        for cf in c.app.globals.custom_fields or []:
            if not c.app.globals.can_edit_field(cf.name):
                continue
            if cf.name in post_custom_fields:
                value = post_custom_fields[cf.name]
                if cf.type == 'sum':
                    any_sums = True
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        value = 0
            elif cf.name in post_markdown_custom_fields:
                value = post_markdown_custom_fields[cf.name]
            elif cf.name == '_milestone' and cf.name in post_data:
                value = post_data[cf.name]
            # unchecked boolean won't be passed in, so make it False here
            elif cf.type == 'boolean':
                value = False
            else:
                value = ''
            if cf.type == 'number' and value == '':
                value = None
            if value is not None:
                changes[cf.name[1:]] = self.ticket.custom_fields.get(cf.name)
                self.ticket.custom_fields[cf.name] = value
                changes[cf.name[1:]] = self.ticket.custom_fields.get(cf.name)
        thread = self.ticket.discussion_thread
        versions = dict(safe_text="safe_", text="")
        clist = changes.get_changed()
        for k, v in versions.items():
            tpath = "data/" + v + "ticket_changed_tmpl"
            t = 'vulcanforge.tools.tickets'
            tpl = pkg_resources.resource_filename(t, tpath)
            ctext = h.render_genshi_plaintext(tpl, changelist=clist)
            if comment:
                ct = "Comment: " + comment if k == "text" else "Comment added."
                ctext += "\n" + ct
            versions[k] = "\n\n" + ctext
        thread.add_post(**versions)
        self.ticket.commit()
        if any_sums:
            self.ticket.dirty_sums()
        session(TM.Ticket).flush()
        redirect(self.ticket.url())

    @expose()
    @validate_form("ticket_subscribe_form")
    def subscribe(self, subscribe=None, unsubscribe=None):
        if subscribe:
            self.ticket.subscribe(type='direct')
        elif unsubscribe:
            self.ticket.unsubscribe()
        redirect(request.referer or 'index')  # TODO: check


class TrackerAttachmentController(AttachmentController):
    AttachmentClass = TM.TicketAttachment
    edit_perm = 'write'


class TrackerAttachmentsController(AttachmentsController):
    AttachmentControllerClass = TrackerAttachmentController

NONALNUM_RE = re.compile(r'\W+')


class TrackerAdminController(DefaultAdminController):

    class Forms(DefaultAdminController):
        field_admin = TrackerFieldAdmin()

    def __init__(self, app):
        self.app = app
        #self.bins = BinController(app=app)
        # if self.app.globals and self.app.globals.milestone_names is None:
        #     self.app.globals.milestone_names = ''

    def _check_security(self):
        g.security.require_access(self.app, 'admin')

    @expose()
    @with_trailing_slash
    def index(self, **kw):
        redirect('permissions')

    @without_trailing_slash
    @expose(TEMPLATE_DIR + 'admin_fields.html')
    def fields(self, **kw):
        c.form = self.Forms.field_admin
        return dict(app=self.app, globals=self.app.globals)

    @expose()
    @validate_form("field_admin", error_handler=fields)
    @require_post()
    @vardec
    def set_custom_fields(self, **post_data):
        for k in [
            'open_status_names',
            'closed_status_names',
            'protected_field_names',
            'show_assigned_to',
            'assigned_to_label',
            'show_description',
            'description_label'
        ]:
            value = post_data.get(k)
            if value is not None:
                setattr(self.app.globals, k, value)
        custom_fields = post_data.get('custom_fields', [])
        for field in custom_fields:
            field['name'] = '_' + '_'.join(
                [w for w in NONALNUM_RE.split(field['label'].lower()) if w]
            )
            field['label'] = field['label'].title()
        self.app.globals.custom_fields = custom_fields
        flash('Fields updated')
        redirect(request.referer or 'permissions')


class RootRestController(BaseController):
    """
    B{Description}: Ticket creation and listing.

    @undocumented: __init__, validate_import, perform_import

    """
    class Forms(BaseController.Forms):
        ticket_form = TrackerTicketForm()

    def __init__(self):
        #self._discuss = AppDiscussionRestController()
        self.artifact = ArtifactRestController()

    def _check_security(self):
        g.security.require_access(c.app, 'read')

    @expose('json')
    def index(self, **kw):
        """
        B{Description}: Retrieve all tickets for a given project/tool.
        Note that it only returns the ticket num and summary.

        B{Errors}
            - 404: If the neighborhood, the project or the tool does not exist

        B{Requires authentication}

        B{Example request}

        GET I{rest/neighborhood/project/ticket_tool/}

        @return: {
        tickets=[{
        ticket_num: int,
        summary: str,
        }, ...]
        }

        @rtype: JSON document
        """
        return dict(tickets=[
            dict(ticket_num=t.ticket_num, summary=t.summary)
            for t in TM.Ticket.query.find(dict(
                app_config_id=c.app.config._id)).sort('ticket_num')
        ])

    @expose()
    @require_post()
    @vardec
    @validate_form("ticket_form", error_handler=h.json_validation_error)
    def new(self, ticket_form=None, **post_data):
        """
        B{Description}: Make a new ticket for any ticket tool instance.
        Note that the author must have create privilege for the tool.

        B{Errors}
            - 404: If the neighborhood, the project or the tool does not exist

        B{Requires authentication}

        B{Example request}

        GET I{rest/neighborhood/project/tool/new?
            summary='Something'&description='Some text'}

        @return: {
        "summary": str,
        "description": str,
        "assigned_to": str,
        "reported_by": str,
        "ticket_num": int
        ...
        }
        @rtype: JSON document

        """
        g.security.require_access(c.app, 'write')
        if ticket_form is None:
            ticket_form = post_data
        if c.app.globals.milestone_names is None:
            c.app.globals.milestone_names = ''
        ticket = TM.Ticket(
            app_config_id=c.app.config._id,
            custom_fields=dict(),
            ticket_num=c.app.globals.next_ticket_num())
        ticket.update(ticket_form)
        redirect(str(ticket.ticket_num) + '/')

    @expose('json')
    def validate_import(self, doc=None, options=None, **post_data):
        g.security.require_access(c.project, 'admin')
        migrator = ImportSupport()
        try:
            status = migrator.validate_import(doc, options, **post_data)
            return status
        except Exception, e:
            LOG.exception(e)
            return dict(status=False, errors=[repr(e)])

    @expose('json')
    def perform_import(self, doc=None, options=None, **post_data):
        g.security.require_access(c.project, 'admin')
        if c.api_token.get_capability('import') != c.project.shortname:
            LOG.error(
                'Import capability is not enabled for %s', c.project.shortname)
            raise exc.HTTPForbidden(detail='Import is not allowed')

        migrator = ImportSupport()
        try:
            status = migrator.perform_import(doc, options, **post_data)
            return status
        except Exception, e:
            LOG.exception(e)
            return dict(status=False, errors=[str(e)])

    @expose()
    def _lookup(self, ticket_num, *remainder):
        return TicketRestController(ticket_num), remainder


class TicketRestController(BaseController):
    """
    B{Description}: Ticket lookup and saving.

    @undocumented: __init__
    """
    class Forms(BaseController.Forms):
        ticket_form = TrackerTicketForm()

    def __init__(self, ticket_num):
        if ticket_num is not None:
            self.ticket_num = int(ticket_num)
            self.ticket = TM.Ticket.query.get(app_config_id=c.app.config._id,
                                              ticket_num=self.ticket_num)

    def _check_security(self):
        g.security.require_access(self.ticket, 'read')

    @expose('json')
    def index(self, **kw):
        """
        B{Description}: Retrieve detailed information about a ticket identified
        by ticket_number

        B{Errors}
            - 404: If the neighborhood, the project or the tool does not exist

        B{Requires authentication}

        B{Example request}

        GET I{rest/neighborhood/project/tool/ticket_number/}

        @return: {
        "summary": str,
        "description": str,
        "assigned_to": str,
        "reported_by": str,
        "ticket_num": int
        ...
        }
        @rtype: JSON document
        """
        return dict(ticket=self.ticket)

    @expose()
    @vardec
    @require_post()
    @validate_form("ticket_form", error_handler=h.json_validation_error)
    def save(self, ticket_form=None, **post_data):
        """
        B{Description}: Edit an existing ticket.

        B{Errors}
            - 404: If the neighborhood, the project or the tool does not exist

        B{Requires authentication}

        B{Example request}

        GET I{rest/neighborhood/project/tool/ticket_number/save?
            summary='Something'&description='Some text'}

        @return: {
        "summary": str,
        "description": str,
        "assigned_to": str,
        "reported_by": str,
        "ticket_num": int
        ...
        }
        @rtype: JSON document
        """
        if ticket_form is None:
            ticket_form = post_data
        g.security.require_access(self.ticket, 'write')
        # if c.app.globals.milestone_names is None:
        #     c.app.globals.milestone_names = ''
        self.ticket.update(ticket_form)
        redirect('.')


class MilestoneController(BaseTrackerController):

    class Widgets(BaseTrackerController.Widgets):
        auto_resize_textarea = ew.TextArea()
        project_user_select = ProjectUserSelect()
        artifact_link = VFArtifactLink()

    def __init__(self, root, field, milestone):
        for fld in c.app.globals.milestone_fields:
            if fld.name[1:] == field:
                break
        else:
            raise exc.HTTPNotFound()
        for m in fld.milestones:
            if m.name == milestone:
                break
        else:
            raise exc.HTTPNotFound()
        self.root = root
        self.field = fld
        self.milestone = m
        self.query = '{}_s:"{}"'.format(fld.name, m.name)
        self.mongo_query = {'custom_fields.{}'.format(fld.name): m.name}

    def _before(self, *args, **kwargs):
        c.artifact_link = self.Widgets.artifact_link

    @with_trailing_slash
    @vardec
    @expose(TEMPLATE_DIR + 'milestone.html')
    @validate(validators=dict(
            limit=validators.Int(if_invalid=None),
            page=validators.Int(if_empty=0),
            sort=validators.UnicodeString(if_empty=None)))
    def index(self, q=None, columns=None, page=0, query=None, sort=None, **kw):
        g.security.require_access(c.app, 'read')
        result = TM.Ticket.paged_query(self.query,
                                       page=page, sort=sort,
                                       columns=columns, **kw)
        result['allow_edit'] = g.security.has_access(c.app, 'write')
        result.pop('q')
        result.update(
            field=self.field,
            milestone=self.milestone,
            total=c.app.globals.milestone_counts.get(self.milestone.name, 0),
            closed=c.app.globals.milestone_closed_counts.get(
                self.milestone.name, 0)
        )
        c.ticket_search_results = self.Forms.ticket_search_results
        c.auto_resize_textarea = self.Widgets.auto_resize_textarea
        return result

    @with_trailing_slash
    @expose(TEMPLATE_DIR + 'mass_edit.html')
    @validate(dict(q=validators.UnicodeString(if_empty=None),
                   limit=validators.Int(if_empty=10),
                   page=validators.Int(if_empty=0),
                   sort=validators.UnicodeString(if_empty='ticket_num_i asc')))
    def edit(self, q=None, limit=None, page=None, sort=None, columns=None,
             **kw):
        g.security.require_access(c.app, 'write')
        result = TM.Ticket.paged_query(
            self.query, page=page, sort=sort, columns=columns, **kw)
        # if c.app.globals.milestone_names is None:
        #     c.app.globals.milestone_names = ''
        result.pop('q')
        result['globals'] = c.app.globals
        result['cancel_href'] = '..'
        c.user_select = self.Widgets.project_user_select
        c.mass_edit = self.Widgets.mass_edit
        c.mass_edit_form = self.Forms.mass_edit_form
        return result
