(function ($) {
    'use strict';

    var setState = function ($el, state) {
            $el.toggleClass('off', !state).toggleClass('on', state);
            console.log($el.attr('id'), state);
        };

    $(function () {

        var $password = $('input[name="password"]'),
            minLength = window.parseInt($('#pwLength').attr('data-length'));

        var update = function () {
            var pw = $(this).val();

            setState($('#pwLength'), pw.length >= minLength);
            setState($('#pwLower'), pw.match(/(?=.*[a-z])/) !== null);
            setState($('#pwUpper'), pw.match(/(?=.*[A-Z])/) !== null);
            setState($('#pwNumber'), pw.match(/(?=.*[\d])/) !== null);
            setState($('#pwSpecial'), pw.match(/(?=.*[\W])/) !== null);
        };
        $password.bind({
            'change': update,
            'keyup': update,
            'blur': update,
            'focus': function() {
                var self = $(this);
                var $passwordRequirements = $('.password-requirements', self.parent());

                if ($passwordRequirements.hasClass('hidden')) {
                    $passwordRequirements.hide();
                    $passwordRequirements.removeClass('hidden');
                    $passwordRequirements.fadeIn();
                }

            }
        });
    });

}(window.jQuery));
