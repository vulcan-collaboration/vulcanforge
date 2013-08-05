import logging
from datetime import datetime

from ming.odm import session

from . import base
from vulcanforge.project.model import Project
from vulcanforge.visualize.model import Visualizer

log = logging.getLogger(__name__)


class CreateDefaultVisualizersCommand(base.Command):
    summary = 'Initialize Default Visualizers in the Database'
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        from pylons import app_globals as g
        site_admin_project = Project.query.get(shortname=g.site_admin_project)
        if site_admin_project is None:
            raise Exception('Must have site admin project')
        if not site_admin_project.app_instance(u'visualize'):
            site_admin_project.install_app(
                u'Visualize', u'visualize', u'Visualizers')
        self.upsert_image_visualizer()
        self.upsert_syntax_visualizer()
        self.upsert_pdf_visualizer()
        session(Visualizer).flush()

    def upsert_image_visualizer(self):
        image_visualizer = Visualizer.query.get(name='Raw Image Visualizer')
        if image_visualizer is None:
            log.info('Installing image visualizer')
            image_visualizer = Visualizer(
                created_date=datetime(1970, 1, 1),
                widget='image',
                name='Raw Image Visualizer',
                mime_types=['^image/'],
                description='Raw Image Visualizer',
                priority=-1,
                active=True
            )
        image_visualizer.icon = 'FILE_IMAGE'
        return image_visualizer

    def upsert_syntax_visualizer(self):
        syntax_visualizer = Visualizer.query.get(name='Syntax Visualizer')
        if syntax_visualizer is None:
            log.info('Installing syntax visualizer')
            syntax_visualizer = Visualizer(
                created_date=datetime(1970, 1, 1),
                widget='syntax',
                name='Syntax Visualizer',
                priority=-1,
                active=True
            )
        syntax_visualizer.mime_types = [
            '^text/',
            '^application/javascript',
            '^application/http',
            '^application/json',
            '^application/xml',
            '^application/xhtml\+xml',
            '^application/x-httpd-php',
            '^application/atom\+xml',
            '^application/atomcat\+xml',
            '^application/atomserv\+xml',
            '^application/vnd.mozilla.xul\+xml',
            '^application/vnd.wap.wbxml',
            '^application/x-info',
            '^application/x-latex',
            ]
        syntax_visualizer.icon = 'FILE_TEXT'
        return syntax_visualizer

    def upsert_pdf_visualizer(self):
        pdf_visualizer = Visualizer.query.get(shortname='pdf')
        if pdf_visualizer is None:
            log.info('Installing pdf visualizer')
            pdf_visualizer = Visualizer(
                created_date=datetime(1970, 1, 1),
                widget="pdf",
                name="PDF Visualizer",
                shortname="pdf",
                mime_types=['^application/pdf'],
                priority=-1,
                active=True,
                icon='FILE_TEXT'
            )
        return pdf_visualizer
