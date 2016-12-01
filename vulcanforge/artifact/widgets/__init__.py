import logging
import ew
import random
import string
from markupsafe import Markup

from pylons import app_globals as g, tmpl_context as c

from vulcanforge.resources.widgets import Widget

LOG = logging.getLogger(__name__)
TEMPLATE_DIR = 'jinja:vulcanforge:artifact/templates/widgets/'


def short_artifact_link_data(artifact):
    data = {
        'label': artifact.link_text_short(),
        'fullLabel': artifact.link_text(),
        'refId': artifact.index_id(),
        'clickURL': Markup(artifact.url()),
        'shortLink': '[{}:{}:{}]'.format(
            artifact.project.shortname,
            artifact.app_config.options.mount_point,
            artifact.shorthand_id()
        ),
        'artifactType': artifact.type_s
    }
    if data['artifactType'] == "Blob":
        visualizer = g.visualize_artifact(artifact).get_visualizer()
        if visualizer:
            data['iconURL'] = visualizer.icon_url
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
            visualizer = g.visualize_url(value.name).get_visualizer()
            if visualizer:
                icon_url = visualizer.icon_url
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
        ctx = super(RelatedArtifactsWidget, self).prepare_context(context)
        ctx['reference_link_widget'] = self.widgets['link']
        return ctx

    def display(self, value=None, **kw):
        return Widget.display(
            self,
            value=value,
            hiding=value.type_s == 'Post',
            ref_id=value.index_id(),
            id_prefix=''.join(random.sample(string.ascii_uppercase, 8)),
            **kw
        )


class LabelListWidget(Widget):
    template = TEMPLATE_DIR + 'label_list.html'
    defaults = dict(
        ew.Widget.defaults,
        artifact=None,
    )


class ArtifactMenuBar(Widget):
    template = TEMPLATE_DIR + 'menu_bar.html'

    def display(self, artifact, buttons=None, feed_url=None, app_config=None,
                disable_publish=False, **kwargs):
        if buttons is None:
            buttons = []
        if feed_url and c.user and not c.user.is_anonymous:
            feed_btn = g.subscription_popup_menu.display(
                artifact=artifact, feed_url=feed_url)
            buttons.append(feed_btn)

        # publish button for exchange artifacts
        if app_config is None:
            app_config = c.app.config

        # TODO: add subtext for multiple exchanges
        if not disable_publish:
            exchanges = g.exchange_manager.get_exchanges(app_config, artifact)
            for exchange, artifact_config in exchanges:
                if artifact_config["publish_url"] and g.security.has_access(
                        artifact, 'publish'):
                    url = artifact_config["publish_url"]
                    if '?' in url:
                        url += '&artifact_id={}'.format(artifact._id)
                    else:
                        url += '?artifact_id={}'.format(artifact._id)
                    xcng_btn = g.icon_button_widget.display(
                        label='Share in {}'.format(exchange.config["name"]),
                        icon=artifact_config.get('publish_icon', 'ico-share'),
                        href=url
                    )
                    buttons.append(xcng_btn)

        return super(ArtifactMenuBar, self).display(buttons=buttons, **kwargs)


class BaseArtifactRenderer(Widget):
    widgets = {}
    defaults = dict(
        Widget.defaults,
        is_exchange=False
    )

    def prepare_context(self, context):
        response = super(BaseArtifactRenderer, self).prepare_context(context)
        response['widgets'] = self.widgets
        return response

    def display(self, artifact, **kw):
        return super(BaseArtifactRenderer, self).display(
            artifact=artifact, **kw)
