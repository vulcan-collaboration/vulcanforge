# -*- coding: utf-8 -*-
from vulcanforge.common.widgets.util import LightboxWidget
from vulcanforge.resources.widgets import JSScript


class CreatePageWidget(LightboxWidget):

    def resources(self):
        for r in super(CreatePageWidget, self).resources():
            yield r
        yield JSScript('''$(function () {
            var validPageName = false,
                $form = $('#lightbox_create_wiki_page form'),
                $submit = $('#newPageFormSubmit'),
                $invalidMessage = $('<p>This is a reserved name</p>').
                    hide().
                    insertBefore($submit);
            $form.
                bind('keyup', function () {
                    var $el = $('#newPageFormName'),
                        pageName = $el.val(),
                        invalidNames = /^(index|new_page|browse_pages|browse_tags|markdown_syntax|feed)$/;
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
                    if (!validPageName) {
                        e.preventDefault();
                        e.stopPropagation();
                        return false;
                    }
                    location.href=$('#sidebar a.add_wiki_page').attr('href')+encodeURIComponent($('input[name=name]', $(this)).val())+'/edit';
                    return false;
                });
        });''')
