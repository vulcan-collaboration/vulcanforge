/**
 * Client side infrastructure for rendering versioned items.
 *
 * NOTE: It shall be integrated into DMD visualizer code and will be replaced.
 *
 * @author Papszi
 *
 */

var $catalogue = $catalogue || {};

(function (global) {
    "use strict";

    // Import Globals

    var $ = global.jQuery,
        trace = global.trace,
        $vf = global.$vf;

    /**
     * Main class for displaying versioned items.
     *
     * @class Presenter
     * @namespace $catalogue
     * @constructor
     *
     */
    $catalogue.Presenter = function (config) {
        this.options = $.extend(true, {}, this.options, config);

        this.propertiesHolder = $('#itemProperties');

        var config = {mode:'DISPLAY'};
        $catalogue.baseProperties.config(config);
        $.each($catalogue.features, function (featureName, feature) {
            feature.config(config);
        });

    };

    $catalogue.Presenter.prototype = {

        // default options
        options: {},

        // Data structures
        versionedItemId: null,

        // UI elements
        propertiesHolder: null,
        propertyWidgets: null,
        pleaseWait: null,

        loadVersionedItemInfo: function (id) {

            if (this.pleaseWait) {
                this.pleaseWait.update("Rendering item properties...");
            } else {
                this.pleaseWait = new $vf.PleaseWait("Rendering item properties...",
                    $("#itemContainer"));
            }

            this.pleaseWait.show();

            $.ajax({
                url: $catalogue.versionedItemSL.url,
                type: "GET",
                data: {},
                dataType: "json",
                context: this,
                complete: function () {
                },
                success: function (result) {
                    this.itemInfoLoaded(result);
                },
                error: $catalogue.ajaxErrorHandler
            });

        },

        itemInfoLoaded: function (response) {
            var i;
            var pDescriptor;
            var widget;
            var $testingStatusWidget;
            this.versionedItemId = response._id;

            $catalogue.baseProperties.setValues(response, true);
            $.each($catalogue.features, function (featureName, feature) {
                feature.setValues(response[featureName], true);
            });

            this.renderPropertyList();
            this.pleaseWait.hide();
        },


        renderPropertyList: function () {
            $catalogue.baseProperties.render();
            $.each($catalogue.features, function (featureName, feature) {
                feature.render();
            });
            this.propertiesHolder.show();
        }

    };

}(window));
