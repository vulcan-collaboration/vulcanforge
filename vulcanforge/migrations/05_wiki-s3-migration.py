from ming.odm import ThreadLocalODMSession
from cStringIO import StringIO

from boto.s3.key import Key

from pylons import app_globals as g
from tg import config

from vulcanforge.common.helpers import urlquote
from vulcanforge.migration.base import BaseMigration
from vulcanforge.tools.wiki.model import WikiAttachment


class MigrateWikiAttachmentS3Keys(BaseMigration):

    def run(self):
        count = 0
        self.write_output('Transferring Wiki Attachments')
        for wiki_attachment in WikiAttachment.query.find({
            'attachment_type': 'WikiAttachment'
        }):

            try:
                old_key = self.get_s3_key(wiki_attachment.keyname,
                                          wiki_attachment.artifact)
                key_data = StringIO()
                old_key.get_contents_to_file(key_data)

                key_data.seek(0)
                new_key = g.get_s3_key(wiki_attachment.keyname,
                                       wiki_attachment.artifact)
                new_key.set_contents_from_file(key_data)

                old_key.delete()
                count += 1
            except Exception, e:
                print str(e)

        ThreadLocalODMSession.close_all()
        self.write_output('Done %s' % str(count))

    def artifact_s3_prefix(self, artifact):
        if artifact is not None:
            return urlquote('/'.join((
                artifact.project.shortname,
                artifact.app_config.options.mount_point,
                artifact.shorthand_id())) + '#')
        else:
            return ''

    def make_s3_keyname(self, key_name, artifact=None):
        return config.get('s3.app_prefix', 'Forge') +\
               self.artifact_s3_prefix(artifact) +\
               urlquote(key_name)

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
