import logging
import os.path

from ming.odm.odmsession import ThreadLocalODMSession
from pylons import app_globals as g, tmpl_context as c
from vulcanforge.project.model import Project
from vulcanforge.tools.wiki.model import Page

from . import base


log = logging.getLogger(__name__)


class ForgeAdminToolsCommand(base.Command):
    summary = "Initialize ForgeAdmin project specific tools"
    parser = base.Command.standard_parser(verbose=True)

    def command(self):
        self.basic_setup()
        log.info('Ensuring that ForgeAdmin specific tools are installed...')
        c.project = Project.query.get(shortname=g.site_admin_project)

        self._ensure_installed('Visualize', 'visualize', 'Visualizers')
        already_there = self._ensure_installed('Wiki', 'static', 'VF Pages')
        if not already_there:
            with g.context_manager.push(g.site_admin_project, 'static'):
                self._create_static_manager(
                    c.project,
                    c.project.app_instance('static'))
        ThreadLocalODMSession.flush_all()

    def _ensure_installed(self, ep_name, mount_point, mount_label=None):
        log.info('...checking for %s at %s/%s...', ep_name,
                 g.site_admin_project, mount_point)
        already_there = True
        app_instance = c.project.app_instance(mount_point)
        if app_instance is None:
            log.info('...installing %s at %s/%s.', ep_name,
                     g.site_admin_project, mount_point)
            c.project.install_app(ep_name, mount_point, mount_label)
            already_there = False
        else:
            log.info('...found %s at %s/%s.', ep_name, g.site_admin_project,
                     mount_point)
        return already_there

    def _create_static_manager(self, project, app):
        # title, static file
        static_pages = (
            ('Terms', 'terms.txt'),
            ('Contact', 'contact.txt'),
            ('About', 'about.txt'),
            ('Technology', 'tech.txt'),
            ('VF-Team', 'team.txt')
        )
        from pylons import app_globals as g
        curdir = os.path.dirname(__file__)
        for title, filename in static_pages:
            page = Page.query.get(title=title, app_config_id=app.config._id)
            if not page:
                path = '%s/resources/staticmanager/%s' % (curdir, filename)
                try:
                    f = open(path, 'r')
                    content = f.read()
                except Exception, e:
                    log.warn('Exception reading %s: %s' % (path, str(e)))
                    content = ''
                log.info('.....adding WikiPage %s with content %s' %
                         (title, content))
                Page(
                    title=title,
                    text=content,
                    viewable_by=[u'all'],
                    app_config_id=app.config._id)
            else:
                log.info('.....found WikiPage %s' % title)
