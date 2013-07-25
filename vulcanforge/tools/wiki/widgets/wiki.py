# -*- coding: utf-8 -*-
from pylons import tmpl_context as c

from vulcanforge.common.widgets.util import LightboxWidget
from vulcanforge.resources.widgets import JSScript


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
