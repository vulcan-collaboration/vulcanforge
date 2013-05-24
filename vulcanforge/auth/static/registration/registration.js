/*globals $ */

$(function() {
    "use strict";

    var $username_field = $('#username_field'),
        $username_status = $('#username_status'),
        $any_input_field = $('input');

    function usernameChanged () {
        var value = $username_field.val();

        $.getJSON('/auth/username_available',
            { username: value },
            function (data) {
                var status = $username_status.text(data.status);

                if (data.status === '') {
                    status.hide();
                } else {
                    status.show();
                }

                if (data.available) {
                    status.addClass("available");
                    status.removeClass("unavailable");
                }
                else {
                    status.addClass("unavailable");
                    status.removeClass("available");
                }
            });
    }

    function removeError() {
        var fieldErrors = $('.fielderror', $(this).parent());
        fieldErrors.remove();
    }

    $username_field
        .bind('keyup', usernameChanged)
        .bind('change', usernameChanged);

    $any_input_field
        .bind('keyup', removeError)
        .bind('change', removeError);

});