(function ($) {
    'use strict';

    var setState = function ($el, state) {
            $el.toggleClass('off', !state).toggleClass('on', state);
            console.log($el.attr('id'), state);
        };

    $(function () {

        var $password = $('input[name="password"]'),
            minLength = window.parseInt($('#pwLength').attr('data-length')),
            lowercase = window.parseInt($('#pwLower').attr('data-length')),
            uppercase = window.parseInt($('#pwUpper').attr('data-length')),
            numbers = window.parseInt($('#pwNumber').attr('data-length')),
            specials = window.parseInt($('#pwSpecial').attr('data-length'));

        var update = function () {
            var pw = $(this).val();

            setState($('#pwLength'), pw.length >= minLength);
            setState($('#pwLower'), pw.match(/[a-z]/g) !== null && pw.match(/[a-z]/g).length >= lowercase);
            setState($('#pwUpper'), pw.match(/[A-Z]/g) !== null && pw.match(/[A-Z]/g).length >= uppercase);
            setState($('#pwNumber'), pw.match(/[\d]/g) !== null && pw.match(/[\d]/g).length >= numbers);
            setState($('#pwSpecial'), pw.match(/[\W_]/g) !== null && pw.match(/[\W_]/g).length >= specials);
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
