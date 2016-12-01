# -*- coding: utf-8 -*-
from pylons import tmpl_context as c, app_globals as g

from vulcanforge.artifact.widgets import (
    ArtifactMenuBar,
    BaseArtifactRenderer,
    LabelListWidget
)
from vulcanforge.common.widgets.form_fields import AttachmentList
from vulcanforge.common.widgets.util import LightboxWidget
from vulcanforge.resources.widgets import JSScript


class PageRenderer(BaseArtifactRenderer):
    template = 'wiki/widgets/page.html'
    widgets = {
        "attachment_list": AttachmentList(),
        "label_list": LabelListWidget()
    }

    def display(self, artifact, **kw):
        page_html = artifact.get_rendered_html()
        return super(PageRenderer, self).display(
            artifact, page_html=page_html, **kw)


class CreatePageWidget(LightboxWidget):

    def resources(self):
        for r in super(CreatePageWidget, self).resources():
            yield r
        yield JSScript('''$(function () {
            var validPageName = false,
                $form = $('#lightbox_create_wiki_page form'),
                $nameField = $('#newPageFormName'),
                $submit = $('#newPageFormSubmit'),
                $invalidMessage = $('<p>This is a reserved name</p>').
                    hide().
                    insertBefore($submit);
            $form.
                bind('keyup', function () {
                    var $el = $('#newPageFormName'),
                        pageName = $el.val(),
                        invalidNames = /^(index|browse_pages|browse_tags|markdown_syntax|feed)$/;
                    if (!pageName.match(invalidNames)) {
                        $el.removeClass("invalid");
                        validPageName = true;
                        $invalidMessage.hide();
                        $submit.show();
                    } else {
                        $el.addClass("invalid");
                        validPageName = false;
                        $invalidMessage.show();
                        $submit.hide();
                    }
                }).
                submit(function(e){
                    var pageTitle;
                    if (!validPageName) {
                        e.preventDefault();
                        e.stopPropagation();
                        return false;
                    }
                    pageTitle = encodeURIComponent($('input[name=name]', $(this)).val()).replace('%2F', '/');
                    location.href=$('#sidebar a.add_wiki_page').attr('href')+pageTitle+'/edit';
                    return false;
                });
            $nameField.autocomplete({
                source: function(request, callback) {
                    $.ajax({
                        url: "''' + c.app.url + '''/title_autocomplete",
                        data: {q: request.term},
                        success: function (data, status, request) {
                            var i;
                            for (i = 0; i < data.results.length; ++i) {
                                data.results[i] += '/';
                            }
                            callback(data.results);
                        }
                    });
                }
            });
        });''')


class WikiPageMenuBar(ArtifactMenuBar):
    def display(self, artifact, is_editing=False, **kw):
        buttons = []
        feed_url = None
        disable_publish = False
        allow_write = g.security.has_access(artifact, 'write')
        is_current = artifact.is_current()
        if artifact.deleted:
            disable_publish = True
            if allow_write:
                undelete_btn = g.icon_button_widget.display(
                    'Undelete', None, 'post-link', 'ico-undelete',
                    href=artifact.original_url() + 'undelete')
                buttons.append(undelete_btn)
        else:
            if is_editing:
                view_btn = g.icon_button_widget.display(
                    'View Page', None, None, 'ico-preview',
                    href=artifact.url())
                buttons.append(view_btn)
            elif allow_write:
                if is_current:
                    edit_btn = g.icon_button_widget.display(
                        'Edit', None, None, 'ico-edit',
                        href=artifact.original_url() + 'edit')
                else:
                    edit_btn = g.icon_button_widget.display(
                        'Revert to version {}'.format(artifact.version),
                        'revert_{}'.format(artifact.version), 'post-link',
                        'ico-undo',
                        href="./revert?version={}".format(artifact.version))
                buttons.append(edit_btn)
            if allow_write and is_current and \
                            c.app.root_page_name != artifact.title:
                delete_btn = g.icon_button_widget.display(
                    'Delete (can be undone)', None, 'post-link', 'ico-delete',
                    href=artifact.original_url()+'delete')
                buttons.append(delete_btn)
            hist_btn = g.icon_button_widget.display(
                'History', None, None, 'ico-history',
                href=artifact.original_url() + 'history')
            buttons.append(hist_btn)
        if is_current:
            feed_url = artifact.original_url() + 'feed'
        return super(WikiPageMenuBar, self).display(
            artifact, buttons, feed_url, disable_publish=disable_publish)