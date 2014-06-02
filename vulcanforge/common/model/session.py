import logging

from pylons import app_globals as g

from ming import Session
from ming.odm.base import state
from ming.odm.odmsession import (
    ThreadLocalODMSession,
    SessionExtension,
    session
)

LOG = logging.getLogger(__name__)


class VFSessionExtension(SessionExtension):

    def __init__(self, session):
        SessionExtension.__init__(self, session)
        self.objects_added = []
        self.objects_modified = []
        self.objects_deleted = []

    def before_flush(self, obj=None):
        if obj is None:
            self.objects_added = list(self.session.uow.new)
            self.objects_modified = list(self.session.uow.dirty)
            self.objects_deleted = list(self.session.uow.deleted)
        else:  # pragma no cover
            st = state(obj)
            if st.status == st.new:
                self.objects_added = [obj]
            elif st.status == st.dirty:
                self.objects_modified = [obj]
            elif st.status == st.deleted:
                self.objects_deleted = [obj]

    def after_flush(self, obj=None):
        self.objects_added = []
        self.objects_modified = []
        self.objects_deleted = []


class ArtifactSessionExtension(VFSessionExtension):

    def index_deleted(self, deleted_specs):
        """deleted_specs should be a list of dictionaries with keys
        ref_id, index_parent_ref_id

        """
        from vulcanforge.artifact.tasks import del_artifacts
        del_artifacts.post(deleted_specs)

    def index_new(self, new_ref_ids, mod_dates=None):
        """Added or modified"""
        from vulcanforge.artifact.tasks import add_artifacts
        add_artifacts.post(new_ref_ids, mod_dates=mod_dates)

    def after_flush(self, obj=None):
        """Update artifact references, and add/update this artifact to solr"""
        if not getattr(self.session, 'disable_artifact_index', False):
            from vulcanforge.artifact.model import ArtifactReference, Shortlink

            # start list of affected app configs
            app_configs = set()

            # Upsert artifact references & shortlinks exist for new objects
            new_ref_ids = []
            mod_dates = {}
            for obj in self.objects_added + self.objects_modified:
                app_configs.add(obj.app_config)
                aref = ArtifactReference.from_artifact(obj)
                new_ref_ids.append(aref._id)
                Shortlink.from_artifact(obj)
                mod_dates[aref._id] = obj.mod_date

            # Flush shortlinks
            session(ArtifactReference).flush()

            # Post delete and add indexing operations
            if self.objects_deleted:
                delete_specs = []
                for obj in self.objects_deleted:
                    ref_id = obj.index_id()
                    parent_ref_id = None
                    index_parent = obj.index_parent()
                    if index_parent:
                        parent_ref_id = index_parent.index_id()
                    delete_specs.append({
                        "ref_id": ref_id,
                        "index_parent_ref_id": parent_ref_id
                    })
                self.index_deleted(delete_specs)
            if new_ref_ids:
                self.index_new(new_ref_ids, mod_dates=mod_dates)

            # store events
            for obj in self.objects_added:
                g.store_event('create', extra=obj.index_id())
            for obj in self.objects_modified:
                g.store_event('modify', extra=obj.index_id())
            for obj in self.objects_deleted:
                g.store_event('delete', extra=obj.index_id())

            # Update Artifact label counts
            for app_config in app_configs:
                app_config.update_label_counts()

        super(ArtifactSessionExtension, self).after_flush(obj)


class SOLRSessionExtension(VFSessionExtension):

    def after_flush(self, obj=None):
        """Update/add to solr"""
        from vulcanforge.common.model.index import GlobalObjectReference
        from vulcanforge.common.tasks.index import (
            del_global_objs, add_global_objs)

        refs = [GlobalObjectReference.from_object(obj)
                for obj in self.objects_added + self.objects_modified
                if obj.indexable()]
        # Flush globalreferences
        session(GlobalObjectReference).flush()

        # Post delete and add indexing operations
        if self.objects_deleted:
            del_global_objs.post([
                obj.index_id() for obj in self.objects_deleted
            ])
        if refs:
            add_global_objs.post([ref._id for ref in refs])

        super(SOLRSessionExtension, self).after_flush(obj)


class VisualizableSessionExtension(VFSessionExtension):

    def before_flush(self, obj=None):
        from vulcanforge.visualize.model import VisualizableQueryParam
        super(VisualizableSessionExtension, self).before_flush(obj)
        for obj in self.objects_deleted:
            try:
                for pfile in obj.find_processed_files():
                    pfile.delete()
            except Exception:
                LOG.exception('Error deleting processed files for %s:%s',
                              str(obj), str(obj._id))
            session(VisualizableQueryParam).flush()
            VisualizableQueryParam.query.remove({
                "unique_id": obj.get_unique_id()})

    def after_flush(self, obj=None):
        for obj in self.objects_added + self.objects_modified:
            obj.trigger_vis_upload_hook.post()
        super(VisualizableSessionExtension, self).after_flush(obj)


main_doc_session = Session.by_name('main')
project_doc_session = Session.by_name('project')
main_orm_session = ThreadLocalODMSession(main_doc_session)
project_orm_session = ThreadLocalODMSession(project_doc_session)
artifact_orm_session = ThreadLocalODMSession(
    doc_session=project_doc_session,
    extensions=[ArtifactSessionExtension])
repository_orm_session = ThreadLocalODMSession(
    doc_session=main_doc_session,
    extensions=[])
solr_indexed_session = ThreadLocalODMSession(
    doc_session=main_doc_session,
    extensions=[SOLRSessionExtension])
visualizable_orm_session = ThreadLocalODMSession(
    doc_session=project_doc_session,
    extensions=[VisualizableSessionExtension])
visualizable_artifact_session = ThreadLocalODMSession(
    doc_session=project_doc_session,
    extensions=[ArtifactSessionExtension, VisualizableSessionExtension])
