import ew as ew_core
import ew.jinja2_ew as ew

from vulcanforge.common.widgets.forms import ForgeForm
from .validators import UniqueOAuthApplicationName


class OAuthApplicationForm(ForgeForm):
    submit_text = 'Register new application'
    style = 'wide'

    class fields(ew_core.NameList):
        application_name = ew.TextField(label='Application Name',
            validator=UniqueOAuthApplicationName())
        application_description = ew.TextArea(label='Application Description')


class OAuthRevocationForm(ForgeForm):
    submit_text = 'Revoke Access'
    fields = []

    class fields(ew_core.NameList):
        _id = ew.HiddenField()
