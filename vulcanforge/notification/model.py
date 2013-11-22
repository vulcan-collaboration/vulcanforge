"""Manage notifications and subscriptions

When an artifact is modified:
- Notification generated by tool app
- Search is made for subscriptions matching the notification
- Notification is added to each matching subscriptions' queue

Periodically:
- For each subscriptions with notifications and direct delivery:
   - For each notification, enqueue as a separate email message
   - Clear subscription's notification list
- For each subscription with notifications and delivery due:
   - Enqueue one email message with all notifications
   - Clear subscription's notification list

Notifications are also available for use in feeds
"""
import cgi

import logging
from datetime import datetime, timedelta
from collections import defaultdict

from bson import ObjectId
import pymongo
from ming import schema as S
from ming.odm import (
    FieldProperty,
    ForeignIdProperty,
    RelationProperty,
    session
)
from ming.odm.declarative import MappedClass
from ming.utils import LazyProperty
from paste.deploy.converters import asbool
from webhelpers import feedgenerator as FG
from webhelpers.text import truncate
from pylons import tmpl_context as c, app_globals as g
from tg import config, jsonify
import jinja2

from vulcanforge.common.model.index import SOLRIndexed
from vulcanforge.common.model.session import main_orm_session
from vulcanforge.common.util import nonce
from vulcanforge.common.helpers import absurl
from vulcanforge.artifact.model import ArtifactReference
from vulcanforge.auth.model import User

from .util import gen_message_id
from .tasks import notify, sendmail


LOG = logging.getLogger(__name__)

MAILBOX_QUIESCENT = None  # Re-enable with [#1384]: timedelta(minutes=10)


class Notification(SOLRIndexed):
    class __mongometa__:
        name = 'notification'
        indexes = [
            ('neighborhood_id', 'tool_name', 'pubdate'),
            ('app_config_id', 'ref_id',),
        ]

    type_s = "Notification"

    _id = FieldProperty(str, if_missing=gen_message_id)

    # Classify notifications
    neighborhood_id = ForeignIdProperty(
        'Neighborhood',
        if_missing=lambda: c.project.neighborhood._id
    )
    project_id = ForeignIdProperty('Project', if_missing=lambda: c.project._id)
    project = RelationProperty('Project', via='project_id')
    app_config_id = ForeignIdProperty(
        'AppConfig',
        if_missing=lambda: c.app.config._id
    )
    app_config = RelationProperty('AppConfig', via='app_config_id')
    tool_name = FieldProperty(str, if_missing=lambda: c.app.config.tool_name)
    ref_id = ForeignIdProperty('ArtifactReference')
    topic = FieldProperty(str)
    unique_id = FieldProperty(str, if_missing=lambda: nonce(40))

    # Notification Content
    in_reply_to = FieldProperty(str)
    from_address = FieldProperty(str)
    reply_to_address = FieldProperty(str)
    subject = FieldProperty(str)
    text = FieldProperty(str)
    link = FieldProperty(str)
    author_id = ForeignIdProperty('User')
    feed_meta = FieldProperty(S.Deprecated)
    artifact_reference = FieldProperty(S.Deprecated)
    pubdate = FieldProperty(datetime, if_missing=datetime.utcnow)

    view = jinja2.Environment(
        loader=jinja2.PackageLoader('vulcanforge.notification', 'templates'))

    def __json__(self):
        data = {
            '_id': str(self._id),
            'neighborhood_id': str(self.neighborhood_id),
            'project_id': str(self.project_id),
            'app_config_id': str(self.app_config_id),
            'tool_name': self.tool_name,
            'ref_id': str(self.ref_id),
            'topic': self.topic,
            'unique_id': str(self.unique_id),
            'in_reply_to': self.in_reply_to,
            'from_address': self.from_address,
            'reply_to_address': self.reply_to_address,
            'subject': self.subject,
            'text': self.text,
            'link': self.link,
            'author_id': str(self.author_id),
            'pubdate': self.pubdate.isoformat(),
        }
        project = self.project
        app_config = self.app_config
        data.update({
            '_rendered': g.markdown.convert(self.text),
            'author': self.author(),
            'project': {
                '_id': str(project._id),
                'name': project.name,
                'url': project.url(),
                'icon_url': project.icon_url,
            },
        })
        if app_config is not None:
            try:
                ac_icon_url = app_config.icon_url(24)
            except TypeError:
                ac_icon_url = None
            data['app_config'] = {
                '_id': str(app_config._id),
                'name': app_config.options.mount_label,
                'url': app_config.url(),
                'icon_url': ac_icon_url,
            }
        return data

    @LazyProperty
    def ref(self):
        if self.ref_id:
            return ArtifactReference.query.get(_id=self.ref_id)

    def index(self, **kwargs):
        # skip if the referred to artifact does not exist
        if self.ref_id is not None \
            and self.ref is None \
            or self.ref.artifact is None:
            return None
        json_dict = self.__json__()
        return {
            'id': self.index_id(),
            'notification_id_s': str(self._id),
            'url_s': self.link,
            'type_s': self.type_s,
            'pubdate_dt': self.pubdate,
            'neighborhood_id_s': str(self.neighborhood_id),
            'author_id_s': str(self.author_id),
            'project_id_s': str(self.project_id),
            'app_config_id_s': str(self.app_config_id),
            'ref_id_s': str(self.ref_id),
            'json_s': jsonify.encode(json_dict),
            'read_roles': self.get_read_roles(),
            'is_real_b': self.project.is_real(),
        }

    def get_read_roles(self):
        target = self.get_artifact()
        if target is None:
            target = self.app_config
        if target is None:
            target = self.project
        return target.get_read_roles()

    @property
    def read_roles(self):
        return self.get_read_roles()

    def author(self):
        return User.query.get(_id=self.author_id) \
            if self.author_id is not None \
            else None

    def get_artifact(self):
        if self.ref_id and self.ref:
            return self.ref.artifact

    def has_access(self, access_type):
        artifact = self.get_artifact()
        if artifact is not None:
            return g.security.has_access(artifact, access_type)
        app_config = self.app_config()
        return app_config.has_access(access_type)

    @classmethod
    def post(cls, artifact, topic, **kw):
        """Create a notification and send the notify message"""
        n = cls._make_notification(artifact, topic, **kw)
        if n:
            session(n).flush(n)
            notify.post(n._id, artifact.index_id(), topic)
        return n

    @classmethod
    def post_user(cls, user, artifact, topic, **kw):
        """
        Create a notification and deliver directly to a user's flash mailbox

        """
        try:
            mbox = Mailbox(user_id=user._id, is_flash=True,
                           project_id=None,
                           app_config_id=None)
            session(mbox).flush(mbox)
        except pymongo.errors.DuplicateKeyError:
            session(mbox).expunge(mbox)
            mbox = Mailbox.query.get(user_id=user._id, is_flash=True)
        n = cls._make_notification(artifact, topic, **kw)
        if n:
            mbox.queue.append(n._id)
        return n

    @classmethod
    def _make_notification(cls, artifact, topic, **kwargs):
        safe_notifications = asbool(config.get('safe_notifications', 'false'))
        safe_text = kwargs.pop('safe_text', None)
        if getattr(c, 'project', None) is None:
            c.project = artifact.project
        if getattr(c, 'app', None) is None:
            c.app = artifact.app
        idx = artifact.index() or {}
        shortname = c.project.shortname
        if shortname == '--init--':
            shortname = c.project.neighborhood.name
        subject_prefix = u'[%s:%s] ' % (
            shortname, c.app.config.options.mount_point)
        if topic == 'message':
            post = kwargs.pop('post')
            safe_text = getattr(post, 'safe_text', None)
            subject = cgi.escape(post.subject or '')
            if post.parent_id and not subject.lower().startswith('re:'):
                subject = u'Re: '+subject
            author = post.author()
            if safe_notifications:
                post_text = safe_text or "commented or modified"
            else:
                post_text = post.text
            if author is not None:
                text = u"{}: {}".format(author.display_name, post_text)
            else:
                text = post_text
            d = dict(
                _id=post._id,
                from_address=str(author._id),
                # TODO: forgemail reference follows
                reply_to_address=u'"%s" <%s>' % (
                    subject_prefix, getattr(artifact, 'email_address',
                                            'noreply@in.vulcanforge.org')),
                subject=subject_prefix+subject,
                text=text,
                in_reply_to=post.parent_id,
                author_id=author._id,
                pubdate=datetime.utcnow())
        else:
            subject = kwargs.pop('subject', u'%s modified by %s' % (
                idx.get('title_s'), c.user.get_pref('display_name')))
            reply_to = u'"%s" <%s>' % (idx.get('title_s', subject),
                                       artifact.email_address)
            text = kwargs.pop('text', subject)
            if safe_notifications:
                text = safe_text or ""
            d = dict(
                from_address=reply_to,
                reply_to_address=reply_to,
                subject=subject_prefix + cgi.escape(subject),
                text=text,
                author_id=c.user._id,
                pubdate=datetime.utcnow())
            email_address = c.user.get_email_address()
            if email_address:
                d['from_address'] = u'"%s" <%s>' % (
                    c.user.get_pref('display_name'),
                    email_address)
        if not d.get('text'):
            d['text'] = u''

        assert d['reply_to_address'] is not None
        if c.project.notifications_disabled:
            LOG.info(
                'Notifications disabled for project %s, not sending %s(%r)',
                c.project.shortname, topic, artifact
            )
            return None
        link_url = kwargs.pop('link', artifact.url())
        n = cls(ref_id=artifact.index_id(), topic=topic, link=link_url, **d)
        return n

    @classmethod
    def feed(cls, q, feed_type, title, link, description,
             since=None, until=None, offset=None, limit=None):
        """Produces webhelper.feedgenerator Feed"""
        d = dict(
            title=title,
            link=absurl(link),
            description=description,
            language=u'en'
        )
        if feed_type == 'atom':
            feed = FG.Atom1Feed(**d)
        elif feed_type == 'rss':
            feed = FG.Rss201rev2Feed(**d)
        query = defaultdict(dict)
        query.update(q)
        if since is not None:
            query['pubdate']['$gte'] = since
        if until is not None:
            query['pubdate']['$lte'] = until
        cur = cls.query.find(query)
        cur.sort('pubdate', pymongo.DESCENDING)
        cur.limit(limit or 10)
        cur.skip(offset or 0)
        for r in cur:
            feed.add_item(
                title=r.subject,
                link=absurl(r.link.encode('utf-8')),
                pubdate=r.pubdate,
                description=r.text,
                unique_id=r.unique_id,
                author_name=r.author().display_name,
                author_link=absurl(r.author().url()))
        return feed

    def get_context(self, **kwargs):
        safe_notifications = asbool(config.get('safe_notifications', 'false'))
        context = {
            'notification': self,
            'prefix': config.get('forgemail.url', 'https://vulcanforge.org'),
            'safe_notifications': safe_notifications,
            'forge_name': config.get('forge_name', 'Forge')
        }
        context.update(kwargs)
        return context

    def footer(self):
        text = ''
        artifact = self.get_artifact()
        if artifact is not None:
            try:
                template = self.view.get_template(
                    'mail/{}.txt'.format(artifact.type_s))
                text += template.render(self.get_context(artifact=artifact))
            except Exception, e:
                LOG.debug('Error rendering notification template '
                          '%s: %s' % (artifact.type_s, e))
        template = self.view.get_template('mail/footer.txt')
        text += template.render(self.get_context())
        return text

    def send_direct(self, user_id):
        text = '\n'.join([
            '# '+self.subject,
            self.text,
            self.footer(),
        ])
        from_address = '"{} Notification" <{}>'.format(
            config.get('forge_name', 'Forge'),
            g.forgemail_return_path)
        sendmail.post(
            destinations=[str(user_id)],
            fromaddr=from_address,
            reply_to=self.reply_to_address,
            subject=self.subject,
            message_id=self._id,
            in_reply_to=self.in_reply_to,
            text=text)

    @classmethod
    def send_digest(cls, user_id, from_address, notifications,
                    reply_to_address=None):
        if not notifications:
            return
        subject = '{} activity digest'.format(
            config.get('forge_name', 'Forge'))
        text = ['# '+subject]
        if reply_to_address is None:
            reply_to_address = from_address
        for n in notifications:
            t_from_address = n.from_address
            try:
                user = User.by_id(ObjectId(n.from_address))
                t_from_address = "{} <{}>".format(
                    user.get_pref('display_name'),
                    user.get_email_address(),
                )
            except Exception:
                LOG.debug("could not render user's email and name for"
                          " id %r", n.from_address)
            text.append('\n'.join([
                '## %s' % (n.subject or '(no subject)'),
                '',
                '- From: %s' % t_from_address,
                '- Message-ID: %s' % n._id,
                '',
                n.text or '-no text-',
                n.footer(),
            ]))
        text = '\n\n---\n\n---\n\n'.join(text)
        sendmail.post(
            destinations=[str(user_id)],
            fromaddr=from_address,
            reply_to=reply_to_address,
            subject=subject,
            message_id=gen_message_id(),
            text=text)

    @classmethod
    def send_summary(cls, user_id, from_address, notifications):
        if not notifications:
            return
        subject = '{} activity summary'.format(
            config.get('forge_name', 'Forge'))
        text = [subject]
        for n in notifications:
            text.append('From: %s' % n.from_address)
            text.append('Subject: %s' % (n.subject or '(no subject)'))
            text.append('Message-ID: %s' % n._id)
            text.append('')
            text.append(truncate(n.text or '-no text-', 128))
            text.append(n.footer())
        text = '\n'.join(text)
        sendmail.post(
            destinations=[str(user_id)],
            fromaddr=from_address,
            reply_to=from_address,
            subject=subject,
            message_id=gen_message_id(),
            text=text)


class Mailbox(MappedClass):
    class __mongometa__:
        session = main_orm_session
        name = 'mailbox'
        unique_indexes = [
            ('user_id', 'project_id', 'app_config_id',
             'artifact_index_id', 'topic', 'is_flash'),
        ]
        indexes = [('project_id', 'artifact_index_id')]

    _id = FieldProperty(S.ObjectId)
    user_id = ForeignIdProperty(User, if_missing=lambda: c.user._id)
    user = RelationProperty(User, via="user_id")
    project_id = ForeignIdProperty('Project', if_missing=lambda: c.project._id)
    app_config_id = ForeignIdProperty(
        'AppConfig',
        if_missing=lambda: c.app.config._id
    )

    # Subscription filters
    artifact_title = FieldProperty(str)
    artifact_url = FieldProperty(str)
    artifact_index_id = FieldProperty(str)
    topic = FieldProperty(str)

    # Subscription type
    #   follow: include in dashboard
    follow = FieldProperty(bool, if_missing=True)
    is_flash = FieldProperty(bool, if_missing=False)
    type = FieldProperty(
        S.OneOf('direct', 'digest', 'summary', 'flash', 'none')
    )
    frequency = FieldProperty(dict(
        n=int,
        unit=S.OneOf('hour', 'day', 'week', 'month')
    ))
    next_scheduled = FieldProperty(datetime, if_missing=datetime.utcnow)

    # Actual notification IDs
    last_modified = FieldProperty(datetime, if_missing=datetime(2000, 1, 1))
    queue = FieldProperty([str])

    project = RelationProperty('Project')
    app_config = RelationProperty('AppConfig')

    def __json__(self):
        return {
            '_id': str(self._id),
            'project_id': str(self.project_id),
            'app_config_id': str(self.app_config_id),
            'artifact_title': self.artifact_title,
            'artifact_url': self.artifact_url,
            'artifact_index_id': self.artifact_index_id,
            'topic': self.topic,
            'follow': self.follow,
            'is_flash': self.is_flash,
            'type': self.type,
            'frequency': self.frequency,
            'next_scheduled': self.next_scheduled,
            'last_modified': self.last_modified,
        }

    def _get_notification_query_params(self):
        params = {}
        if self.app_config_id is not None:
            params['app_config_id'] = self.app_config_id
        if self.artifact_index_id is not None:
            params['ref_id'] = self.artifact_index_id
        return params

    @property
    def type_label(self):
        label = self.type
        if self.type == 'digest' or self.type == 'summary':
            label += ' {n} {unit}'.format(self.frequency)
        return label

    def get_is_tool_subscription(self):
        return self.artifact_index_id is None

    @classmethod
    def subscribe(cls, user_id=None, project_id=None, app_config_id=None,
                  artifact=None, topic=None, type='direct', n=1, unit='day'):
        if user_id is None:
            user_id = c.user._id
        if project_id is None:
            project_id = c.project._id
        if app_config_id is None:
            app_config_id = c.app.config._id
        tool_already_subscribed = cls.query.get(
            user_id=user_id,
            project_id=project_id,
            app_config_id=app_config_id,
            artifact_index_id=None)
        if tool_already_subscribed:
            LOG.debug('Tried to subscribe to artifact %s, '
                      'while there is a tool subscription',
                      artifact and artifact.index_id())
            return
        if artifact is None:
            artifact_title = 'All artifacts'
            artifact_url = None
            artifact_index_id = None
        else:
            i = artifact.index()
            artifact_title = i['title_s']
            artifact_url = artifact.url()
            artifact_index_id = i['id']
            artifact_already_subscribed = cls.query.get(
                user_id=user_id,
                project_id=project_id,
                app_config_id=app_config_id,
                artifact_index_id=artifact_index_id
            )
            if artifact_already_subscribed:
                return
        d = dict(
            user_id=user_id,
            project_id=project_id,
            app_config_id=app_config_id,
            artifact_index_id=artifact_index_id,
            topic=topic
        )
        sess = session(cls)
        try:
            mbox = cls(
                type=type, frequency=dict(n=n, unit=unit),
                artifact_title=artifact_title,
                artifact_url=artifact_url,
                **d)
            sess.flush(mbox)
        except pymongo.errors.DuplicateKeyError:
            sess.expunge(mbox)
            mbox = cls.query.get(**d)
            mbox.artifact_title = artifact_title
            mbox.artifact_url = artifact_url
            mbox.type = type
            mbox.frequency.n = n
            mbox.frequency.unit = unit
            sess.flush(mbox)
        if not artifact_index_id:
            # Unsubscribe from individual artifacts when subscribing to tool
            others = cls.query.find(dict(
                user_id=user_id,
                project_id=project_id,
                app_config_id=app_config_id
            ))
            for other_mbox in others:
                if other_mbox is not mbox:
                    other_mbox.delete()

    @classmethod
    def unsubscribe(cls, user_id=None, project_id=None, app_config_id=None,
                    artifact_index_id=None, topic=None):
        if user_id is None:
            user_id = c.user._id
        if project_id is None:
            project_id = c.project._id
        if app_config_id is None:
            app_config_id = c.app.config._id
        cls.query.remove(dict(
            user_id=user_id,
            project_id=project_id,
            app_config_id=app_config_id,
            artifact_index_id=artifact_index_id,
            topic=topic))

    @classmethod
    def subscribed(
            cls, user_id=None, project_id=None, app_config_id=None,
            artifact=None, topic=None):
        if user_id is None:
            user_id = c.user._id
        if project_id is None:
            project_id = c.project._id
        if app_config_id is None:
            if hasattr(c.app, 'app_config'):
                app_config_id = c.app.app_config._id
            else:
                app_config_id = c.app.config._id
        if artifact is None:
            artifact_index_id = None
        else:
            i = artifact.index()
            artifact_index_id = i['id']
        query_params = {
            'user_id': user_id,
            'project_id': project_id,
            'app_config_id': app_config_id,
            'artifact_index_id': {
                '$in': [artifact_index_id, None],
            }
        }
        return cls.query.find(query_params).count() != 0

    @classmethod
    def get_subscription(cls, user_id=None, project_id=None,
                         app_config_id=None, artifact=None, topic=None):
        if user_id is None:
            user_id = c.user._id
        if project_id is None:
            project_id = c.project._id
        if app_config_id is None:
            if hasattr(c.app, 'app_config'):
                app_config_id = c.app.app_config._id
            else:
                app_config_id = c.app.config._id
        if artifact is None:
            artifact_index_id = None
        else:
            i = artifact.index()
            artifact_index_id = i['id']
        query_params = {
            'user_id': user_id,
            'project_id': project_id,
            'app_config_id': app_config_id,
            'artifact_index_id': {
                '$in': [artifact_index_id, None],
            }
        }
        return cls.query.get(**query_params)

    @classmethod
    def deliver(cls, nid, artifact_index_id, topic):
        """Called in the notification message handler to deliver notification
        IDs to the appropriate  mailboxes.  Atomically appends the nids
        to the appropriate mailboxes.

        """
        d = {
            'project_id': c.project._id,
            'app_config_id': c.app.config._id,
            'artifact_index_id': {'$in': [None, artifact_index_id]},
            'topic': {'$in': [None, topic]}
        }
        for mbox in cls.query.find(d):
            if mbox.user and mbox.user.active():
                mbox.query.update(
                    {'$push': dict(queue=nid),
                     '$set': dict(last_modified=datetime.utcnow())})
                # Make sure the mbox doesn't stick around to be flush()ed
                session(mbox).expunge(mbox)

    @classmethod
    def fire_ready(cls):
        """Fires all direct subscriptions with notifications as well as
        all summary & digest subscriptions with notifications that are ready

        """
        now = datetime.utcnow()
        # Queries to find all matching subscription objects
        q_direct = dict(
            type='direct',
            queue={'$ne': []})
        if MAILBOX_QUIESCENT:
            q_direct['last_modified'] = {'$lt': now-MAILBOX_QUIESCENT}
        q_digest = dict(
            type={'$in': ['digest', 'summary']},
            next_scheduled={'$lt': now})
        for mbox in cls.query.find(q_direct):
            mbox = cls.query.find_and_modify(
                query=dict(_id=mbox._id),
                update={'$set': dict(queue=[])},
                new=False)
            mbox.fire(now)
        for mbox in cls.query.find(q_digest):
            next_scheduled = now
            if mbox.frequency.unit == 'hour':
                next_scheduled += timedelta(hours=mbox.frequency.n)
            elif mbox.frequency.unit == 'day':
                next_scheduled += timedelta(days=mbox.frequency.n)
            elif mbox.frequency.unit == 'week':
                next_scheduled += timedelta(days=7 * mbox.frequency.n)
            elif mbox.frequency.unit == 'month':
                next_scheduled += timedelta(days=30 * mbox.frequency.n)
            mbox = cls.query.find_and_modify(
                query=dict(_id=mbox._id),
                update={'$set': dict(
                    next_scheduled=next_scheduled,
                    queue=[])},
                new=False)
            mbox.fire(now)

    def fire(self, now):
        # break out early if notifications are disabled for this project
        if self.project.disable_notification_emails:
            return
        notifications = Notification.query.find(dict(_id={'$in': self.queue}))
        notifications = notifications.all()
        if len(notifications) != len(self.queue):
            LOG.warn("Expected notifications not found for %s:" % self.queue)
        if self.type == 'direct':
            ngroups = defaultdict(list)
            for n in notifications:
                if n.topic == 'message':
                    n.send_direct(self.user_id)
                    # Messages must be sent individually so they can be replied
                    # to individually
                else:
                    key = (
                        n.subject,
                        n.from_address,
                        n.reply_to_address,
                        n.author_id
                    )
                    ngroups[key].append(n)
                # Accumulate messages from same address with same subject
            for (subject, from_address, reply_to_address, author_id), ns \
                in ngroups.iteritems():
                if len(ns) == 1:
                    n.send_direct(self.user_id)
                else:
                    Notification.send_digest(
                        self.user_id,
                        from_address,
                        ns,
                        reply_to_address
                    )
        else:
            from_address = '"{} Notification" <{}>'.format(
                config.get('forge_name', 'Forge'),
                g.forgemail_return_path)
            if self.type == 'digest':
                Notification.send_digest(
                    self.user_id, from_address, notifications)
            elif self.type == 'summary':
                Notification.send_summary(
                    self.user_id, from_address, notifications)
