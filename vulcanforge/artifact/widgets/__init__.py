import logging
import ew
import random
import string

from vulcanforge.resources.widgets import Widget
from vulcanforge.visualize.model import Visualizer

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:artifact/templates/widgets/'


def short_artifact_link_data(artifact):
    data = {
        'label': artifact.link_text_short(),
        'fullLabel': artifact.link_text(),
        'refId': artifact.index_id(),
        'clickURL': artifact.url(),
        'shortLink': '[{}:{}:{}]'.format(
            artifact.project.shortname,
            artifact.app_config.options.mount_point,
            artifact.shorthand_id()
        ),
        'artifactType': artifact.type_s
    }
    if data['artifactType'] == "Blob":
        visualizers = Visualizer.get_for_resource(artifact.name)
        if visualizers:
            data['iconURL'] = visualizers[0].icon_url
    return data


class GenericArtifactLink(ew.Widget):
    template = TEMPLATE_DIR + 'referencelink.html'


class VFArtifactLink(ew.Widget):
    template = TEMPLATE_DIR + 'vfartifactlink.html'

    def display(self, value=None, extra=None, url=None,
                artifact_type=None, tag="div", label=None, **kw):
        if label is None:
            label = value.link_text_short()
        if url is None:
            url = value.url()
        if artifact_type is None:
            artifact_type = value.type_s
        return super(VFArtifactLink, self).display(
            value=value, url=url, extra=extra, label=label, id=id,
            artifact_type=artifact_type, tag=tag, **kw
        )


class TreeReferenceLink(VFArtifactLink):
    pass


class FileReferenceLink(VFArtifactLink):

    def display(self, value=None, icon_url=None, **kw):
        if icon_url is None:
            visualizers = Visualizer.get_for_resource(value.name)
            if visualizers:
                icon_url = visualizers[0].icon_url
        return VFArtifactLink.display(
            self, value=value, icon_url=icon_url, **kw)


class ArtifactLink(ew.Widget):
    """A link to an artifact"""
    widgets = dict(
        folder=TreeReferenceLink(),
        file=FileReferenceLink(),
        generic=VFArtifactLink()
    )

    def display(self, value=None, **kw):
        widget = self.widgets[value.link_type]
        return widget.display(value=value, **kw)


class RelatedArtifactsWidget(Widget):
    """Unordered List of all artifacts relating to an artifact"""
    template = TEMPLATE_DIR + 'relatedartifacts.html'
    js_template = '''
    $('#sidebar_search_submit').hide();

    $vf.afterInit(function() {

        var infoPanel = new $vf.ArtifactInfoPanel({
            parentClickURL: '',
            infoURL: '/artifact_ref/get_references/',
            refId: '{{ref_id}}',
            {% if hiding %}
            infoTriggerE: $("#{{id_prefix}}giantInfoButtonE")
            {% else %}
            containerE: $('#{{id_prefix}}relatedArtifactsPanelHolder'),
                    embedded: true
            {% endif %}
        });

    }, []);
    '''
    defaults = dict(
        ew.Widget.defaults,
        value=None
    )
    widgets = dict(
        link=ArtifactLink()
    )

    def prepare_context(self, context):
        c = super(RelatedArtifactsWidget, self).prepare_context(context)
        c['reference_link_widget'] = self.widgets['link']
        return c

    def display(self, value=None, **kw):
        return Widget.display(
            self,
            value=value,
            hiding=value.type_s == 'Post',
            ref_id=value.index_id(),
            id_prefix=''.join(random.sample(string.ascii_uppercase, 8)),
            **kw
        )


class LabelListWidget (Widget):
    template = TEMPLATE_DIR + 'label_list.html'
    defaults = dict(
        ew.Widget.defaults,
        artifact=None,
    )
