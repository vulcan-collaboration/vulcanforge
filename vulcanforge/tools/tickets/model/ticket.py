import logging
import urllib
import json
from datetime import datetime
import itertools

import bson
import pymongo
from pymongo.errors import OperationFailure
from pylons import tmpl_context as c, app_globals as g

from ming import schema
from ming.utils import LazyProperty
from ming.odm import session
from ming.odm import FieldProperty, ForeignIdProperty, RelationProperty
from ming.odm.declarative import MappedClass

from vulcanforge.common.model.session import project_orm_session
from vulcanforge.common.util import diff as patience, ConfigProxy
from vulcanforge.artifact.model import (
    Artifact,
    VersionedArtifact,
    Snapshot,
    Feed,
    BaseAttachment
)
from vulcanforge.auth.model import User
from vulcanforge.auth.schema import ACE, ALL_PERMISSIONS, DENY_ALL
from vulcanforge.discussion.model import Thread
from vulcanforge.notification.model import Notification
from vulcanforge.project.model import ProjectRole
from vulcanforge.tools.tickets.tasks import refresh_search_counts
from .session import ticket_orm_session

LOG = logging.getLogger(__name__)

config = ConfigProxy(common_suffix='forgemail.domain')


class Globals(MappedClass):

    class __mongometa__:
        name = 'globals'
        session = project_orm_session
        indexes = ['app_config_id']

    type_s = 'Globals'
    _id = FieldProperty(schema.ObjectId)
    app_config_id = ForeignIdProperty(
        'AppConfig', if_missing=lambda: c.app.config._id)
    last_ticket_num = FieldProperty(int)
    status_names = FieldProperty(str)
    open_status_names = FieldProperty(str)
    closed_status_names = FieldProperty(str)
    protected_field_names = FieldProperty(str, if_missing='')
    show_assigned_to = FieldProperty(schema.Bool, if_missing=True)
    assigned_to_label = FieldProperty(schema.String, if_missing='Assigned To')
    show_description = FieldProperty(schema.Bool, if_missing=True)
    description_label = FieldProperty(schema.String, if_missing='Description')
    milestone_names = FieldProperty(str, if_missing='')
    custom_fields = FieldProperty([{str: None}])
    simple_form = FieldProperty(schema.Deprecated)  # bool, if_missing=False)
    _bin_counts = FieldProperty(schema.Deprecated)  # {str:int})
    _bin_counts_data = FieldProperty([dict(summary=str, hits=int)])
    _bin_counts_expire = FieldProperty(datetime)
    _milestone_counts = FieldProperty([dict(name=str, hits=int, closed=int)])
    _milestone_counts_expire = FieldProperty(datetime)

    app_config = RelationProperty('AppConfig')

    @classmethod
    def next_ticket_num(cls):
        gbl = cls.query.find_and_modify(
            query=dict(app_config_id=c.app.config._id),
            update={'$inc': {'last_ticket_num': 1}},
            new=True)
        session(cls).expunge(gbl)
        return gbl.last_ticket_num

    @property
    def all_status_names(self):
        return ' '.join([self.open_status_names, self.closed_status_names])

    @property
    def set_of_all_status_names(self):
        return {name for name in self.all_status_names.split(' ') if name}

    @property
    def set_of_open_status_names(self):
        return {name for name in self.open_status_names.split(' ') if name}

    @property
    def set_of_closed_status_names(self):
        return {name for name in self.closed_status_names.split(' ') if name}

    @property
    def closed_query(self):
        return "status_s:(%s)" % ', '.join(
            '"{}"'.format(s) for s in self.set_of_closed_status_names
        )

    @property
    def not_closed_query(self):
        return "NOT %s" % self.closed_query

    @property
    def not_closed_mongo_query(self):
        return dict(
            status={'$in': list(self.set_of_open_status_names)})

    @property
    def default_ticket_sort(self):
        return 'ticket_num_i desc'

    @property
    def milestone_fields(self):
        return [fld for fld in self.custom_fields \
                if fld.get('type') == 'milestone']

    def get_milestone_counts(self, **kw):
        params = {
            "facet": "on",
            "facet.field": "_milestone_s",
            "rows": 0
        }
        params.update(kw)
        q = ' AND '.join((
            'app_config_id_s:{}'.format(c.app.config._id),
            'type_s:"{}"'.format(Ticket.type_s),
            'is_history_b:False'
        ))
        m_result = g.search(q, **params)
        milestone_counts = {}
        if m_result is not None:
            res_iter = iter(m_result.facets['facet_fields']['_milestone_s'])
            for milestone, count in itertools.izip(*[res_iter] * 2):
                milestone_counts[milestone] = count
        return milestone_counts

    @LazyProperty
    def milestone_counts(self):
        return self.get_milestone_counts()

    @LazyProperty
    def milestone_closed_counts(self):
        return self.get_milestone_counts(fq=[self.closed_query])

    def refresh_counts(self):
        # Refresh bin counts
        self._bin_counts_data = []
        for b in Bin.query.find(dict(app_config_id=self.app_config_id)):
            r = g.search.search_artifact(Ticket, b.terms, rows=0)
            hits = r is not None and r.hits or 0
            self._bin_counts_data.append(dict(summary=b.summary, hits=hits))

    def bin_count(self, name):
        for d in self._bin_counts_data:
            if d['summary'] == name:
                return d
        return dict(summary=name, hits=0)

    def invalidate_bin_counts(self):
        """
        Spin up a task to refresh the bin counts

        """
        refresh_search_counts.post()

    def sortable_custom_fields_shown_in_search(self):
        for field in self.custom_fields:
            ftype = field.get('type')
            if ftype == 'markdown' or not field.get('show_in_search'):
                continue
            if ftype == 'milestone':
                sortable_name = "{0}_dt,{0}_s".format(field['name'])
            else:
                sortable_name = "{0}_s".format(field['name'])
            yield dict(field, sortable_name=sortable_name)

    def can_edit_field(self, field_name):
        if field_name in self.protected_field_names:
            return g.security.has_access(self.app_config, 'edit_protected')
        return g.security.has_access(self.app_config, 'write')


class TicketHistory(Snapshot):

    class __mongometa__:
        name = 'ticket_history'

    def original(self):
        return Ticket.query.get(_id=self.artifact_id)

    def shorthand_id(self):
        return '%s#%s' % (self.original().shorthand_id(), self.version)

    def url(self):
        return self.original().url() + '?version=%d' % self.version

    @property
    def assigned_to(self):
        if self.assigned_to_ids:
            return User.query.find({"_id": {"$in": self.assigned_to_ids}})
        return []

    def index(self, **kw):
        return super(TicketHistory, self).index(
            title_s='Version %d of %s' % (
                self.version, self.original().summary),
            type_s='Ticket Snapshot',
            text_objects=[
                self.data.summary,
            ],
            **kw
        )


class Bin(Artifact):
    class __mongometa__:
        name = 'bin'

    type_s = 'Bin'
    _id = FieldProperty(schema.ObjectId)
    summary = FieldProperty(str, required=True)
    terms = FieldProperty(str, if_missing='')
    sort = FieldProperty(str, if_missing='')

    def url(self):
        base = self.app_config.url() + 'search/search/?'
        params = dict(tool_q=(self.terms or ''))
        if self.sort:
            params['sort'] = self.sort
        return base + urllib.urlencode(params)

    def shorthand_id(self):
        return self.summary

    def index(self, **kw):
        return super(Bin, self).index(
            type_s=self.type_s,
            summary_t=self.summary,
            terms_s=self.terms,
            text_objects=[
                self.summary,
                self.terms,
            ],
            **kw
        )


class Ticket(VersionedArtifact):
    class __mongometa__:
        name = 'ticket'
        history_class = TicketHistory
        session = ticket_orm_session
        indexes = [
            'ticket_num',
            'app_config_id',
            ('app_config_id', 'custom_fields._milestone')]
        unique_indexes = [
            ('app_config_id', 'ticket_num')
        ]

    type_s = 'Ticket'
    _id = FieldProperty(schema.ObjectId)
    created_date = FieldProperty(datetime, if_missing=datetime.utcnow)

    super_id = FieldProperty(schema.ObjectId, if_missing=None)
    sub_ids = FieldProperty([schema.ObjectId], if_missing=[])
    ticket_num = FieldProperty(int, required=True, allow_none=False)
    summary = FieldProperty(str, if_missing='')
    description = FieldProperty(str, if_missing='')
    reported_by_id = ForeignIdProperty(User, if_missing=lambda: c.user._id)
    assigned_to_ids = FieldProperty([schema.ObjectId], if_missing=[])
    milestone = FieldProperty(str, if_missing='')
    status = FieldProperty(str, if_missing='open')
    custom_fields = FieldProperty({str: None})

    reported_by = RelationProperty(User, via='reported_by_id')

    @classmethod
    def new(cls):
        """Create a new ticket, safely (ensuring a unique ticket_num"""
        while True:
            ticket_num = c.app.globals.next_ticket_num()
            ticket = cls(
                app_config_id=c.app.config._id,
                custom_fields=dict(),
                ticket_num=ticket_num)
            try:
                session(ticket).flush(ticket)
                return ticket
            except OperationFailure, err:
                if 'duplicate' in err.args[0]:
                    LOG.warning('Try to create duplicate ticket %s',
                                ticket.url())
                    session(ticket).expunge(ticket)
                    continue
                raise

    def index(self, **kw):
        params = dict(
            title_s='Ticket %s' % self.ticket_num,
            version_i=self.version,
            type_s=self.type_s,
            ticket_num_i=self.ticket_num,
            milestone_s=self._milestone,
            status_s=self.status,
            open_b=self.is_open(),
            snippet_s=self.summary,
            summary_t=self.summary,
            description_t=self.description,
            reported_by_s=self.reported_by_username,
            reported_by_name_s=self.reported_by_name,
            assigned_to_s_mv=self.assigned_to_usernames,
            assigned_to_name_s_mv=self.assigned_to_names,
            last_updated_dt=self.last_updated,
            created_date_dt=self.created_date,
            text_objects=[
                self.ticket_num,
                self.summary,
                self.description,
                self.status,
                self.reported_by_name,
                self.reported_by_username,
                ','.join(self.assigned_to_names),
                ','.join(self.assigned_to_usernames)
            ]
        )
        for k, v in self.custom_fields.iteritems():
            params[k + '_s'] = unicode(v)
        # sort milestones by due date, if available
        for fld in self.globals.milestone_fields:
            if fld.name == 'milestone' or fld.name in self.custom_fields:
                for m in fld.milestones:
                    if m.name == self._milestone:
                        date = m.get('due_date')
                        if date:
                            date = datetime.strptime(date, '%m/%d/%Y')
                        params[fld.name + '_dt'] = date
        params.update(kw)
        return super(Ticket, self).index(**params)

    def get_link_content(self):
        return ' '.join((self.summary or '', self.description))

    @classmethod
    def attachment_class(cls):
        return TicketAttachment

    @classmethod
    def translate_query(cls, q, fields):
        q = super(Ticket, cls).translate_query(q, fields)
        cf = [f.name for f in c.app.globals.custom_fields]
        for f in cf:
            actual = '_%s_s' % f[1:]
            base = f
            q = q.replace(base + ':', actual + ':')
        return q

    @classmethod
    def get_label_info(cls):
        ## this wont work and im not sure why
        #js = """function() {
        #map = function() {
        #    this.labels.forEach( function(l) {
        #        emit( {label:l}, {count:1} );
        #    } );
        #};
        #reduce = function(key, values) {
        #    var count=0;
        #    values.forEach( function(v) {
        #        count += v['count'];
        #    } );
        #    return {count:count};
        #};
        #mr = db.%s.mapReduce(map, reduce, { out : { inline : 1 } } );
        #return db[mr.result].find();
        #}""" % cls.__mongometa__.name
        # so we use the simpler
        js = "db.%s.distinct('labels', {app_config_id:ObjectId(\"%s\")})" % (
            cls.__mongometa__.name,
            c.app.config._id
            )
        output = cls.query.session.impl.db.eval(js)
        return output

    @property
    def _milestone(self):
        milestone = None
        if self.globals:
            for fld in self.globals.milestone_fields:
                if fld.name == '_milestone':
                    return self.custom_fields.get('_milestone', '')
        return milestone

    @property
    def assigned_to(self):
        if self.assigned_to_ids:
            return User.query.find({"_id": {"$in": self.assigned_to_ids}})
        return []

    @property
    def reported_by_username(self):
        if self.reported_by:
            return self.reported_by.username
        return 'nobody'

    @property
    def reported_by_name(self):
        who = self.reported_by
        if who in (None, User.anonymous()):
            return 'nobody'
        return who.get_pref('display_name')

    @property
    def assigned_to_usernames(self):
        if self.assigned_to_ids:
            return [u.username for u in self.assigned_to]
        return ['nobody']

    @property
    def assigned_to_names(self):
        if self.assigned_to_ids:
            names = [u.get_pref('display_name') for u in self.assigned_to
                     if not u in (None, User.anonymous())]

            if names:
                return names
        return ['nobody']

    @property
    def email_address(self):
        domain = '.'.join(reversed(
            self.app.url[1:-1].split('/'))).replace('_', '-')
        return '%s@%s%s' % (self.ticket_num, domain, config.common_suffix)

    @property
    def email_subject(self):
        return '#%s %s' % (self.ticket_num, self.summary)

    @LazyProperty
    def globals(self):
        return Globals.query.get(app_config_id=self.app_config_id)

    def is_open(self):
        return self.status not in self.app.globals.set_of_closed_status_names

    @property
    def open_or_closed(self):
        if self.is_open():
            return 'open'
        return 'closed'

    def _get_private(self):
        return bool(self.acl)

    def _set_private(self, bool_flag):
        if bool_flag:
            role_developer = ProjectRole.by_name('Developer')._id
            role_creator = c.project.project_role(self.reported_by)._id
            self.acl = [
                ACE.allow(role_developer, ALL_PERMISSIONS),
                ACE.allow(role_creator, ALL_PERMISSIONS),
                DENY_ALL]
        else:
            self.acl = []
    private = property(_get_private, _set_private)

    def commit(self):
        VersionedArtifact.commit(self)
        if self.version > 1:
            hist = TicketHistory.query.get(
                artifact_id=self._id,
                version=self.version - 1
            )
            old = hist.data
            changes = [
                'Ticket %s has been modified: %s' % (
                    self.ticket_num, self.summary),
                'Edited By: %s (%s)' % (
                    c.user.get_pref('display_name'), c.user.username)
            ]
            fields = [
                ('Summary', old.summary, self.summary),
                ('Status', old.status, self.status)
            ]
            for key in self.custom_fields:
                fields.append(
                    (key, old.custom_fields.get(key, ''),
                     self.custom_fields[key])
                )
            for title, o, n in fields:
                if o != n:
                    changes.append('%s updated: %r => %r' % (
                        title, o, n))
            if hist.assigned_to_ids != self.assigned_to_ids:
                o = ', '.join(u.username for u in hist.assigned_to)
                changes.append('Owners updated: {} => {}'.format(
                    o, ','.join(self.assigned_to_usernames)))
                new = [uid for uid in self.assigned_to_ids
                       if uid not in hist.assigned_to_ids]
                for u in User.query.find({"_id": {"$in": new}}):
                    self.autosubscribe(user=u)
            if old.description != self.description:
                changes.append('Description updated:')
                changes.append('\n'.join(
                    patience.unified_diff(
                        a=old.description.split('\n'),
                        b=self.description.split('\n'),
                        fromfile='description-old',
                        tofile='description-new')))
            description = '\n'.join(changes)
        else:
            self.autosubscribe()
            for user in self.assigned_to:
                self.autosubscribe(user=user)
            description = self.description
            subject = self.email_subject
            Thread(discussion_id=self.app_config.discussion_id,
                   ref_id=self.index_id())
            Notification.post(
                artifact=self,
                topic='metadata',
                text=description,
                subject=subject)
        Feed.post(self, description)

    def url(self):
        return self.app_config.url() + str(self.ticket_num) + '/'

    @LazyProperty
    def next_ticket(self):
        return self.__class__.query.get(ticket_num=self.ticket_num + 1,
                                        app_config_id=self.app_config_id)

    @LazyProperty
    def prev_ticket(self):
        return self.__class__.query.get(ticket_num=self.ticket_num - 1,
                                        app_config_id=self.app_config_id)

    def get_next_accessible_for(self, user=None):
        if user is None:
            user = c.user
        next_ticket = self.next_ticket
        while next_ticket:
            if g.security.has_access(next_ticket, 'read', user):
                break
            else:
                next_ticket = next_ticket.next_ticket
        return next_ticket

    def get_prev_accessible_for(self, user=None):
        if user is None:
            user = c.user
        prev_ticket = self.prev_ticket
        while prev_ticket:
            if g.security.has_access(prev_ticket, 'read', user):
                break
            else:
                prev_ticket = prev_ticket.prev_ticket
        return prev_ticket

    def shorthand_id(self):
        return '#' + str(self.ticket_num)

    def link_text(self):
        return '%s %s' % (self.shorthand_id(), self.summary or '')

    @property
    def attachments(self):
        return TicketAttachment.query.find({
            'app_config_id': self.app_config_id,
            'artifact_id': self._id,
            'type': 'attachment'
        })

    def set_as_subticket_of(self, new_super_id):
        # For this to be generally useful we would have to check first that
        # new_super_id is not a sub_id (recursively) of self

        if self.super_id == new_super_id:
            return

        if self.super_id is not None:
            old_super = Ticket.query.get(
                _id=self.super_id,
                app_config_id=c.app.config._id
            )
            old_super.sub_ids = [id for id in old_super.sub_ids
                                 if id != self._id]
            old_super.dirty_sums(dirty_self=True)

        self.super_id = new_super_id

        if new_super_id is not None:
            new_super = Ticket.query.get(
                _id=new_super_id,
                app_config_id=c.app.config._id
            )
            if new_super.sub_ids is None:
                new_super.sub_ids = []
            if self._id not in new_super.sub_ids:
                new_super.sub_ids.append(self._id)
            new_super.dirty_sums(dirty_self=True)

    def recalculate_sums(self, super_sums=None):
        """Calculate custom fields of type 'sum' (if any) by recursing into
        subtickets (if any).

        """
        if super_sums is None:
            super_sums = {}
            globals = Globals.query.get(app_config_id=c.app.config._id)
            for k in [cf.name for cf in globals.custom_fields or []
                      if cf['type'] == 'sum']:
                super_sums[k] = float(0)

        # if there are no custom fields of type 'sum', we're done
        if not super_sums:
            return

        # if this ticket has no subtickets, use its field values directly
        if not self.sub_ids:
            for k in super_sums:
                try:
                    v = float(self.custom_fields.get(k, 0))
                except (TypeError, ValueError):
                    v = 0
                super_sums[k] += v

        # else recurse into subtickets
        else:
            sub_sums = {}
            for k in super_sums:
                sub_sums[k] = float(0)
            for id in self.sub_ids:
                subticket = Ticket.query.get(
                    _id=id, app_config_id=c.app.config._id)
                subticket.recalculate_sums(sub_sums)
            for k, v in sub_sums.iteritems():
                self.custom_fields[k] = v
                super_sums[k] += v

    def dirty_sums(self, dirty_self=False):
        """From a changed ticket, climb the superticket chain to call
        recalculate_sums at the root.

        """
        root = self if dirty_self else None
        next_id = self.super_id
        while next_id is not None:
            root = Ticket.query.get(
                _id=next_id, app_config_id=c.app.config._id)
            next_id = root.super_id
        if root is not None:
            root.recalculate_sums()

    def update(self, ticket_form):
        # update is not allowed to change the ticket_num
        ticket_form.pop('ticket_num', None)

        labels = (ticket_form.pop('labels', None) or [])
        if labels == ['']:
            labels = []
        self.labels = labels
        custom_sums = set()
        other_custom_fields = set()
        for cf in self.globals.custom_fields or []:
            if cf['type'] == 'sum':
                custom_sums.add(cf['name'])
            else:
                other_custom_fields.add(cf['name'])
            if cf['type'] == 'boolean' and \
                    'custom_fields.' + cf['name'] not in ticket_form:
                self.custom_fields[cf['name']] = 'False'
        # this has to happen because the milestone custom field has special
        # layout treatment
        if '_milestone' in ticket_form:
            other_custom_fields.add('_milestone')
            milestone = ticket_form.pop('_milestone', None)
            if 'custom_fields' not in ticket_form:
                ticket_form['custom_fields'] = dict()
            ticket_form['custom_fields']['_milestone'] = milestone

        # attachments
        for attachment in ticket_form.pop('new_attachments', []):
            if not hasattr(attachment, 'file'):
                continue
            self.attach(attachment.filename, attachment.file,
                        content_type=attachment.type)

        # other fields
        for k, v in ticket_form.iteritems():
            if k == 'assigned_to':
                self.assigned_to_ids = [
                    u._id for u in v if c.project.user_in_project(user=u)]
            elif k != 'super_id':
                setattr(self, k, v)
        if 'custom_fields' in ticket_form:
            for k, v in ticket_form['custom_fields'].iteritems():
                if k in custom_sums:
                    # sums must be coerced to numeric type
                    try:
                        self.custom_fields[k] = float(v)
                    except (TypeError, ValueError):
                        self.custom_fields[k] = 0
                elif k in other_custom_fields:
                    # strings are good enough for any other custom fields
                    self.custom_fields[k] = v
        if 'markdown_custom_fields' in ticket_form:
            for k, v in ticket_form['markdown_custom_fields'].items():
                if k in other_custom_fields:
                    self.custom_fields[k] = v
        self.commit()
        # flush so we can participate in a subticket search (if any)
        session(self.__class__).flush()
        super_id = ticket_form.get('super_id')
        if super_id:
            self.set_as_subticket_of(bson.ObjectId(super_id))
        self.globals.invalidate_bin_counts()

    def __json__(self):
        return dict(
            _id=str(self._id),
            created_date=self.created_date,
            mod_date=self.mod_date,
            super_id=str(self.super_id),
            sub_ids=[str(id) for id in self.sub_ids],
            ticket_num=self.ticket_num,
            summary=self.summary,
            description=self.description,
            reported_by=self.reported_by_username,
            assigned_to=self.assigned_to_usernames,
            reported_by_id=self.reported_by_id and str(self.reported_by_id)
                           or None,
            assigned_to_ids=map(str, self.assigned_to_ids),
            milestone=self.milestone,
            status=self.status,
            custom_fields=self.custom_fields)

    @classmethod
    def paged_query(cls, q, mongo=False, **kw):
        """
        Query tickets, default search with SOLR but allow Mongo queries
        """
        if mongo:
            return cls.paged_mongo_query(q, **kw)
        return cls.paged_solr_query(q, **kw)

    @classmethod
    def paged_mongo_query(cls, query, limit=None, page=0, sort=None,
                          columns=None, **kw):
        """Query tickets, sorting and paginating the result."""
        limit, page, start = g.handle_paging(limit, page, default=25)
        q = cls.query.find(dict(query, app_config_id=c.app.config._id))
        q = q.sort('ticket_num')
        if sort and sort != 'None':
            for s in sort.split(','):
                field, direction = s.split()
                if field.startswith('_'):
                    field = 'custom_fields.' + field
                direction = dict(
                    asc=pymongo.ASCENDING,
                    desc=pymongo.DESCENDING)[direction]
                q = q.sort(field, direction)
        q = q.skip(start)
        q = q.limit(limit)
        tickets = []
        count = q.count()
        for t in q:
            if g.security.has_access(t, 'read'):
                tickets.append(t)
            else:
                count -= 1
        sortable_custom_fields = \
            c.app.globals.sortable_custom_fields_shown_in_search()
        if not columns:
            columns = [
                dict(name='ticket_num', sort_name='ticket_num',
                     label='Ticket Number', active=True),
                dict(name='summary', sort_name='summary',
                     label='Summary', active=True),
                dict(name='status', sort_name='status',
                     label='Status', active=True),
                dict(name='assigned_to', sort_name='assigned_to_name_s',
                     label=c.app.globals.assigned_to_label, active=True),
                dict(name='last_updated', sort_name='last_updated',
                     label='Last Updated', active=True)
            ]
            for field in sortable_custom_fields:
                columns.append(
                    dict(name=field['name'], sort_name=field['name'],
                         label=field['label'], active=True))
        return dict(
            tickets=tickets,
            sortable_custom_fields=sortable_custom_fields,
            columns=columns,
            count=count,
            q=json.dumps(query),
            limit=limit,
            page=page,
            sort=sort,
            **kw)

    @classmethod
    def paged_solr_query(cls, q, limit=None, page=0, sort=None,
                         columns=None, **kw):
        """Query tickets, sorting and paginating the result.

        We do the sorting and skipping right in SOLR, before we ever ask
        Mongo for the actual tickets.  Other keywords for
        search_artifact (e.g., history) or for SOLR are accepted through
        kw.  The output is intended to be used directly in templates,
        e.g., exposed controller methods can just:

            return paged_query(q, ...)

        If you want all the results at once instead of paged you have
        these options:
          - don't call this routine, search directly in mongo
          - call this routine with a very high limit and TEST that
            count<=limit in the result
        limit=-1 is NOT recognized as 'all'.  500 is a reasonable limit.
        """
        limit, page, start = g.handle_paging(limit, page, default=25)
        count = 0
        tickets = []
        refined_sort = sort if sort else 'ticket_num_i desc'
        if 'ticket_num_i' not in refined_sort:
            refined_sort += ',ticket_num_i asc'
        try:
            if q:
                matches = g.search.search_artifact(
                    cls, q, rows=limit, sort=refined_sort, start=start,
                    fl='ticket_num_i', **kw)
            else:
                matches = None
            solr_error = None
        except ValueError, e:
            solr_error = e.args[0]
            matches = []
        if matches:
            count = matches.hits
            # ticket_numbers is in sorted order
            ticket_numbers = [match['ticket_num_i'] for match in matches.docs]
            # but query, unfortunately, returns results in arbitrary order
            query = cls.query.find({'app_config_id': c.app.config._id,
                                    'ticket_num': {'$in': ticket_numbers}})
            # so stick all the results in a dictionary...
            ticket_for_num = {}
            for t in query:
                ticket_for_num[t.ticket_num] = t
            # and pull them out in the order given by ticket_numbers
            tickets = []
            for tn in ticket_numbers:
                if tn in ticket_for_num:
                    if g.security.has_access(ticket_for_num[tn], 'read'):
                        tickets.append(ticket_for_num[tn])
                    else:
                        count -= 1
        sortable_custom_fields = \
            c.app.globals.sortable_custom_fields_shown_in_search()
        if not columns:
            columns = [
                {'name': 'ticket_num', 'sort_name': 'ticket_num_i',
                 'label': 'Ticket Number', 'active': True},
                {'name': 'summary', 'sort_name': 'snippet_s',
                 'label': 'Summary', 'active': True},
                {'name': 'status', 'sort_name': 'status_s', 'label': 'Status',
                 'active': True},
                {'name': 'assigned_to', 'sort_name': 'assigned_to_name_s',
                 'label': c.app.globals.assigned_to_label, 'active': True},
                {'name': 'last_updated', 'sort_name': 'last_updated_dt',
                 'label': 'Last Updated', 'active': True}
            ]
            for field in sortable_custom_fields:
                columns.append(dict(name=field['name'],
                                    sort_name=field['sortable_name'],
                                    label=field['label'], active=True))
        c.csv_url = '{}search/csv?{}'.format(c.app.url,
                                           urllib.urlencode([
                                               ('q', q), ('sort', sort)
                                           ]))
        c.aggregate_url = '{}search/aggregate?{}'.format(c.app.url,
                                                        urllib.urlencode([
                                                            ('q', q)
                                                        ]))
        return dict(
            tickets=tickets,
            sortable_custom_fields=sortable_custom_fields,
            columns=columns,
            count=count,
            q=q,
            limit=limit,
            page=page,
            sort=sort,
            solr_error=solr_error,
            **kw)


class TicketAttachment(BaseAttachment):
    ArtifactType = Ticket

    class __mongometa__:
        polymorphic_identity = 'TicketAttachment'

    attachment_type = FieldProperty(str, if_missing='TicketAttachment')


