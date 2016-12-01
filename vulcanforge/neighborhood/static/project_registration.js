/*globals jQuery*/

(function ($) {
    "use strict";

    var manual_override = false,
        $name_avail_message = $('#name_availablity'),
        $name_input = $('input[name="project_name"]'),
        $unixname_input = $('input[name="project_unixname"]'),
        apiRoot = $name_input.attr("data-apiroot") || "",
        handle_name_taken = function (message) {
            if (message) {
                $name_avail_message.html(message);
                $name_avail_message.removeClass('success');
                $name_avail_message.addClass('error');
            } else {
                $name_avail_message.html('This name is available.');
                $name_avail_message.removeClass('error');
                $name_avail_message.addClass('success');
            }
            $('div.error').hide();
            $name_avail_message.show();
        };

    $name_input.blur(function () {
        var project_name = $(this).val();
        if (manual_override === false && project_name) {
            $.getJSON(
                apiRoot + 'suggest_name',
                {'project_name': project_name},
                function (result) {
                    $unixname_input.val(result.suggested_name);
                    handle_name_taken(result.message);
                }
            );
        }
    });

    $unixname_input.change(function () {
        manual_override = true;
        $.getJSON(
            apiRoot + 'check_name',
            {'project_name': $unixname_input.val()},
            function (result) {
                handle_name_taken(result.message);
            }
        );
    });

}(jQuery));