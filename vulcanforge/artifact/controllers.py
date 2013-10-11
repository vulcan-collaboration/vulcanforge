# -*- coding: utf-8 -*-

import logging
import urllib

from ming.utils import LazyProperty
from webob import exc
from paste.deploy.converters import asbool
from pylons import tmpl_context as c, app_globals as g, request
from tg import redirect
from tg.decorators import expose
from tg.controllers import RestController

from vulcanforge.common.controllers import BaseController
from vulcanforge.common.controllers.decorators import require_post
from vulcanforge.common.exceptions import AJAXNotFound, AJAXForbidden
from vulcanforge.artifact.model import ArtifactReference, Shortlink
from vulcanforge.artifact.widgets import short_artifact_link_data
from vulcanforge.artifact.tasks import process_artifact
from vulcanforge.discussion.model import Post
from vulcanforge.project.model import Project
from vulcanforge.visualize.model import Visualizer
from vulcanforge.visualize.widgets.visualize import ArtifactRenderVisualizer


LOG = logging.getLogger(__name__)


class ArtifactReferenceController(BaseController):

    def _make_app_reference(self, app_config, project=None, label=None,
                            artifact=None):
        if project is None:
            project = Project.query.get(_id=app_config.project_id)

        referenceable = app_config.reference_opts['can_reference'] and \
                        app_config.is_visible_to(c.user)
        if referenceable:
            createURL = None
            create_perm = app_config.reference_opts['create_perm']
            creatable = (
                app_config.reference_opts.get('can_create') and
                g.security.has_access(app_config, create_perm) and
                app_config.load().can_create(artifact)
            )
            if creatable:
                createURL = app_config.url() + \
                            app_config.reference_opts['new_uri'] + '/'
            if label is None:
                label = app_config.options.mount_label
                if app_config.project_id != project._id:
                    label = '{}:{}'.format(project.name, label)
            return dict(
                mount_point=app_config.options.mount_point,
                tool_name=app_config.tool_name.capitalize(),
                label=label,
                createURL=createURL,
                ordinal=app_config.options.get('ordinal', 0),
                instances=[],
                count=0
            )

    @expose('json')
    def get_references(self, artifact_ref=None, limit=5, embedded=False, **kw):
        """
        Get related artifacts for an artifact

        @param artifact_ref: str  artifact reference id
        @param limit: int   max relations per category (0 = unlimited)
        @return: dict   related artifacts and shortlink for given artifact

        """
        # get the aref and set the context
        embedded = asbool(embedded)
        artifact = None
        if artifact_ref:
            artifact = ArtifactReference.artifact_by_index_id(
                urllib.unquote(artifact_ref))
        if not artifact:
            raise AJAXNotFound("Reference doesn't yet exist")
        g.context_manager.set(app_config_id=artifact.app_config_id)
        try:
            g.security.require_access(artifact.project.neighborhood, 'read')
            g.security.require_access(artifact, 'read')
        except exc.HTTPClientError:
            raise AJAXForbidden('Read access required')

        reference_dict = {}
        # get default tools
        for ac in c.project.app_configs:
            if ac.reference_opts.get('can_create'):
                app_ref = self._make_app_reference(
                    ac, c.project, artifact=artifact)
                if app_ref:
                    reference_dict[app_ref['label']] = app_ref

        # get relations
        seen_ids = set()
        for relation in artifact.relations():
            related = relation['artifact']
            if related.index_id() in seen_ids:
                continue
            seen_ids.add(related.index_id())

            # add tool if necessary
            label = related.ref_category()
            if not label in reference_dict:
                reference_dict[label] = self._make_app_reference(
                    related.app_config,
                    c.project,
                    label,
                    artifact=artifact
                )

            # update instances and relations count
            if reference_dict[label]:
                instances = reference_dict[label]['instances']
                if not limit or len(instances) < limit:
                    if embedded:
                        data = short_artifact_link_data(related)
                    else:
                        data = (related.link_text_short(), related.url())
                    instances.append(data)
                reference_dict[label]['count'] += 1

        # artifact shortlink
        data = dict(
            relations=sorted(filter(None, reference_dict.values()),
                             key=lambda a: a['ordinal']),
            shortLink=Shortlink.from_artifact(artifact).render_link()
        )

        # artifact preview
        if artifact.preview_url:
            data['preview'] = artifact.preview_url
        elif 'derive_preview_url' in dir(artifact):
            derived_url = artifact.derive_preview_url()
            if derived_url:
                data['preview'] = derived_url

        return data

    @expose('json')
    def collaboration_apps(self, project_id=None):
        if project_id is not None:
            g.context_manager.set(project_id)
        g.security.require_access(c.project, 'read')
        app_refs = []
        for ac in filter(lambda a: a.reference_opts['can_create'],
                         c.project.app_configs):
            app_ref = self._make_app_reference(ac, c.project)
            if app_ref:
                i = 0
                for a in app_refs:
                    if app_ref['ordinal'] < a:
                        break
                    i += 1
                app_refs.insert(i, app_ref)
        return dict(
            relations=app_refs,
            loading=True
        )


class BaseArtifactRest(object):

    def __init__(self, index_only=False):
        super(BaseArtifactRest, self).__init__()
        self.index_only = index_only

    def _from_shortlink(self, shortlink):
        full_shortlink = u'[{}:{}:{}]'.format(
            c.project.shortname,
            c.app.config.options.mount_point,
            shortlink
        )
        artifact = Shortlink.artifact_by_link(full_shortlink)
        return artifact

    def _from_index_id(self, index_id):
        aref = ArtifactReference.query.get(_id=index_id)
        if aref:
            return aref.artifact

    def _before(self, *args, **kw):
        self.artifact = None
        if not self.index_only and 'shortlink' in request.params:
            self.artifact = self._from_shortlink(
                urllib.unquote(request.params['shortlink']))
        if not self.artifact and 'index_id' in request.params:
            self.artifact = self._from_index_id(
                urllib.unquote(request.params['index_id']).decode('utf8'))
        if not self.artifact:
            raise AJAXNotFound
        g.security.require_access(self.artifact.project.neighborhood, 'read')


class BaseAlternateRestController(RestController):
    artifact = None

    @expose('json')
    def get_one(self, context='visualizer', **kw):
        g.security.require_access(self.artifact, 'read')
        response = {'url': None}
        if self.artifact.alt_loading:
            response['status'] = 'loading'
        else:
            alt = self.artifact.get_alt_resource(context)
            if alt:
                if isinstance(alt, basestring):
                    alt = {'url': alt}
                response.update({
                    'url': alt.get('url'),
                    'status': alt.get('status', 'available')
                })
            else:
                response['status'] = 'dne'
        return response

    @expose()
    def put(self, context='visualizer', url=None,
            key=None, still_loading=False, **kw):
        g.security.require_access(
            self.artifact,
            self.artifact.app_config.reference_opts['create_perm']
        )
        if not url and key:
            url = dict(key=key)
        if context == 'all':
            context = '*'
        self.artifact.set_alt_resource(context, url=url)
        self.artifact.alt_loading = still_loading

    def _assert_can_process(self, context):
        if self.artifact.alt_loading or \
        self.artifact.get_alt_resource(context):
            raise AJAXForbidden(
                'Artifact has alternate resource or is currently loading')
        return True


class AlternateRestController(BaseAlternateRestController, BaseArtifactRest):

    @expose('json')
    def post(self, processor=None, context='visualizer', **kw):
        """Queues a processesing operation"""
        g.security.require_access(self.artifact, 'read')
        self._assert_can_process(context)
        process_artifact.post(processor, context, self.artifact.index_id())
        self.artifact.alt_loading = True
        return {
            'success': True
        }


class ArtifactRestController(BaseArtifactRest):
    """
    B{Description}: Artifact related functionality

    """

    def __init__(self, index_only=False):
        super(ArtifactRestController, self).__init__(index_only)
        self.alternate = AlternateRestController(index_only)

    @expose('json')
    def get_comments(self, **kw):
        """
        B{Description}: Get comments associated with a given artifact.
        Slug is a unique identifier of this post within the artifact discussion
        thread.

        B{Errors}
            - 404: If the neighborhood, the project or the tool does not exist

        B{Requires authentication}

        B{Example request}

        GET I{rest/neighborhood/project/tool/artifact_shortlink/get_comments}

        @return: {
        "posts": [{
        "slug": str,
        "text": str,
        "author": str username,
        "timestamp": timestamp
        }, ...]
        }

        @rtype: JSON document
        """
        g.security.require_access(self.artifact, 'read')
        thread = self.artifact.discussion_thread
        return dict(posts=thread.posts)

    @require_post()
    @expose('json')
    def add_comment(self, text, reply_to=None, **kw):
        """
        B{Description}: Add a comment to an artifact.

        B{Errors}
            - 404: If the neighborhood, the project or the tool does not exist

        B{Requires authentication}

        B{Example request}

        POST I{rest/neighborhood/project/tool/artifact_shortlink/add_comment}

        @param text: Required, the comment itself
        @param reply_to: Optional, the slug of another post within the
        discussion thread.
        @return: {
        "post": [{
        "slug": str,
        "text": str,
        "author": str username,
        "timestamp": timestamp
        }
        }

        @rtype: JSON document
        """
        g.security.require_access(self.artifact, 'read')
        thread = self.artifact.discussion_thread
        if reply_to:
            parent = Post.query.get(slug=reply_to, thread_id=thread._id)
            if not parent:
                raise AJAXNotFound('Parent post not found')
            post = thread.post(text, parent_id=parent._id)
        else:
            post = thread.add_post(text=text)
        return dict(post=post)

    @expose('json')
    def has_access(self, permission="read", **kw):
        return {
            "has_access": g.security.has_access(self.artifact, permission)
        }


class AttachmentsController(BaseController):
    AttachmentControllerClass = None

    def __init__(self, artifact):
        self.artifact = artifact

    @expose()
    def _lookup(self, filename=None, *args):
        if filename:
            if not args:
                filename = request.path.rsplit('/', 1)[-1]
            filename = urllib.unquote(filename)
            controller = self.AttachmentControllerClass(
                filename, self.artifact)
            return controller, args
        else:
            raise exc.HTTPNotFound


class AttachmentController(BaseController):
    AttachmentClass = None
    edit_perm = 'edit'

    class Widgets(BaseController.Widgets):
        artifact_render_widget = ArtifactRenderVisualizer()

    def _check_security(self):
        g.security.require_access(self.artifact, 'read')

    def __init__(self, filename, artifact):
        self.filename = filename
        self.artifact = artifact

    @LazyProperty
    def attachment(self, **kw):
        metadata = self.AttachmentClass.metadata_for(self.artifact)
        metadata['type'] = 'attachment'
        attachment = self.AttachmentClass.query.get(
            filename=self.filename,
            **metadata
        )
        if attachment is None:
            raise exc.HTTPNotFound
        return attachment

    @LazyProperty
    def thumbnail(self):
        metadata = self.AttachmentClass.metadata_for(self.artifact)
        metadata['type'] = 'thumbnail'
        attachment = self.AttachmentClass.query.get(
            filename=self.filename,
            **metadata
        )
        if attachment is None:
            raise exc.HTTPNotFound
        return attachment

    @expose()
    def index(self, delete=False, embed=True, visualizer_id=None, **kw):
        if request.method == 'POST':
            g.security.require_access(self.artifact, self.edit_perm)
            if delete:
                self.attachment.delete()
                try:
                    if self.thumbnail:
                        self.thumbnail.delete()
                except exc.HTTPNotFound:
                    pass
            redirect(request.referer or self.artifact.url())
        elif 'embed_vis' in kw:
            visualizer = None
            if visualizer_id:
                visualizer = Visualizer.query.get(_id=visualizer_id)
            return self.Widgets.artifact_render_widget.display(
                value=self.attachment,
                visualizer=visualizer,
                content=self.attachment.read(),
                filename=self.attachment.filename,
                context="embed"
            )
        elif g.s3_serve_local:
            return self.attachment.serve(embed)
        else:
            return redirect(self.attachment.remote_url())

    @expose()
    def thumb(self, embed=True):
        return self.thumbnail.serve(embed)
