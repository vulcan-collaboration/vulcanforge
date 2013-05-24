/*global window */

(function (global) {
    "use strict";

    // Import Globals
    var $ = global.jQuery,
        trace = global.trace || function (text) {
            window.console.log(text);
        },
        pieOptions = {
            series: {
                pie: {
                    show: true,
                    radius: 1,
                    label: {
                        show: true,
                        radius: 1,
                        formatter: function (label, series) {
                            return '<div style="font-size:8pt;text-align:center;padding:2px;color:white;">' + Math.round(series.percent) + '%</div>';
                        },
                        background: {
                            opacity: 0.7,
                            color: '#000'
                        }
                    },
                    combine: {
                        color: '#aaa',
                        threshold: 0.01
                    }
                },
                legend: {
                    show: true
                }
            }
        },
        barOptions = {};

    $.fn.showManufacturabilityDetails = function (config) {

        function preparePieChartData(dataset, dataKey) {
            var result = [];
            $.each(dataset, function (i, item) {
                result.push({
                    label: item.name,
                    data: item[dataKey]
                });
            });
            result.sort(function (a, b) {
                var aValue = a[dataKey],
                    bValue = b[dataKey];
                return ((aValue < bValue) ? -1 : ((aValue > bValue) ? 1 : 0));
            });
            return result;
        }

        function makePieChart($container, label, dataset, dataKey, options) {
            var $chart = $('<div class="chart-container"/>'),
                chartData = preparePieChartData(dataset, dataKey);
            $container.
                append('<h4 class="chart-title">' + label + '</h4>').
                append($chart);
            $.plot($chart, chartData, options);
        }

        function makeSortFunctionForKey(key) {
            var fn = function (a, b) {
                var valA = a[key],
                    valB = b[key];
                return (valA > valB) ? 1 : (valA < valB) ? -1 : 0
            };
            return fn;
        }

        function makeBarChart($container, label, dataset, dataKey, options) {
            var datasetCopy = Array.apply({}, dataset),
                barData = [],
                lineData = [],
                chartData,
                chartOptions = {
                    xaxis: {
                        ticks: null
                    },
                    yaxes: [
                        {},
                        {
                            min: 0,
                            max: 100,
                            alignTicksWithAxis: 1,
                            position: 'right',
                            tickFormatter: function (v, axis) {
                                return v.toFixed(axis.tickDecimals) + '%';
                            },
                            tickDecimals: 0,
                            tickSize: 20,
                            minTickSize: 20
                        }
                    ]
                },
                $chart = $('<div class="chart-container"/>'),
                chartItemCount = 5,
                totalValue = 0,
                percentSum = 0;
            datasetCopy.sort(makeSortFunctionForKey(dataKey));
            datasetCopy.reverse();
            $.extend(chartOptions, options);
            chartOptions.xaxis.ticks = [];
            $.each(datasetCopy, function () {
                totalValue += this[dataKey];
            });
            $.each(datasetCopy, function (i) {
                var dataVal = this[dataKey],
                    percentVal = dataVal / totalValue * 100;
                percentSum += percentVal;
                if (i < chartItemCount) {
                    chartOptions.xaxis.ticks.push([i, '<span class="chart-long-x-label">' + this.name + '</span>']);
                    barData.push([i - 0.5, dataVal]);
                    lineData.push([i, percentSum]);
                }
            });
            chartData = [
                {
                    data: barData,
                    bars: {show:true}
                },
                {
                    data: lineData,
                    lines: {show:true},
                    yaxis: 2
                }
            ];
            $container.
                append('<h4 class="chart-title">' + label + '</h4>').
                append($chart);
            $.plot($chart, chartData, chartOptions);
        }

        function renderDetails( data, $into ) {
            var $innerContainer = $('<div/>', {
                    'class': 'manufacturability-details-container'
                }),
                $chartContainer = $('<div/>', {
                    'class': 'charts'
                }),
                datasets = {
                    purchased: [],
                    manufactured: []
                };

            if (data.submissionId) {
                $innerContainer.
                    append($('<div class="inline-block"></div>' ).
                    append($('<label>Submission Id:</label>') ).
                    append($('<span>'+data.submissionId+'</span>')));
            }
            if (data.status) {
                $innerContainer.
                    append($('<div class="inline-block"></div>' ).
                    append($('<label>Status:</label>') ).
                    append($('<span>'+data.status+'</span>')));
            }
            if (data.manufacturable) {
                $innerContainer.
                    append($('<div class="inline-block"></div>' ).
                    append($('<label>Manufacturable:</label>') ).
                    append($('<span>'+(data.manufacturable ? "yes" : "no")+'</span>')));
            }
            if (data.message) {
                $innerContainer.
                    append($('<div></div>' ).
                    append($('<label>Message:</label>') ).
                    append($('<span></span>').text(data.message)));
            }
            if (data.bestScore) {
                $innerContainer.
                    append($('<h3 class="content-section-header">Best Score</h3>'));
                $innerContainer.
                    append($('<div class="inline-block"></div>').
                    append($('<label>Id:</label>')).
                    append($('<span>'+data.bestScore.id+'</span>')));
                $innerContainer.
                    append($('<div class="inline-block"></div>').
                    append($('<label>Score:</label>')).
                    append($('<span>'+data.bestScore.score+'</span>')));
                $innerContainer.
                    append($('<div class="inline-block"></div>').
                    append($('<label>Lead Time:</label>') ).
                    append($('<span>'+data.bestScore['time(min)']+' minutes</span>')));
            }

            $innerContainer.append($chartContainer);

            $into.append($innerContainer);

            if (data.bestScore && data.bestScore.manufacturingDetails) {
                $.each(data.bestScore.manufacturingDetails, function (i, item) {
                    item['cost($)'] = Math.round(item['cost($)'] * 100) / 100;
                    item['time(min)'] = Math.round(item['time(min)'] * 10) / 10;
                    datasets[item.type].push(item);
                });
                // # Purchased
                if (datasets.purchased.length > 0) {
                    $innerContainer.append('<h3 class="content-section-header">Purchased</h3>');
                    // ## Cost
                    makeBarChart($innerContainer,
                        "Top Purchased by Cost ($)",
                        datasets.purchased,
                        'cost($)',
                        barOptions
                    );
                    // ## Time
                    makeBarChart($innerContainer,
                        "Top Purchased by Lead Time (Minutes)",
                        datasets.purchased,
                        'time(min)',
                        barOptions
                    );
                }
                // # Manufactured
                if (datasets.manufactured.length > 0) {
                    $innerContainer.append('<h3 class="content-section-header">Manufactured</h3>');
                    // ## Cost
                    makeBarChart($innerContainer,
                        "Top Manufactured by Cost ($)",
                        datasets.manufactured,
                        'cost($)',
                        barOptions
                    );
                    // ## Time
                    makeBarChart($innerContainer,
                        "Top Manufactured by Lead Time (Minutes)",
                        datasets.manufactured,
                        'time(min)',
                        barOptions
                    );
                }
                // # Timeline
                renderTimeline($innerContainer, data);
                // # Feedback
                renderFileList($innerContainer, data, data.bestScore.manfacturingDetails);
            } else {
                // # Feedback
                renderFileList($innerContainer, data, data.manufacturabilityAssessment);
            }

            return true;
        }

        function renderFileList($container, data, entries) {
            if (typeof entries != 'undefined') {
                $.each(entries, function (i, item) {
                    var detail = item.detailedFeedback,
                        submissionId = data.submissionId.replace(/-/g, '').substr(0, 24);
                    if (detail
                        && detail.fileID
                        && detail.fileName
                        && detail.mimeType) {
                        $innerContainer.
                            append('<h4 class="chart-title">Details for ' + item.name + '</h4>');
                        $('<a>').
                            addClass('feedback-file-link').
                            attr('href', './detail_file/' + submissionId + '/' + detail.fileID).
                            text(detail.fileName).
                            appendTo($container);
                    }
                });
            }
        }

        function renderTimeline($parent, data) {
            // data
            var result = data.bestScore,
                items = [],
                // times
                startDate = new Date(result.assemblyDetails.startTime),
                endDate = new Date(result.assemblyDetails.completeTime),
                startTime = startDate.getTime(),
                endTime = endDate.getTime(),
                earliestStartTime = startTime,
                latestEndTime = endTime,
                totalDuration = null,
                // displayData
                $container = $('<div/>').
                    addClass('ganttViewContainer');
            // prepare data
            $.each(result.manufacturingDetails, function () {
                var itemStartDate = new Date(this.startTime),
                    itemEndDate = new Date(this.completeTime),
                    itemStartTime = itemStartDate.getTime(),
                    itemEndTime = itemEndDate.getTime();
                if (itemStartTime < earliestStartTime) {
                    earliestStartTime = itemStartTime;
                }
                if (itemEndTime > latestEndTime) {
                    latestEndTime = itemEndTime;
                }
                items.push({
                    label: this.name,
                    startTime: itemStartTime,
                    endTime: itemEndTime
                });
            });
            items.push({
                label: "Assembly",
                startTime: startTime,
                endTime: endTime
            });
            items.unshift({
                label: "Total Lead Time",
                startTime: earliestStartTime,
                endTime: latestEndTime
            });
            totalDuration = latestEndTime - earliestStartTime;
            // build
            $.each(items, function (i) {
                // times
                var itemRelativeStartTime = this.startTime - earliestStartTime,
                    itemDuration = this.endTime - this.startTime,
                    dayDuration = itemDuration / (24 * 60 * 60 * 1000),
                    dayLabel,
                    // displayData
                    itemLeftOffset = (itemRelativeStartTime / totalDuration) * 100 + '%',
                    itemWidth = (itemDuration / totalDuration) * 100 + '%',
                    // elements
                    $itemContainer = $('<div/>').
                        addClass('ganttViewItem').
                        appendTo($container);
                dayLabel = ((dayDuration < 1) ? '<' : '~') + ' ' +
                    Math.ceil(dayDuration) + ' ' +
                    'day' + ((dayDuration > 1) ? 's' : '');
                $('<div/>').
                    addClass('ganttViewItemBar').
                    css({
                        'left': itemLeftOffset,
                        'width': itemWidth
                    }).
                    appendTo($itemContainer);
                $('<span/>').
                    addClass('ganttViewItemLabel').
                    html('<strong>' + this.label + '</strong> <em>( ' + dayLabel + ' )</em>').
                    appendTo($itemContainer);
            });
            $parent.
                append('<h3 class="content-section-header">Timeline</h3>').
                append($container);
        }

        function renderPendingStatusDetails(data, $into) {
            var $innerContainer = $('<div/>', {
                'class': 'manufacturability-pending-container'
            }),
            completedInt = data["completedTasks"] === null ? "unknown" : parseInt(data["completedTasks"], 10),
            totalInt = data["totalTasks"] === null ? "unknown" : parseInt(data["totalTasks"], 10),
            rendered = false;

            if (completedInt !== "unknown" || totalInt !== "unknown"){
                $innerContainer.append($("<div/>").append($("<label/>", {
                    "text": "Progress:"
                })).append($("<span/>", {
                    "text": completedInt + " / " + totalInt + " tasks completed"
                })));
                rendered = true;
            }

            if (data["stage"]) {
                $innerContainer.append($("<div/>").append($("<label/>", {
                    "text": "Current Analysis Stage:"
                })).append($("<span/>", {
                    "text": data["stage"]
                })));
                rendered = true
            }

            $into.append($innerContainer);

            return rendered;
        }

        return this.each(function () {

            var $container = $(this), rendered = false;

            if (config.data) {
                $container.empty();
                if (config.data["status"] === 'pending'){
                    rendered = renderPendingStatusDetails(config.data, $container);
                } else{
                    rendered = renderDetails(config.data, $container);
                }
            }
            if (rendered === false){
                $container.text('Currently no details available to display.');
            }

            return $container;

        });

    }

}(window));
