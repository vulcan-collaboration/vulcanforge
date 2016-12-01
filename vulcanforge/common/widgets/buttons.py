import ew

TEMPLATE_DIR = 'jinja:vulcanforge:common/templates/widgets/'


class ButtonWidget(ew.Widget):
    """A button on screen"""
    template = TEMPLATE_DIR + 'button.html'

    def display(self, label=None, elementId=None, css=None, icon=None,
                action=None, type=None, **kw):

        return ew.Widget.display(self,
            label = label,
            type = type or 'button',
            elementId = elementId,
            class_str = " ".join([
                css or '', icon and ('%s has-icon' % icon ) or '']),
            action = action,
            **kw
        )


class IconButtonWidget(ew.Widget):
    """A button on screen"""
    template = TEMPLATE_DIR + 'icon_button.html'

    def display(self, label=None, elementId=None, className=None, icon=None,
                action=None, href=None, **kw):
        classes = []
        if icon:
            classes.append('{} icon'.format(icon))
        if className:
            classes.append(className)
        return ew.Widget.display(
            self, label=label, href=href, elementId=elementId,
            class_str=" ".join(classes), action=action, **kw)
