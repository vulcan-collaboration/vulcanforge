import logging

import ew
from ew.core import validator
from formencode import validators, Invalid

from vulcanforge.common.widgets.forms import ForgeForm

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:visualize/manage_tool/templates/widgets/'


class VisualizerUploadForm(ForgeForm):
    template = TEMPLATE_DIR + 'add_visualizer.html'

    class fields(ew.NameList):
        archive = ew.FileField(
            label="Upload a Zip File",
            validators=validators.FieldStorageUploadConverter(not_empty=True))

    @validator
    def validate(self, value, state=None):
        if value['archive'] == u'':
            raise Invalid(u'Please upload a file', dict(archive=u''), None)
        return value
