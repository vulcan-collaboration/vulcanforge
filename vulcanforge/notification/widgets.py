# -*- coding: utf-8 -*-
import ew
from vulcanforge.resources.widgets import CSSLink

TEMPLATE_DIR = 'jinja:vulcanforge:notification/templates/widgets/'


class ActivityFeedItemWidget(ew.Widget):
    template = TEMPLATE_DIR + 'activity_feed_item.html'
    defaults = dict(
        ew.Widget.defaults,
        notification=None,
        project_icon=True,
        author_icon=False,
        show_text=False
    )

    def resources(self):
        yield CSSLink('notification/activity_feed.css')

    def prepare_context(self, context):
        context = super(ActivityFeedItemWidget, self).prepare_context(context)
        notification = context.get('notification', None)
        artifact = notification.get_artifact()
        if artifact is not None:
            thread = artifact.get_discussion_thread(generate_if_missing=False)
            context = dict(
                context,
                artifact=artifact,
                comment_count=getattr(thread, 'num_replies', 0)
            )
        return context


class ActivityFeed(ew.Widget):
    template = TEMPLATE_DIR + 'activity_feed.html'
    defaults = dict(
        ew.Widget.defaults,
        notifications=None,
        project_icon=True,
        author_icon=False,
        show_text=False
    )

    class widgets:
        activity_feed_item = ActivityFeedItemWidget()

    def resources(self):
        yield CSSLink('notification/activity_feed.css')

    def prepare_context(self, context):
        context = super(ActivityFeed, self).prepare_context(context)
        return dict(context,
            activity_feed_item=self.widgets.activity_feed_item
        )
