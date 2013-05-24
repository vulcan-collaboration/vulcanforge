/**
 * project-widgets
 *
 * :author: tannern,wgaggioli
 * :date: 12/7/11,7/24/12
 */

(function($) {
    "use strict";

    $(function () {
        /*
         * Project Summary
         */
        $('.projectSummary:has(.title a)')
            .css('cursor', 'pointer')
            .bind('click', function (e) {
                var link = $('.title a', $(this)),
                    href = link.attr('href'),
                    target = link.attr('target');
                if (e.which === 1) {
                    if (target === undefined) {
                        window.location.href = href;
                    }
                    else {
                        window.open(href, target);
                    }
                }
                else if (e.which === 2) {
                    window.open(href, '_blank');
                }
            });

        $('.cancel-project').click(function() {
            var url = $(this).attr("href"),
                row = $(this).parents('.projectSummary').first(),
                go = confirm($(this).text() + "?");
            if (go === true){
                $(this).remove();
                $.post(url, {
                    _session_id:$.cookie('_session_id')
                }, function(response) {
                    if (response.error){
                        alert(response.error);
                    } else {
                        window.location.reload(true);
                    }

                }, 'json');
            }
            return false;
        });
    });
}(jQuery));
