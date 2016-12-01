import logging

from webob import exc
from pylons import tmpl_context as c, app_globals as g
from tg import expose, validate, flash, redirect, request

from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import validate_form, \
    require_post, vardec
from vulcanforge.common.validators import ObjectIdValidator
from vulcanforge.auth.schema import EVERYONE
from vulcanforge.exchange.schema import ExchangeACE
from vulcanforge.exchange.widgets.publish import ArtifactPublishForm
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.model import Project

LOG = logging.getLogger(__name__)


class ArtifactPublishController(BaseController):
    class Forms(BaseController.Forms):
        publish_form = ArtifactPublishForm()

    def _get_form_values_from_node(self, node):
        value = {
            "replace_existing": True,
            "replace_node": str(node._id),
            "scope": node.share_scope,
            "revision": str(node.version + 1),
            "title": node.title
        }
        if value['scope'] == 'neighborhood':
            value['share_neighborhoods'] = node.get_share_neighborhood_ids()
        elif value['scope'] == 'project':
            pids = node.get_share_project_ids()
            cur = Project.query.find({"_id": {"$in": pids}})
            value['share_projects'] = [p.shortname for p in cur]
        return value

    @expose('exchange/publish.html')
    @validate({
        "artifact_id": ObjectIdValidator(),
        "cur_node_id": ObjectIdValidator(not_empty=False)
    })
    def index(self, artifact_id=None, cur_node_id=None, **kwargs):
        artifact = c.artifact_config['artifact'].query.get(_id=artifact_id)
        if artifact is None:
            raise exc.HTTPNotFound
        g.security.require_access(artifact, 'publish')
        c.publish_form = self.Forms.publish_form
        publish_action = g.make_url('do_publish', is_index=True)

        value = {
            "artifact_id": artifact_id,
            "title": artifact.title_s
        }

        node_cls = c.artifact_config['node']
        c.replaceable_nodes = node_cls.find_from_artifact(artifact).all()
        if c.replaceable_nodes:
            cur_node = None
            if cur_node_id:
                for node in c.replaceable_nodes:
                    if node._id == cur_node_id:
                        cur_node = node
                        break
            if not cur_node:
                cur_node = c.replaceable_nodes[0]
            value.update(self._get_form_values_from_node(cur_node))
        else:
            value.update({
                "title": artifact.title_s,
                "revision": "1"
            })

        return {
            'xcng_name': c.exchange.config['name'],
            'artifact': artifact,
            'publish_action': publish_action,
            'value': value
        }

    def _create_publish_acl(self, artifact, scope, share_projects=None,
                            share_neighborhoods=None, **kwargs):
        # access control policy
        acl = []
        if scope == 'public':
            acl.append(ExchangeACE.allow(EVERYONE, 'read'))
        elif scope == 'neighborhood':
            if not share_neighborhoods:
                flash('Must specify at least one Neighborhood to share with!')
                redirect('.', {"artifact_id": artifact._id})
            for nbhd_id in share_neighborhoods:
                nbhd = Neighborhood.query.get(_id=nbhd_id)
                if not nbhd: # or not g.security.has_access(nbhd, 'read'):
                    self._publish_error(artifact._id)
                ace = ExchangeACE.allow_project(
                    nbhd.neighborhood_project._id, 'read')
                acl.append(ace)
        elif scope == 'project':
            if not share_projects:
                flash('Must specify at least one Team to share with!')
                redirect('.', {"artifact_id": artifact._id})
            for project in share_projects:
                if not project or project.deleted: # or not g.security.has_access(project, 'read'):
                    self._publish_error(artifact._id)
                ace = ExchangeACE.allow_project_members(project._id, 'read')
                acl.append(ace)
        return acl

    def _publish_error(self, artifact_id):
        flash('Erroneous Input Detected. Please try again.', 'error')
        redirect('.', {"artifact_id": artifact_id})

    @expose()
    @require_post()
    @validate_form('publish_form')
    def do_publish(self, artifact_id=None, scope='public', share_projects=None,
                   share_neighborhoods=None, replace_existing=False,
                   replace_node=None, title=None, revision=None,
                   change_log=None, index_fields=None, **kwargs):

        if c.form_errors:
            self._publish_error(artifact_id)

        # find artifact
        artifact = c.artifact_config['artifact'].query.get(_id=artifact_id)
        if artifact is None:
            raise exc.HTTPNotFound
        g.security.require_access(artifact, 'publish')

        # parse index_fields
        if index_fields is None:
            index_fields = {}
        # for key, val in kwargs.items():
        #     if key.startswith('index_fields.'):
        #         _, field = key.split('.', 1)
        #         index_fields[field] = val
        all_index_fields = artifact.exchange_index_fields()
        if index_fields:
            all_index_fields.update(index_fields)

        # create access control entries
        acl = self._create_publish_acl(
            artifact, scope, share_projects=share_projects,
            share_neighborhoods=share_neighborhoods, **kwargs)

        # create/modify node
        node_cls = c.artifact_config['node']
        with g.context_manager.push(app_config_id=artifact.app_config_id):
            params = {
                "acl": acl,
                "title": title,
                "artifact_title": artifact.title_s,
                "index_fields": all_index_fields,
                "share_scope": scope,
            }

            # get or create node
            node = None
            if replace_existing and replace_node:
                q = node_cls.find_from_artifact(artifact, _id=replace_node)
                node = q.first()
            if node:
                node.update_from_artifact(artifact, **params)
            else:
                node = node_cls.new_from_artifact(artifact, **params)
            node.revision = revision or str(node.version)
            node.commit(change_log)

        artifact.publish_hook(scope=scope, share_projects=share_projects,
            share_neighborhoods=share_neighborhoods, replace_existing=replace_existing)

        do_redirect = kwargs.get("redirect", True)
        if do_redirect:
            flash('Artifact published successfully', 'success')
            redirect(node.url())
        else:
            return node

    @expose('json')
    @require_post()
    @validate({"node_id": ObjectIdValidator()})
    def delete(self, node_id, **kwargs):
        node = c.artifact_config['node'].query.get(_id=node_id)
        if not node:
            raise exc.HTTPNotFound()
        g.security.require_access(node.artifact, 'publish')
        node.unpublish()
        node.artifact.unpublish_hook()

        return {
            "location": node.cur_artifact.url()
        }
