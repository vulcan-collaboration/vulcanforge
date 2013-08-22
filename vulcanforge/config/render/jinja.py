from jinja2.exceptions import TemplateNotFound
import pkg_resources

from webhelpers.html import literal
import jinja2
import ew
from tg import config


class JinjaEngine(ew.TemplateEngine):

    @property
    def _environ(self):
        return config['pylons.app_globals'].jinja2_env

    def load(self, template_name):
        try:
            return self._environ.get_template(template_name)
        except jinja2.TemplateNotFound:
            raise ew.errors.TemplateNotFound, '%s not found' % template_name

    def parse(self, template_text, filepath=None):
        return self._environ.from_string(template_text)

    def render(self, template, context):
        context = self.context(context)
        with ew.utils.push_context(ew.widget_context, render_context=context):
            text = template.render(**context)
            return literal(text)


class PackagePathLoader(jinja2.BaseLoader):

    def __init__(self):
        self.fs_loader = jinja2.FileSystemLoader(['/'])

    def get_source(self, environment, template):
        if ':' not in template:
            raise TemplateNotFound(template)
        package, path = template.split(':')
        filename = pkg_resources.resource_filename(package, path)
        return self.fs_loader.get_source(environment, filename)
