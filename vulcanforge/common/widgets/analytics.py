import ew


class GoogleAnalytics(ew.Widget):
    template = 'jinja:vulcanforge:common/templates/widgets/analytics.html'
    defaults = dict(
        ew.Widget.defaults,
        account='UA-XXXXX-X')
