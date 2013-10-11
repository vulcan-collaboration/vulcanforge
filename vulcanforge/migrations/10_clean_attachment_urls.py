# -*- coding: utf-8 -*-

"""
10_clean_attachment_urls

@author: U{tannern<tannern@gmail.com>}
"""
from vulcanforge.artifact.model import BaseAttachment
from vulcanforge.discussion.model import Post, DiscussionAttachment
from vulcanforge.migration.base import BaseMigration
from vulcanforge.migration.util import MappedClassFieldReference
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.project.model import Project
from vulcanforge.tools.forum.model import ForumPost, ForumAttachment
from vulcanforge.tools.forum.model.forum import ForumPostHistory
from vulcanforge.tools.tickets.model import Ticket, TicketHistory, \
    TicketAttachment
from vulcanforge.tools.wiki.model import Page, PageHistory, WikiAttachment


class CleanAttachmentURLs(BaseMigration):
    attachment_models = [
        BaseAttachment,
        ForumAttachment,
        DiscussionAttachment,
        TicketAttachment,
        WikiAttachment
    ]
    markdown_fields = [
        MappedClassFieldReference(Neighborhood, 'homepage'),
        MappedClassFieldReference(Project, 'description'),
        MappedClassFieldReference(Post, 'text'),
        MappedClassFieldReference(ForumPost, 'text'),
        MappedClassFieldReference(ForumPostHistory, 'data', key='text'),
        MappedClassFieldReference(Ticket, 'description'),
        MappedClassFieldReference(TicketHistory, 'data', key='description'),
        MappedClassFieldReference(Page, 'text'),
        MappedClassFieldReference(PageHistory, 'data', key='text')
    ]

    def run(self):
        self.log.info('Migrating all attachment urls in markdown fields...')
        self.log.info('- attachments:')
        for old_url, new_url in self.iter_urls():
            self.log.info('    {}  -->  {}'.format(old_url, new_url))
        self.log.info('- migration:')
        for field_record in self.markdown_fields:
            self.log.info('    migrating {}...'.format(field_record))
            for instance in field_record.iter_instances():
                value = field_record.get_value(instance)
                for remote_url, local_url in self.iter_urls():
                    value = value.replace(remote_url, local_url)
                field_record.set_value(instance, value)
        self.log.info('done.')

    def iter_urls(self):
        seen_remote_urls = set()
        for Model in self.attachment_models:
            for instance in Model.query.find():
                remote_url = instance.remote_url()
                local_url = instance.local_url()
                if remote_url in seen_remote_urls:
                    continue
                seen_remote_urls.add(remote_url)
                yield remote_url, local_url
