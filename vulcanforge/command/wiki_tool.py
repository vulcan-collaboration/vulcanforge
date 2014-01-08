# coding=utf-8
import logging
import json
import os
import zipfile

from pylons import tmpl_context as c, app_globals as g
from ming.odm import ThreadLocalODMSession
from tg import config
from vulcanforge.auth.model import User
from vulcanforge.common.util import temporary_dir
from vulcanforge.common.util.context import register_widget_context
from vulcanforge.neighborhood.model import Neighborhood
from vulcanforge.tools.wiki.model import Page, Globals
from vulcanforge.tools.wiki.util import BrokenLinkFinder

from .base import Command

LOG = logging.getLogger(__name__)
WIKI_DUMP_EXTENSION = '.wikidump.json'


class WikiDumpHandlerError(Exception):
    pass


class ExportWikiPages(Command):
    min_args = 2
    max_args = None
    usage = ('<ini file> -- <project shortname> <wiki mount name> '
             '<directory to export to> [neighborhood]')
    summary = 'Exports wiki pages and attachments into a dump archive.'
    parser = Command.standard_parser(verbose=True)
    parser.add_option(
        '-r', '--replace_urls', dest='replace_urls', action='store_true',
        default=False, help="Hunt down and replace relative urls")
    parser.add_option(
        '-a', '--skip_attachments', dest='skip_attachments',
        action='store_true', default=False, help="Do not export attachments")

    def command(self):
        self.basic_setup()

        neighborhood = None
        if len(self.args) > 4:
            neighborhood = Neighborhood.by_prefix(self.args[4])

        g.context_manager.set(self.args[1], self.args[2],
                              neighborhood=neighborhood)
        if not c.app or c.app.config.tool_name.lower() != 'wiki':
            WikiDumpHandlerError(
                "General error: unable to locate wiki app at {}/{}".format(
                    self.args[1], self.args[2]))

        LOG.info('Exporting wikipages from {}/{}...'.format(
            self.args[1], self.args[2]))
        root_title = c.app.root_page_name
        criteria = dict(app_config_id=c.app.config._id)
        criteria['deleted'] = False
        q = Page.query.find(criteria)
        q = q.sort('title')
        count = q.count()

        if not count:
            WikiDumpHandlerError('No pages to export')

        # set up archive
        if len(self.args) > 3:
            dirname = self.args[3]
        else:
            dirname = os.getcwd()
        base_filename = self.args[1] + '_' + self.args[2] + '_wikidump'
        zip_filename = os.path.join(dirname, base_filename + '.zip')
        with zipfile.ZipFile(zip_filename, 'w', allowZip64=True) as zip_handle:
            # create page manifest, writing attachments along the way
            pages = []
            for i, page in enumerate(q):
                attachments = []
                if not self.options.skip_attachments:
                    for attachment in page.attachments:
                        exp_path = os.path.join(
                            page.title, attachment.filename)
                        attachments.append({
                            'filename': attachment.filename,
                            'exp_path': exp_path,
                            'content_type': attachment.content_type
                        })
                        try:
                            zip_handle.writestr(exp_path, attachment.read())
                        except Exception:
                            LOG.exception("Error writing attachment %s >> %s",
                                          attachment.filename, page.title)

                if self.options.replace_urls:
                    page_text = self.update_relative_urls(page)
                else:
                    page_text = page.text
                page_descriptor = {
                    'title': page.title,
                    'text': page_text,
                    'labels': page.labels,
                    'attachments': attachments,
                    'order': i,
                    'is_root': page.title == root_title
                }

                pages.append(page_descriptor)

            # finish write
            pages_filename = 'pages' + WIKI_DUMP_EXTENSION
            zip_handle.writestr(pages_filename, json.dumps(pages))
            LOG.info('{number} pages found.'.format(number=count))
            LOG.info('{fn} created.'.format(fn=zip_filename))

    def update_relative_urls(self, page):
        """Returns page text with relative urls updated"""
        base_url = config.get('base_url')
        if 'localhost' in base_url:
            base_url = None
        to_replace = page.app_config.url()
        app = page.app_config.options.mount_point
        replace_with = to_replace.replace(app, '{_app}')\
                                 .replace(page.project.shortname, '{_project}')

        page_text = page.text
        if base_url:
            page_text = page_text.replace(base_url, '')
        page_text = page_text.replace(to_replace, replace_with)
        page_text = page_text.replace(
            '[{project}:{app}:'.format(
                project=page.project.shortname,
                app=app),
            '[')
        page_text = page_text.replace('[{app}:'.format(app=app), '[')
        return page_text


class ImportWikiPages(Command):
    min_args = 4
    max_args = None
    usage = ('<ini file> -- <dump file> <to project (shortname)> '
             '<into wiki (mount name)> <by user (username)> [neighborhood]')
    summary = 'Imports wiki pages and attachments from a dump archive.'
    parser = Command.standard_parser(verbose=True)
    parser.add_option(
        '-u', '--no_update', dest='no_update', action='store_true',
        default=False,
        help="Do not update existing pages, just print a warning and skip")
    parser.add_option(
        '-r', '--replace_urls', dest='replace_urls', action='store_true',
        default=False,
        help="Update content exported with -r option to have correct urls")

    def command(self):
        self.basic_setup()

        LOG.info('Importing wikipages...')

        zip_name = self.args[1]
        if not os.path.exists(zip_name):
            WikiDumpHandlerError("General error: unable to locate dump file!")

        neighborhood = None
        if len(self.args) > 5:
            neighborhood = Neighborhood.by_prefix(self.args[5])

        g.context_manager.set(self.args[2], self.args[3],
                              neighborhood=neighborhood)
        if not c.app or c.app.config.tool_name.lower() != 'wiki':
            WikiDumpHandlerError(
                "General error: unable to locate app [{mount_point}]!".format(
                    mount_point=self.args[3]))

        c.user = User.by_username(self.args[4])
        if c.user is None:
            raise WikiDumpHandlerError("General error: unable to find user!")

        with temporary_dir() as dirname:
            with zipfile.ZipFile(zip_name, allowZip64=True) as zip_handle:
                zip_handle.extractall(dirname)

            # get root
            pages_filename = 'pages' + WIKI_DUMP_EXTENSION
            with open(os.path.join(dirname, pages_filename)) as pages_fp:
                for page_descriptor in json.load(pages_fp):
                    if self.options.no_update:
                        page = Page.query.get(
                            title=page_descriptor['title'],
                            app_config_id=c.app.config._id
                        )
                        if page:
                            LOG.warn('Page {} already exists. SKIPPING'.format(
                                page_descriptor['title']
                            ))
                            continue
                    page = Page.upsert(page_descriptor['title'])
                    if page_descriptor['is_root']:
                        gl = Globals.query.get(
                            app_config_id=c.app.config._id)
                        gl.root = page.title
                    page_text = page_descriptor['text']
                    if self.options.replace_urls:
                        page_text = page_text\
                            .replace('{_project}', self.args[2])\
                            .replace('{_app}', self.args[3])
                    page.text = page_text
                    page.labels = page_descriptor['labels']
                    page.viewable_by = ['all']
                    for attachment in page_descriptor['attachments']:
                        query = page.attachment_class().metadata_for(page)
                        query['filename'] = attachment['filename']
                        old = page.attachment_class().query.get(**query)
                        if old:
                            old.delete()
                        try:
                            fp = open(
                                os.path.join(dirname, attachment['exp_path']))
                        except (IOError, KeyError):
                            LOG.warn(
                                "Unable to find %s for page %s in file",
                                attachment['exp_path'],
                                page.title
                            )
                        else:
                            page.attach(
                                attachment['filename'],
                                fp,
                                content_type=attachment['content_type']
                            )
                    page.commit()

        ThreadLocalODMSession.flush_all()


class FindBrokenLinks(Command):
    min_args = 3
    max_args = 3
    usage = '<ini file> project mount_point'
    summary = 'Finds broken links and images in a wiki tool.'
    parser = Command.standard_parser(verbose=True)
    parser.add_option("-n", "--neighborhood", dest="neighborhood",
                      help="Neighborhood url prefix (if necessary)")
    parser.add_option("-u", "--user", dest="user",
                      help="Make requests as user with this username")

    def command(self):
        self.basic_setup()
        register_widget_context()
        neighborhood = None
        if self.options.neighborhood:
            neighborhood = Neighborhood.by_prefix(self.options.neighborhood)
            if not neighborhood:
                raise RuntimeError("Unable to find neighborhood {}".format(
                    self.options.neighborhood))

        g.context_manager.set(self.args[1], self.args[2],
                              neighborhood=neighborhood)

        if self.options.user:
            user = User.by_username(self.options.user)
        else:
            user = None
        broken_finder = BrokenLinkFinder(user=user)

        def text_overflow(s, max_len):
            if len(s) > max_len:
                s = s[:max_len-3] + '...'
            return s

        print "{:^80} {:^80} {:^80} {:^33}".format(
            "Page (url)", "Broken Link", "Html Str", "Reason")

        fmt = "{:80} {:80} {:80} {}"
        for error_spec in broken_finder.find_broken_links_by_app():
            print fmt.format(
                error_spec["page"].url(),
                text_overflow(error_spec["link"], 80),
                text_overflow(error_spec["html"], 80),
                text_overflow(error_spec["msg"], 80)
            )