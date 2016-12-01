import logging

from pylons import tmpl_context as c, app_globals as g
from ew import jinja2_ew

from vulcanforge.common.validators import ObjectIdValidator
from vulcanforge.common.widgets.forms import ForgeForm
from vulcanforge.project.model import AppConfig

LOG = logging.getLogger(__name__)


class ArtifactImportForm(ForgeForm):
    submit_text = 'Import'
    style = "wide"

    @property
    def fields(self):
        projects = {p._id: p.name for p in c.user.my_projects()}
        query = {
            "project_id": {"$in": projects.keys()},
            "tool_name": c.artifact_config["tool_name"]
        }
        opts = []
        for ac in AppConfig.query.find(query):
            if g.security.has_access(ac, 'write'):
                opts.append(
                    jinja2_ew.Option(
                        py_value=str(ac._id),
                        label="{} in {}".format(
                            ac.options.mount_label, projects[ac.project_id])
                    )
                )
        fields = [
            jinja2_ew.FieldSet(
                fields=[
                    jinja2_ew.SingleSelectField(
                        label="Import Into Tool",
                        name="app_config_id",
                        options=opts,
                        validator=ObjectIdValidator()
                    ),
                    jinja2_ew.HiddenField(
                        name="node_id",
                        validator=ObjectIdValidator()
                    )
                ]
            )
        ]
        return fields
