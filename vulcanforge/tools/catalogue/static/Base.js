/**
 * Core module for Versioned Item.
 *
 * @author Papszi
 * @module $catalogue
 */

var $catalogue = $catalogue || {
    tbPanel: null
};

(function (global) {
    "use strict";

    // Import Globals

    var $ = global.jQuery,
        isSet = global.isSet,
        $tb = global.$tb,
        trace = global.trace,
        $vf = global.$vf;

    $catalogue.baseProperties = {};
    $catalogue.features = {};
    $catalogue.versionedItemSL = {};
    $catalogue.versionedItemId = undefined;

    // Utility Functions

    /**
     * Initializes the webflash functionality to display status messages as
     * user feedback in the top right corner of screen
     *
     * @method webflash
     * @namespace $catalogue
     */
    $catalogue.webflash = function (options) {
        var opts = $.extend({}, $catalogue.webflash.defaults, options);
        if ($.cookie('webflash')) {
            var flash_message = JSON.parse($.cookie('webflash'));
            var messagesEl = $("#" + opts.messagesId);

            messagesEl.notify(flash_message.message, {
                    status: flash_message.status,
                    timer: opts.timer
                }
            );

            $.cookie('webflash', null, {
                path: '/'
            });
        }
    };

    $catalogue.webflash.defaults = {
        messagesId: "messages",
        timer: 4000
    };

    /**
     * Utility function for ordering lists of propertydescriptors.
     *
     * @method sortBySortName
     * @namespace $catalogue
     *
     * @param {Object} a Data structure representing a PropertyDescriptor.
     * @param {Object} b Data structure representing a PropertyDescriptor.
     */
    $catalogue.sortBySortName = function (a, b) {
        if (a.sort_name && b.sort_name) {
            var x = a.sort_name.toLowerCase();
            var y = b.sort_name.toLowerCase();
            return ((x < y) ? -1 : ((x > y) ? 1 : 0));
        }
    };

    $catalogue.calculateBundleSize = function(sizeInBytes){
        var quantity = ' KB';
        var size = sizeInBytes / 1000;
        if (sizeInBytes / 1000 / 1000 > 1){
            quantity = ' MB';
            size = sizeInBytes / 1000 / 1000;
        }
        var roundedSize = Math.round(100 * size) / 100;

        return roundedSize + quantity;
    };

    $catalogue.deleteItem = function(versionedItemType, itemDeleteUrl, afterDeleteUrl) {
        var go = confirm("Are you certain you want to delete this "+versionedItemType+"?");
        if (go === true) {
            $.ajax({
                url: itemDeleteUrl,
                type: "DELETE",
                headers: {VFSessionID: $.cookie('_session_id')},
                dataType: 'json',
                context: this,
                complete: function () {
                },
                success: function (response) {
                    var url = response.location ? response.location : afterDeleteUrl;
                    $catalogue.webflash();
                    window.location.href = url;
                },
                error: $catalogue.ajaxErrorHandler
            });
        }
        return false;
    };

    $catalogue.ajaxErrorHandler = function (jqXHR, textStatus, errorThrown) {
        var alertParams = {
            title: 'Action could not be performed.',
            message: null
        };
        if (jqXHR.responseText) {
            try{
                var responseData = JSON.parse(jqXHR.responseText);
                if (responseData.detail) {
                    alertParams.message = responseData.detail;
                }
            } catch(err){
                alertParams.message = jqXHR.responseText;
            }
        }
        if (alertParams.message == null) {
            alertParams.message = errorThrown;
        }
        $catalogue.alert(alertParams);
    };

    $catalogue.alert = function (opt) {
        var message = typeof(opt) == 'string' ? opt : '';
        if (opt.title != undefined) {
            message += opt.title + '\n\n';
        }
        if (opt.message != undefined) {
            message += opt.message;
        }
        if (message.length > 0) {
            return alert(message);
        }
    };

    $(function () {
        $('.validation-container-errors, .validation-container-warnings').
            on('click', function (e) {
                $(this).
                    find('ul').
                    slideToggle();
            });
    });

}(window));

