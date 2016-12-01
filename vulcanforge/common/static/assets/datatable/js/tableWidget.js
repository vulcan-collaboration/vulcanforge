/* globals window, jQuery */

(function ($) {
    "use strict";

    var TableWidget = function (containerE, opts) {

        var that = this,
            defaultOpts = {
                bDownloadToolbar: true
            },
            extIndex;


        this.oTable = null;

        opts = $.extend({}, defaultOpts, opts);
        if (!opts.hasOwnProperty("sDownloadUrl") && opts.hasOwnProperty('sAjaxSource')) {
            extIndex = opts.sAjaxSource.lastIndexOf('.');
            opts.sDownloadUrl = extIndex === -1 ? opts.sAjaxSource : opts.sAjaxSource.substring(0, extIndex);
        }

        function initTable(tableOptions) {
            var sTitle = opts.sTitle,
                tableE = $('<table>', {
                    cellpadding: "0",
                    cellspacing: "0",
                    border: "0",
                    "class": "bordered-table zebra-striped",
                    id: 'dataTableWidget_' + sTitle.toLowerCase()
                }),
                toolbarE,
                toolbarContent;

            if (tableOptions === undefined) {
                tableOptions = opts;
            }

            tableE.appendTo(containerE);

            that.oTable = tableE.dataTable(opts);

            // add title
            toolbarE = tableE.siblings('.toolbar');
            toolbarContent = $('<h4/>', {
                "class": "span12 text-left",
                "text": sTitle
            });

            if (opts.bDownloadToolbar){
                toolbarContent.append(
                    $('<div/>', {
                        "class": "btn-group pull-right"
                    })
                ).append(
                    $('<a/>', {
                        "class": "btn",
                        "href": opts.sDownloadUrl + '.csv',
                        "text": "Download as CSV"
                    })
                ).append(
                    $('<a/>', {
                        "class": "btn",
                        "href": opts.sDownloadUrl + '.json',
                        "text": "Download as JSON"
                    })
                );
            }

            toolbarContent.appendTo(toolbarE);
        }

        function renderData(data) {
            opts.aaData = opts.aaData || data.aaData;
            opts.aoColumns = opts.aoColumns || data.aoColumns;

            initTable(opts);
        }

        function getDataFromUrl(url) {
            var i = url.lastIndexOf('/') + 1,
                filename = url.substring(i, url.lastIndexOf('.'));
            opts.sTitle = opts.sTitle || filename;
            opts.sDownloadUrl = opts.sDownloadUrl || url.substring(0, i);

            $.getJSON(url, null, function (data) {
                renderData(data);
            });
        }

        if (opts.hasOwnProperty('sDataSource')) {
            getDataFromUrl(opts.sDataSource);
        } else if (opts.hasOwnProperty('fnDataSource')) {
            opts.fnDataSource(renderData);
        } else {
            initTable(opts);
        }

    };

    window.TableWidget = TableWidget;

}(jQuery));