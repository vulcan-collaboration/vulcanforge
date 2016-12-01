/**
 * subscriptions.js
 *
 * :author: tannern
 * :date: 5/11/12
 */
(function ($) {
    'use strict';

    $(function () {
        // digest settings
        $('input.mailbox_type[value="digest"]').
            bind('change', function () {
                $(this).closest('tr').
                    find('.digest-settings').
                    toggle($(this).is(':checked'));
            }).
            trigger('change');
        $('input.mailbox_type[value!="digest"]').
            bind('change', function () {
                $(this).closest('tr').
                    find('.mailbox_type[value="digest"]').
                    trigger('change');
            });

        // collapsible sections
        $('.subscription-header').
            bind('click', function () {
                $(this).
                    closest('.subscription-container').
                    toggleClass('open').
                    find('.subscription-content').
                    slideToggle();
            }).
            each(function () {
                var $container = $(this).
                    closest('.subscription-container');
                $container.
                    find('.subscription-content').
                    toggle($container.hasClass('open'));
            });

        // disable controls
        $('.subscription-row').
            bind('refresh-row', function () {
                var disabled = $(this).
                    has('input[type="checkbox"]:checked').
                    length == 0;
                $(this).
                    find('input[type!="checkbox"], select').
                    not('input[type="hidden"]').
                    attr('disabled', disabled);
            }).
            trigger('refresh-row').
            find('input[type="checkbox"]').
            bind('change', function () {
                $(this).
                    closest('.subscription-row').
                    trigger('refresh-row');
            });
    });

}(jQuery));
