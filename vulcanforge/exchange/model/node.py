import logging

from pylons import app_globals as g, tmpl_context as c
import pymongo
from ming import schema
from ming.odm import FieldProperty
from ming.utils import LazyProperty

from vulcanforge.artifact.model import VersionedArtifact, Snapshot
from vulcanforge.auth.model import User
from vulcanforge.exchange.schema import ExchangeACL
from vulcanforge.exchange.model.session import (
    exchange_node_session,
    exchange_orm_session
)
from vulcanforge.notification.model import Notification
from vulcanforge.project.model import Project

LOG = logging.getLogger(__name__)


class NodeHistory(Snapshot):
    class __mongometa__:
        name = 'node_history'
        session = exchange_orm_session

    change_log = FieldProperty(str, if_missing=None)

    def original(self):
        return ExchangeNode.query.get(_id=self.artifact_id)


class ExchangeNode(VersionedArtifact):
    """Shared item in the exchange that points to a forge artifact."""

    class __mongometa__:
        name = 'exchange_node'
        session = exchange_node_session
        history_class = NodeHistory
        indexes = [
            ('forge_artifact_id', 'deleted', 'mod_date'),
            ('exchange_uri', 'mod_date'),
            ('forge_artifact_id', 'exchange_uri', 'artifact_name')
        ]
        polymorphic_on = 'kind'
        polymorphic_identity = 'node'

    type_s = 'Exchange Node'

    kind = FieldProperty(str, if_missing='node')
    acl = FieldProperty(ExchangeACL)
    title = FieldProperty(str)  # defaults to forge_artifact_title
    exchange_uri = FieldProperty(str)  # shortname that identifies the xcng
    exchange_mount_point = FieldProperty(str)  # specific to xcng artifact type
    forge_artifact_id = FieldProperty(schema.ObjectId)
    forge_artifact_version = FieldProperty(schema.Int, if_missing=None)
    forge_artifact_name = FieldProperty(str)
    forge_artifact_title = FieldProperty(str)
    tool_name = FieldProperty(str)
    index_fields = FieldProperty(None, if_missing={})
    share_scope = FieldProperty(str, if_missing='public')
    last_log = FieldProperty(str, if_missing=None)
    revision = FieldProperty(str)  # defaults to str(version)
    deleted = FieldProperty(bool, if_missing=False)

    @classmethod
    def find_from_artifact(cls, artifact, deleted=False, **query):
        query.update({
            "forge_artifact_id": artifact._id,
            "deleted": deleted
        })
        return cls.query.find(query).sort('mod_date', pymongo.DESCENDING)

    @classmethod
    def new_from_artifact(cls, artifact, **kwargs):
        params = {
            "forge_artifact_id": artifact._id,
        }
        if getattr(c, "exchange", None):
            params["exchange_uri"] = c.exchange.config["uri"]
        if getattr(c, "artifact_config", None):
            mount_point = c.artifact_config['tool_name'] + '_' + \
                c.artifact_config['artifact_name']
            params.update({
                "forge_artifact_name": c.artifact_config["artifact_name"],
                "tool_name": c.artifact_config["tool_name"],
                "exchange_mount_point": mount_point
            })
        params.update(kwargs)
        node = cls(**params)
        node.update_from_artifact(artifact)
        node.notify_create()
        return node

    def update_from_artifact(self, artifact, **kwargs):
        params = {}
        if hasattr(artifact, "version"):
            params["forge_artifact_version"] = artifact.version
        params["forge_artifact_title"] = artifact.title_s
        params.update(kwargs)
        for name, val in params.items():
            setattr(self, name, val)
        self.notify_update()

    def notify_create(self):
        subject = '{} shared {}'.format(c.user.username, self.title)
        template = g.jinja2_env.get_template('exchange/notify/upsert.txt')
        text = template.render({
            "subject": subject,
            "exchange_name": self.exchange.config['name'],
            "title": self.title,
            "url": g.url(self.url()),
            "exchange_url": g.url(self.exchange.url())
        })
        Notification.post(self, "exchange", text=text, subject=subject)

    def notify_update(self):
        subject = '{} updated shared resource {}'.format(
            c.user.username, self.title)
        template = g.jinja2_env.get_template('exchange/notify/upsert.txt')
        text = template.render({
            "subject": subject,
            "exchange_name": self.exchange.config['name'],
            "title": self.title,
            "url": g.url(self.url()),
            "exchange_url": g.url(self.exchange.url())
        })
        Notification.post(self, "exchange", text=text, subject=subject)

    def notify_delete(self):
        subject = '{} unshared {}'.format(c.user.username, self.title)
        template = g.jinja2_env.get_template('exchange/notify/delete.txt')
        text = template.render({
            "subject": subject,
            "exchange_name": self.exchange.config['name'],
            "exchange_url": g.url(self.exchange.url())
        })
        Notification.post(self, "exchange", text=text, subject=subject)

    def get_read_roles(self):
        read_roles = super(ExchangeNode, self).get_read_roles()
        # add read roles for projects with which artifact is shared
        for ace in self.acl:
            if hasattr(ace, 'member_project_id'):
                mp = Project.by_id(ace.member_project_id)
                if mp:
                    for role in mp.get_expanded_read_roles():
                        if role.name == 'Member':
                            role_id = str(role._id)
                            if role_id not in read_roles:
                                read_roles.append(role_id)
                            break
        return read_roles

    @property
    def url_prefix(self):
        return '/exchange/{}/{}/'.format(
            self.exchange_uri, self.exchange_mount_point)

    @property
    def display_name(self):
        name = self.title
        if self.deleted:
            name += ' [Redacted]'
        return name

    def url(self):
        return self.url_prefix + 'view?node_id={}'.format(self._id)

    def history_url(self):
        return self.url_prefix + 'view/history?node_id={}'.format(self._id)

    def edit_url(self):
        postfix = 'publish?artifact_id={}&cur_node_id={}'.format(
            self.forge_artifact_id,
            self._id)
        return self.url_prefix + postfix

    def delete_url(self):
        return self.url_prefix + 'publish/delete?node_id={}'.format(self._id)

    def import_url(self):
        return self.url_prefix + 'importer?node_id={}'.format(self._id)

    def commit(self, change_log=None):
        if change_log:
            self.last_log = change_log
        node_hist = super(ExchangeNode, self).commit()
        node_hist.change_log = change_log
        return node_hist

    def unpublish(self):
        self.deleted = True
        with g.context_manager.push(app_config_id=self.app_config_id):
            self.commit("Deleted")
        g.solr.delete(q="id:{}".format(self.index_id()))
        self.notify_delete()

    @property
    def title_s(self):
        return self.title

    def index(self, text_objects=None, use_posts=False, **kwargs):
        if self.deleted:  # no index for old nodes
            return None

        if text_objects is None:
            text_objects = []

        index_fields = self.index_fields or {}
        kwargs.update(index_fields)

        last_version = self.get_version(self.version)
        kwargs.update({
            "revision_s": self.revision,
            "share_scope_s": self.share_scope,
            "exchange_uri_s": self.exchange_uri,
            "project_url_s": self.project.url(),
            "tool_url_s": self.app_config.url(),
            "tool_label_s": self.app_config.options.mount_label,
            "tool_name_s": self.tool_name,
            "artifact_type_s": self.forge_artifact_name,
            "author_display_name_s": last_version.author.display_name,
            "author_username_s": last_version.author.username
        })
        if "text" not in kwargs:
            a_index = self.artifact.index()
            if a_index and 'text' in a_index:
                kwargs["text"] = a_index["text"]

        return super(ExchangeNode, self).index(
            text_objects=text_objects,
            use_posts=use_posts,
            **kwargs)

    @property
    def exchange(self):
        return g.exchange_manager.get_exchange_by_uri(self.exchange_uri)

    @LazyProperty
    def cur_artifact(self):
        """Get original artifact at tip (no version info)"""
        a_spec = self.exchange.config["artifacts"][self.exchange_mount_point]
        artifact = a_spec["artifact"].query.get(_id=self.forge_artifact_id)
        return artifact

    @LazyProperty
    def artifact(self):
        """Returns original artifact"""
        artifact = self.cur_artifact
        if self.forge_artifact_version and hasattr(artifact, "version"):
            if self.forge_artifact_version < artifact.version:
                artifact = artifact.get_version(self.forge_artifact_version)
        return artifact

    def update_index_fields(self, use_cur_artifact=True, index_fields=None):
        rel_artifact = None

        if use_cur_artifact and self.cur_artifact:
            rel_artifact = self.cur_artifact
            if hasattr(self.cur_artifact, "version"):
                self.forge_artifact_version = self.cur_artifact.version
            self.forge_artifact_title = self.title = self.cur_artifact.title_s
        elif not use_cur_artifact and self.artifact:
            rel_artifact = self.artifact
            self.forge_artifact_title = self.title = self.artifact.title_s

        if index_fields is not None:
            self.index_fields = index_fields
        elif rel_artifact:
            self.index_fields = rel_artifact.exchange_index_fields()

    def authors(self):
        """All the users that have edited this page"""
        user_ids = set(r.author.id for r in self.history())
        return User.query.find({'_id': {'$in': list(user_ids)}}).all()

    def get_share_project_ids(self):
        project_ids = []
        for ace in self.acl:
            if ace.member_project_id:
                project_ids.append(ace.member_project_id)
        return project_ids

    def get_share_neighborhood_ids(self):
        nbhd_ids = []
        for ace in self.acl:
            if ace.project_id:
                proj = Project.query_get(_id=ace.project_id)
                if proj:
                    nbhd_ids.append(proj.neighborhood_id)
        return nbhd_ids

