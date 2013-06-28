/**
 * Created with PyCharm.
 * User: tannern
 * Date: 4/4/13
 * Time: 11:58 AM
 * To change this template use File | Settings | File Templates.
 */

(function ($) {
    'use strict';

    // graph types defined at the bottom
    var graphTypes,
        $vf = window.$vf || {};
    $vf.stats = $vf.stats || {};

    // utility
    function as (fn, object) {
        return function () {
            fn.apply(object, arguments);
        };
    }
    function pad(s, length, filler){
        s = s.toString();
        while (s.length < length){
            s = filler + s;
        }
        return s;
    }
    function dateToStr(dateObj) {
        return [
            dateObj.getUTCFullYear(),
            pad(dateObj.getUTCMonth() + 1, 2, '0'),
            pad(dateObj.getUTCDate(), 2, '0')
        ].join('-');
    }
    function timeFromStr(str) {
        var parts = str.split('-');
        return Date.UTC(parts[0], parts[1] - 1, parts[2]);
    }

    $vf.stats.weekendMarkings = function (axes) {
        var markings = [],
            d = new Date(axes.xaxis.min),
            i;
        // go to the first Saturday
        d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 1) % 7))
        d.setUTCSeconds(0);
        d.setUTCMinutes(0);
        d.setUTCHours(0);
        i = d.getTime();
        // when we don't set yaxis, the rectangle automatically
        // extends to infinity upwards and downwards
        do {
            markings.push({ xaxis: { from: i, to: i +
                2 * 24 * 60 * 60 * 1000 } });
            i += 7 * 24 * 60 * 60 * 1000;
        }
        while (i < axes.xaxis.max);
        return markings;
    };

    // exceptions
    $vf.stats.InvalidGraphType = function (graphType) {
        this.message = "graphType \"" + graphType + "\" is not supported.";
    };

    // define
    $.widget('vf.vfStatsWidget', {
        options: {
            graphType: 'bar',
            dataSrc: null,
            dataParams: undefined,
            dataset: null,
            threshold: 0.01,
            clickable: false,
            selectedLabel: undefined
        },
        _create: function () {
            if (typeof this.options.dataParams === 'undefined'){
                this.options.dataParams = {};
            }
            if (this.options.dataSrc) {
                this._loadDataFromSrc(this.options.dataSrc, this.options.dataParams);
            } else {
                this.dataset = this.options.dataset;
            }
            this.element.addClass('vfStatsWidget');
            this.$tooltip = $('<div></div>').
                addClass('vfStatsWidgetTooltip').
                appendTo($('body')).
                hide();
            this.element.bind({
                'dataLoading.vfStats': as(this._handleDataLoading, this),
                'dataLoaded.vfStats': as(this._handleDataLoaded, this)
            });
            graphTypes[this.options.graphType].init.call(this);
            if (typeof this.options.dataSrc !== 'undefined') {
                this._render()
            }
        },
        _loadDataFromSrc: function (dataSrc, dataParams) {
            var that = this,
                queryParams = $.extend({}, dataParams);
            this.element.trigger('dataLoading.vfStats', {
                queryParams: queryParams
            });
            $.ajax({
                'url': dataSrc,
                'dataType': 'json',
                'data': queryParams,
                'success': function (data) {
                    that.dataset = data;
                    that.element.trigger('dataLoaded.vfStats', {
                        'dataset': that.dataset
                    });
                }
            });
        },
        _handleDataLoading: function () {
            this.element.text('loading...');
        },
        _handleDataLoaded: function () {
            this._render();
        },
        _render: function () {
            var renderer = graphTypes[this.options.graphType].renderer;
            if (typeof renderer === 'undefined') {
                throw new $vf.stats.InvalidGraphType(this.options.graphType);
            }
            this.element.empty();
            this.element.trigger('rendering.vfStats');
            renderer.call(this);
        },
        updateParams: function(params) {
            var changelog = {}, that = this, old;
            $.each(params, function(key, value){
                old = that.options.dataParams[key];
                if (old !== value){
                    changelog[key] = {
                        "old": old,
                        "new": value
                    };
                    that.options.dataParams[key] = value;
                }
            });
            return changelog;
        },
        reRender: function() {
            this._loadDataFromSrc(this.options.dataSrc, this.options.dataParams);
        }
    });

    // instantiate
    $(function () {
        $('.vfStatsWidget').each(function () {
            var $this = $(this);
            $this.vfStatsWidget({
                graphType: $this.attr('data-type'),
                dataSrc: $this.attr('data-src')
            });
        });
    });

    // define graph types
    //  methods are called as the widget
    graphTypes = {
        // mongodb aggregates

        'aggregate-count-by-date': {
            init: function () {
                this.element.bind({
                    'dataLoading.vfStats': function (e, context) {
                        delete(context.queryParams.date_start);
                        delete(context.queryParams.date_end);
                    }
                });
            },
            renderer: function () {
                var that = this,
                    graphData = [{
                        label: 'total',
                        data: []
                                 }],
                    entryInterval = 24 * 60 * 60 * 1000,
                    mainView, overview,
                    startTime, endTime,
                    mainViewOptions = {
                        bars: {
                            show: true,
                            barWidth: entryInterval,
                            align: 'left'
                        },
                        xaxis: {
                            mode: 'time',
                            minTickSize: [1, "day"]
                        },
                        yaxis: {
                            minTickSize: 1,
                            min: 0,
                            autoscaleMargin: 0.1,
                            tickDecimals: 0
                        },
                        selection: {
                            mode: 'x'
                        },
                        grid: {
                            markings: $vf.stats.weekendMarkings,
                            hoverable: true
                        }
                    },
                    overviewOptions = {
                        bars: {
                            show: true,
                            barWidth: entryInterval,
                            align: 'left',
                            shadowSize: 0
                        },
                        xaxis: {
                            ticks: [],
                            mode: 'time'
                        },
                        yaxis: {
                            ticks: [],
                            min: 0,
                            autoscaleMargin: 0.25
                        },
                        selection: {
                            mode: 'x',
                            xaxis: {}
                        },
                        grid: {
                            markings: $vf.stats.weekendMarkings
                        },
                        legend: {
                            show: false
                        }
                    };
                // prep dataset
                $.each(this.dataset['result'], function (i, entry) {
                    var time = Date.UTC(entry._id.year, entry._id.month - 1, entry._id.day),
                        datapoint = [time, entry.count];
                    that.element.trigger('processDatapoint.vfStats', {
                        originalDataEntry: entry,
                        datapoint: datapoint
                    });
                    graphData[0].data.push(datapoint);
                });
                this.element.trigger('dataProcessed.vfStats', {
                    graphData: graphData
                });
                // create elements
                this.$mainView = $('<div/>').
                    addClass('vfStatsTimelineMainView').
                    appendTo(this.element);
                this.$overview = $('<div/>').
                    addClass('vfStatsTimelineOverview').
                    appendTo(this.element);
                // draw graphs
                if (this.options.dataParams.date_start && this.options.dataParams.date_end) {
                    startTime = timeFromStr(this.options.dataParams.date_start);
                    endTime = timeFromStr(this.options.dataParams.date_end);
                    mainViewOptions.xaxis.min = startTime;
                    mainViewOptions.xaxis.max = endTime;
                }
                mainView = $.plot(this.$mainView, graphData, mainViewOptions);
                overview = $.plot(this.$overview, graphData, overviewOptions);
                if (this.options.dataParams.date_start && this.options.dataParams.date_end) {
                    overview.setSelection({
                        xaxis: {
                            from: mainViewOptions.xaxis.min,
                            to: mainViewOptions.xaxis.max
                        }
                    }, true);
                }
                // bind events
                this.$mainView.bind({
                    'plotselected': function (event, ranges) {
                        var changelog,
                            ymax = 0,
                            plotdata = mainView.getData();
                        ranges.xaxis.from = Math.floor(ranges.xaxis.from / entryInterval) * entryInterval;
                        ranges.xaxis.to = Math.ceil(ranges.xaxis.to / entryInterval) * entryInterval;
                        $.each(plotdata, function (e, val) {
                            $.each(val.data, function (e1, val1) {
                                if ((val1[0] >= ranges.xaxis.from) && (val1[0] <= ranges.xaxis.to)) {
                                    ymax = Math.max(ymax, val1[1]);
                                }
                            });
                        });
                        ymax = Math.ceil(ymax * 1.1);
                        mainView = $.plot(that.$mainView, graphData, $.extend(true, {}, mainViewOptions, {
                            xaxis: {
                                min: ranges.xaxis.from,
                                max: ranges.xaxis.to
                            },
                            yaxis: {
                                max: ymax
                            }
                        }));
                        overview.setSelection(ranges, true);

                        changelog = that.updateParams({
                            "date_start": dateToStr(new Date(ranges.xaxis.from)),
                            "date_end": dateToStr(new Date(ranges.xaxis.to))
                        });
                        if (changelog){
                            that.element.trigger('paramsChanged.vfStats', {
                                "changed": changelog,
                                "params": that.options.dataParams
                            });
                        }
                    },
                    'plothover': function (e, loc, plot) {
                        var context;
                        if (plot !== null) {;
                            context = {
                                loc: loc,
                                plot: plot,
                                date: new Date(plot.datapoint[0])
                            };
                            context.label = [
                                plot.datapoint[1] + ' ' + plot.series.label,
                                context.date.toGMTString().split(' ').slice(0,4).join(' ')
                            ].join('<br>');
                            that.element.trigger('timelineBarHover.vfStats', context);
                            that.$tooltip.
                                html(context.label).
                                show().
                                css({
                                    'top': loc.pageY - that.$tooltip.outerHeight() - 10,
                                    'left': loc.pageX - that.$tooltip.outerWidth() / 2,
                                    'border-color': plot.series.color
                                });
                        } else if (e.target !== that.$tooltip) {
                            that.$tooltip.
                                hide();
                        }
                    }
                });
                this.$overview.bind({
                    'plotselected': function (event, ranges) {
                        mainView.setSelection(ranges);
                    },
                    'plotunselected': function (event) {
                        var changelog;
                        mainViewOptions.xaxis.min = undefined;
                        mainViewOptions.xaxis.max = undefined;
                        mainView = $.plot(that.$mainView, graphData, mainViewOptions);
                        changelog = that.updateParams({
                            "date_start": undefined,
                            "date_end": undefined
                        });
                        if (changelog){
                            that.element.trigger('paramsChanged.vfStats', {
                                "changed": changelog,
                                "params": that.options.dataParams
                            });
                        }
                    }
                });
            }
        },

        'aggregate-count-by-label': {
            init: function () {

            },
            renderer: function () {
                var that = this,
                    dataset = this.dataset['result'],
                    graphData = [],
                    sum = 0,
                    otherSum = 0,
                    others = [],
                    graphOptions = {
                        series: {
                            pie: {
                                show: true,
                                radius: 1,
                                innerRadius: 0.5,
                                label: {
                                    show: false
                                },
                                combine: {
                                    color: '#aaa',
                                    threshold: that.options.threshold
                                }
                            }
                        },
                        grid: {
                            hoverable: true,
                            clickable: this.options.clickable
                        },
                        legend: {
                            show: false
                        }
                    };
                // prepare data
                $.each(dataset, function (i, entry) {
                    var datapoint = {
                        label: entry.label,
                        data: entry.count,
                        entry: entry
                    };
                    that.element.trigger('processDatapoint.vfStats', {
                        originalDataEntry: entry,
                        datapoint: datapoint
                    });
                    graphData.push(datapoint);
                    sum += entry.count;
                });
                this.element.trigger('dataProcessed.vfStats', {
                    graphData: graphData
                });
                // chart
                this.$graph = $('<div/>').
                    addClass('vfStatsPieView').
                    appendTo(this.element);
                this.element.trigger('prepareGraphOptions.vfStats', {
                    graphOptions: graphOptions
                });
                $.plot(this.$graph, graphData, graphOptions);
                // table
                this.$table = $('<table/>').
                    addClass('vfStatsTableView');

                function makeRow(label, count, entry, frac, selected){
                    var $row = $('<tr/>').appendTo(that.$table),
                        $labelCell = $('<td/>').
                            attr('data-label', label).
                            text(label).
                            appendTo($row),
                        percText = '';
                    if (that.options.clickable) {
                        $row.
                            addClass(selected ? 'selected' : '');
                        $labelCell.
                            addClass('vfStatsSelectable').
                            addClass(selected ? 'selected' : '').
                            bind('click', function () {
                                that.options.selectedLabel = label;
                                that.element.trigger('labelSelected.vfStats', {
                                    label: label,
                                    entry: entry
                                });
                        });
                    }
                    $('<td/>').
                        text(count).
                        appendTo($row);
                    if (frac !== null){
                        percText = '(' + Math.round(frac * 100) + "%)"
                    }
                    $('<td/>').
                        text(percText).
                        appendTo($row);
                }

                $.each(dataset, function (i, entry) {
                    var frac = entry.count / sum,
                        selected = (entry.label === that.options.selectedLabel);
                    if (frac <= that.options.threshold){
                        otherSum += entry.count;
                        others.push(entry);
                    } else {
                        makeRow(entry.label, entry.count, entry, frac, selected);
                    }
                });
                if (otherSum > 0) {
                    makeRow('Other', otherSum, others, otherSum / sum);
                }
                if (this.options.clickable) {
                    makeRow('All', sum, null, null, typeof that.options.selectedLabel === 'undefined');
                }
                this.$table.appendTo(this.element);
                // bind events
                this.$graph.bind({
                    'plothover': function (e, loc, plot) {
                        var label;
                        if (plot !== null) {
                            label = plot.series.label + '<br>' +
                                plot.datapoint[1][0][1] + ' (' + Math.round(plot.datapoint[0]) + '%)';
                            that.$tooltip.
                                html(label).
                                show().
                                css({
                                    'top': loc.pageY - that.$tooltip.outerHeight() - 10,
                                    'left': loc.pageX - that.$tooltip.outerWidth() / 2,
                                    'border-color': plot.series.color
                                });
                        } else if (e.target !== that.$tooltip) {
                            that.$tooltip.
                                hide();
                        }
                    },
                    'plotclick': function (e, pos, item) {
                        var entry = null;
                        if (item !== null) {
                            if (item.series.label === 'Other'){
                                entry = others;
                            } else {
                                entry = dataset[item.seriesIndex];
                            }
                            that.options.selectedLabel = item.series.label;
                            that.element.trigger('labelSelected.vfStats', {
                                label: item.series.label,
                                entry: entry
                            });
                        }
                    }
                });
                this.element.bind('labelSelected.vfStats', function (e, context) {
                    that.$table.
                        find('.selected').
                        removeClass('selected').
                        end().
                        find('td[data-label="'+context.label+'"]').
                        addClass('selected').
                        parent().
                        addClass('selected');
                });
            }
        },

        // solr faceting
        'facet-pie': {
            'init': function () {

            },
            'renderer': function () {
                var that = this,
                    dataset = this.dataset,
                    graphData = [],
                    graphOptions = {
                        series: {
                            pie: {
                                show: true,
                                radius: 1,
                                innerRadius: 0.5,
                                label: {
                                    show: false,
                                },
                                combine: {
                                    color: '#aaa',
                                    threshold: that.options.threshold
                                }
                            }
                        },
                        grid: {
                            hoverable: true,
                            clickable: this.options.clickable
                        },
                        legend: {
                            show: false
                        }
                    };
                // prepare data
                $.each(dataset, function (i, datum) {
                    var pointIndex = Math.floor(i / 2),
                        point = graphData[pointIndex] = graphData[pointIndex] || {};
                    if (i % 2) {  // value
                        point.data = datum;
                    } else {  // label
                        point.label = datum;
                    }
                });
                this.element.trigger('dataProcessed.vfStats', {
                    graphData: graphData
                });
                // chart
                this.$graph = $('<div/>').
                    addClass('vfStatsMiniPieView').
                    appendTo(this.element);
                this.element.trigger('prepareGraphOptions.vfStats', {
                    graphOptions: graphOptions
                });
                $.plot(this.$graph, graphData, graphOptions);
                this.$graph.bind({
                    'plothover': function (e, loc, plot) {
                        var label;
                        if (plot) {
                            label = plot.series.label + '<br>' +
                                plot.datapoint[1][0][1] + ' (' + Math.round(plot.datapoint[0]) + '%)';
                            that.$tooltip.
                                html(label).
                                show().
                                css({
                                    'top': loc.pageY - that.$tooltip.outerHeight() - 10,
                                    'left': loc.pageX - that.$tooltip.outerWidth() / 2,
                                    'border-color': plot.series.color
                                });
                        } else if (e.target !== that.$tooltip) {
                            that.$tooltip.
                                hide();
                        }
                    }
                });
                this.element.bind('mouseleave', function () {
                    that.$graph.trigger('plothover', {
                        pageX: 0,
                        pageY: 0
                    }, null);
                });
            }
        }
    };

})(jQuery);
