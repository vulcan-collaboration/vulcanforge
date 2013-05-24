from pylons import tmpl_context as c
from tg import request
import ew as ew_core
import ew.jinja2_ew as ew

from vulcanforge.common.widgets.form_fields import SubmitButton
from vulcanforge.common.validators import MingValidator
from vulcanforge.notification.model import Mailbox

TEMPLATE_DIR = 'jinja:vulcanforge:artifact/templates/widgets/'


class _MeasurementField(ew.FieldSet):
    template = 'jinja:vulcanforge:common/templates/form/compound-field.html'

    class fields(ew_core.NameList):
        n = ew.IntField(show_label=False)
        unit = ew.SingleSelectField(
            options=Mailbox.frequency.field.schema.fields['unit'].options,
            show_label=False
        )


class _SubscriptionTable(ew.TableField):

    class hidden_fields(ew_core.NameList):
        _id = ew.HiddenField(validator=MingValidator(Mailbox))
        topic = ew.HiddenField()
        artifact_index_id = ew.HiddenField()

    class fields(ew_core.NameList):
        project_name = ew.HTMLField(label='Project', show_label=True)
        mount_point = ew.HTMLField(label='App', show_label=True)
        artifact_title = ew.HTMLField(label='Artifact', show_label=True)
        topic = ew.HTMLField(label='Topic', show_label=True)
        queue = ew.HTMLField(label="# Queued", show_label=True)
        next_scheduled = ew.HTMLField(label="next scheduled", show_label=True)
        type = ew.SingleSelectField(
            label='Type',
            show_label=True,
            options=['direct', 'digest', 'none']
        )
        frequency = _MeasurementField(
            label='Frequency',
            show_label=True
        )
        reset_time = ew.Checkbox(label="reset time",
                                 suppress_label=True,
                                 show_label=True)
        unsubscribe = ew.Checkbox(label="unsubscribe",
                                  suppress_label=True,
                                  show_label=True)


class SubscriptionForm(ew.SimpleForm):
    defaults = dict(
        ew.SimpleForm.defaults,
        submit_text='Save Changes')

    class fields(ew_core.NameList):
        subscriptions = _SubscriptionTable()


class SubscribeForm(ew.SimpleForm):
    template = TEMPLATE_DIR + 'subscribe.html'
    defaults = dict(
        ew.SimpleForm.defaults,
        thing='tool',
        style='text',
        tool_subscribed=False,
        value=None)

    class fields(ew_core.NameList):
        subscribe = SubmitButton()
        unsubscribe = SubmitButton()

    def from_python(self, value, state=None):
        return value


class SubscriptionPopupMenu(ew_core.Widget):
    template = TEMPLATE_DIR + 'subscription_popup_menu.html'
    defaults = dict(
        ew_core.Widget.defaults,
        project=None,
        app_config=None,
        artifact=None)

    def prepare_context(self, context):
        context = super(SubscriptionPopupMenu, self).prepare_context(context)
        c.url = request.url

        artifact = context.get('artifact', None)
        project = context.get('project', getattr(c, 'project', None))
        app_config = context.get('app_config', getattr(c, 'app_config', None))
        if app_config is None:
            app_config = getattr(getattr(c, 'app', None), 'config', None)
        if project is None:
            project = getattr(app_config, 'project', None)
        if artifact is not None:
            project = artifact.project
            app_config = artifact.app_config
        project_id = getattr(project, '_id', None)
        app_config_id = getattr(app_config, '_id', None)
        mailbox = Mailbox.get_subscription(
            user_id=c.user._id,
            project_id=project_id,
            app_config_id=app_config_id,
            artifact=artifact
        )
        return dict(context, artifact=artifact, project=project,
                    app_config=app_config, mailbox=mailbox)
