# -*- coding: utf-8 -*-

"""
06_ensure_file_references

@author: U{tannern<tannern@gmail.com>}
"""
from vulcanforge.artifact.model import BaseAttachment
from vulcanforge.common.model import File, FileReference
from vulcanforge.discussion.model import DiscussionAttachment
from vulcanforge.migration.base import BaseMigration
from vulcanforge.neighborhood.model import NeighborhoodFile
from vulcanforge.project.model import ProjectFile
from vulcanforge.tools.forum.model import ForumFile
from vulcanforge.tools.tickets.model import TicketAttachment
from vulcanforge.tools.wiki.model import WikiAttachment


FILE_CLASSES = (
    File,
    BaseAttachment,
    DiscussionAttachment,
    NeighborhoodFile,
    ProjectFile,
    ForumFile,
    TicketAttachment,
    WikiAttachment,
)


class EnsureFileReferences(BaseMigration):

    def run(self):
        self._create_references()

    def _create_references(self):
        self.write_output("Creating FileReference objects for File classes...")
        self.seen_collections = set()
        map(self._upsert_model, FILE_CLASSES)
        self.write_output("Finished creating FileReference objects.")

    def _upsert_model(self, Model):
        collection_name = Model.__mongometa__.name
        seen = collection_name in self.seen_collections
        self.seen_collections.add(collection_name)
        if seen:
            self.write_output("  {} ({}): skipped: polymorphic".format(
                Model.__name__, collection_name))
            return
        cursor = Model.query.find()
        count = cursor.count()
        self.write_output("  {} ({}): checking {} instances...".format(
            Model.__name__, collection_name, count))
        i = 0
        for instance in cursor:
            i += 1
            self._upsert_instance(i, count, instance)

    def _upsert_instance(self, i, count, instance):
        msg = ''
        try:
            FileReference.upsert_from_file_instance(instance)
            msg = 'confirmed'
        except Exception, e:
            msg = 'error: {}'.format(e)
        finally:
            self.write_output("    [{}/{}] {} {}".format(
                i, count, instance._id, msg))
