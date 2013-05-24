/*global window*/

/*
 * Initializing markup-edit stuff.
 *
 * @author Naba Bana
 */
(function (global) {
    "use strict";

    // Local globals
    var $ = global.$,
        contentAreasWrapper = $('#content-areas-wrapper'),
        oldContentAreaWrapperPosition,
        $closeButton = $('<div/>', {
            "class": "icon ico-close close",
            title: 'Close Markdown Help'
        });

    $(function() {

        if(!global.markdown_init){
            global.markdown_init = true;

            var helpArea = null,
                helpPanelOpener = function(evt){
                    evt.preventDefault();
                    if (!helpArea){
                        $.ajax({
                            url: '/nf/markdown_syntax',
                            type: "GET",
                            success: function(response){
                                helpArea = $('<div/>', {
                                    "class": "modal markdown-help"
                                }).append( $closeButton ).css("display", "none")
                                    .append(response);

                                oldContentAreaWrapperPosition = contentAreasWrapper.css('position');
                                contentAreasWrapper.css('position', 'fixed');

                                helpArea.lightbox_me({
                                    centered: true,
                                    overlayCSS: {
                                        position: 'fixed',
                                        background: 'black',
                                        opacity: .3
                                    },
                                    onClose: function () {
                                        contentAreasWrapper.css('position', oldContentAreaWrapperPosition);
                                    }
                                });
                            }
                        });
                    } else{

                        oldContentAreaWrapperPosition = contentAreasWrapper.css('position');
                        contentAreasWrapper.css('position', 'fixed');

                        helpArea.lightbox_me({
                            onClose: function () {
                                contentAreasWrapper.css('position', oldContentAreaWrapperPosition);
                            }
                        });
                    }
                };



            $('.markdown-help-button').click(helpPanelOpener);
            $('#sidebarmenu-item-markdown-syntax a.nav_child').click(helpPanelOpener);

            var isScrolledIntoView = function (elem) {
                var docViewTop = $(window).scrollTop();
                var docViewBottom = docViewTop + $(window).height();

                var elemTop = $(elem).offset().top;
                var elemBottom = elemTop + $(elem).height();

                return ((elemBottom <= docViewBottom) && (elemTop >= docViewTop));
            };


            $('div.markdown-edit').each(function(){
                var $container = $(this);

                $container.tabs({selected: 0});

                var $textarea = $('textarea', $container);
                $textarea.tabby({tabString : "    "});
                var $preview = $('a.markdown-preview-button', $container);
                var $edit = $('a.markdown-edit-button', $container);
                //var $edit = $('a.markdown-edit-button', $container);
                var $preview_area = $('div.markdown-preview', $container);
                var $formControls = $('.form-controls');
                var exitPreviewButton = $('.exit-preview-button', $container).remove().removeClass('hidden');
                var $form = $('form', $container.parents());

                exitPreviewButton.click(function() {
                    $edit.click();
                });

                if ($formControls) {
                    exitPreviewButton.hide();
                }

                $preview.click(function(evt){
                    $preview_area.html('');
                    $preview_area.addClass('waiting-on-something');
                    evt.preventDefault();
                    var cval = $.cookie('_session_id');

                    if ($formControls) {
                        $formControls.prepend(exitPreviewButton);
                        exitPreviewButton.show();
                    }

                    $.post('/nf/markdown_to_html', {
                        markdown:$textarea.val(),
                        project:$('input.markdown_project', $container).val(),
                        app:$('input.markdown_app', $container).val(),
                        _session_id:cval

                    },
                    function(resp){
                        $preview_area.html(resp);
                        $preview_area.removeClass('waiting-on-something');

                        if ($formControls && !isScrolledIntoView($formControls)) {
                            $form.addClass('fix-controls');
                        }

                    });
                });

                $edit.click(function() {
                    if (exitPreviewButton) {
                        exitPreviewButton.hide();
                        $form.removeClass('fix-controls');
                    }
                });
            });

            $('.markdown-tabs').fadeIn('slow');
        }
    });
}(window));