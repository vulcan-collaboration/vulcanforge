from cStringIO import StringIO

from boto.s3.key import Key

from pylons import app_globals as g
from tg import config

from vulcanforge.common.helpers import urlquote
from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.wiki.model import WikiAttachment, PageHistory


class MigrateWikiAttachmentS3Keys(BaseMigration):

    def run(self):
        self.write_output('Migrating Wiki Attachments...')
        cursor = WikiAttachment.query.find({
            'attachment_type': 'WikiAttachment'
        })
        for wiki_attachment in cursor:
            wikipage = wiki_attachment.artifact
            old_key = None
            while old_key is None and wikipage.version >= 0:
                old_key = self.get_s3_key(wiki_attachment.keyname,
                                          wikipage,
                                          insert_if_missing=False)
                if old_key is not None:
                    break
                try:
                    wikipage = wiki_attachment.artifact.\
                        get_version(wikipage.version - 1)
                except IndexError:
                    break
            old_key_name = self.make_s3_keyname(wiki_attachment.keyname,
                                                wikipage)
            if old_key is None:
                self.write_output("  skipping: {}".format(old_key_name))
                continue
            self.write_output("  migrating: {}".format(old_key_name))
            try:
                key_data = StringIO()
                old_key.get_contents_to_file(key_data)

                key_data.seek(0)
                new_key = g.get_s3_key(wiki_attachment.keyname,
                                       wiki_attachment.artifact)
                new_key.set_contents_from_file(key_data)

                old_key.delete()
            except Exception, e:
                self.write_output(e)
        self.write_output('Finished migrating Wiki Attachments.')

    def artifact_s3_prefix(self, artifact):
        if artifact is not None:
            if isinstance(artifact, PageHistory):
                title = artifact.data.title
            else:
                title = artifact.title
            return urlquote('/'.join((
                artifact.project.shortname,
                artifact.app_config.options.mount_point,
                title)) + '#')
        else:
            return ''

    def make_s3_keyname(self, key_name, artifact=None):
        return ''.join([
            config.get('s3.app_prefix', 'Forge'), '/',
            self.artifact_s3_prefix(artifact),
            urlquote(key_name)
        ])

    def get_s3_key(self, key_name, artifact=None, bucket=None,
                   insert_if_missing=True):
        if bucket is None:
            bucket = g.s3_bucket
        key_name = self.make_s3_keyname(key_name, artifact)

        key = None
        try:
            key = bucket.get_key(key_name)
        except:
            pass

        if key is None and insert_if_missing:
            key = Key(bucket, key_name)

        return key
