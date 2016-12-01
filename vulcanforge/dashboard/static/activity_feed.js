/*
# activity feed

## events
- initialize
- load more
- update
- change filters
- load notifications
- load filters

### initialize
- load notifications
- load filters

### load notifications
*/

(function ($, $vf) {
    "use strict";

    $vf.afterInit(function () {
        var $filterList = $('#filter-list'),
            dateStats = $('#notification-stats').
                vfStatsWidget({
                    graphType: 'aggregate-count-by-date',
                    dataSrc: "notification_aggregate",
                    dataParams: {
                        'order': 'year,month,day'
                    }
                }),
            $notificationList = $('#notification-list'),
            $moreButton = $('#load-more-btn'),
            $loadingMore = $('#loading-notifications'),
            $loadingFilters = $('#loading-filters'),
            $noNotifications = $('#no-notifications'),
            $selectAll = $('#select-all'),
            $unselectAll = $('#unselect-all'),
            $selectNew = $('#select-new'),
            //
            earliest_dt = null,
            latest_dt = null,
            filterXHR = null,
            notificationXHR = null,
            updateInterval = window.setInterval(function () {
                $(document).
                    trigger("UpdateNotifications");
            }, 10 * 1000),
            updateTimesInterval = window.setInterval(function () {
                $(document).
                    trigger('UpdateNotificationTimes');
            }, 10 * 1000),
            //
            showNotifications = function () {
                $notificationList.
                    animate({
                        opacity: 1,
                        top: 0
                    });
            },
            hideNotifications = function () {
                $notificationList.
                    animate({
                        opacity: 0,
                        top: '100%'
                    });
            },
            //
            updateForgeStaticURL = function (url) {
                return url.replace(/\/nf\/.*\/_ew_\//, $vf.resourceURL);
            },
            preprocessNotificationObject = function (notificationObject) {
                if (this.project && this.project.icon_url) {
                    this.project.icon_url = updateForgeStaticURL(this.project.icon_url);
                }
                if (this.app_config && this.app_config.icon_url) {
                    this.app_config.icon_url = updateForgeStaticURL(this.app_config.icon_url);
                }
                if (this.exchange && this.exchange.icon_url) {
                    this.exchange.icon_url = $vf.resourceURL + this.exchange.icon_url;
                }
            };
            dateStats.bind('paramsChanged.vfStats', function(event, changeSpec){
                var newParams = {};
                if (changeSpec["changed"]["date_start"]){
                    newParams["date_start"] = changeSpec["params"]["date_start"];
                }
                if (changeSpec["changed"]["date_end"]){
                    newParams["date_end"] = changeSpec["params"]["date_end"];
                }
                if (newParams.date_start || newParams.date_end) {
                     if (updateInterval) {
                        window.clearInterval(updateInterval);
                        updateInterval = undefined;
                    }
                    if (newParams.date_start) {
                        earliest_dt = new Date(newParams.date_start).toISOString();
                    }
                    if (newParams.date_end) {
                         latest_dt = new Date(newParams.date_end).toISOString() ;
                    }
                    $(document).trigger('LoadNotificationRange');
                } else if (newParams.hasOwnProperty('date_start') &&
                           newParams.hasOwnProperty('date_end')) {
                    if (!updateInterval) {
                        updateInterval = window.setInterval(function () {
                             $(document).
                                 trigger("UpdateNotifications");
                         }, 10 * 1000);
                    }
                    $(document).trigger('LoadNotifications');
                }
            });

        $(document).
            bind({
                "LoadFilters": function () {
                    filterXHR = $.ajax({
                        url: 'filters',
                        success: function (content) {
                            $filterList.
                                html(content);
                        }
                    });
                },
                "SelectAllFilters": function () {
                    filterXHR = $.ajax({
                        url: 'filters?global_state=set',
                        success: function (content) {
                            $filterList.
                                html(content);
                            $(document).
                                trigger('LoadNotifications');
                                dateStats.vfStatsWidget("reRender");
                        }
                    });
                },
                "UnselectAllFilters": function () {
                    filterXHR = $.ajax({
                        url: 'filters?global_state=unset',
                        success: function (content) {
                            $filterList.
                                html(content);
                            $(document).
                                trigger('LoadNotifications');
                                dateStats.vfStatsWidget("reRender");
                        }
                    });
                },
                "SelectNewFilters": function () {
                    filterXHR = $.ajax({
                        url: 'filters?global_state=new',
                        success: function (content) {
                            $filterList.
                                html(content);
                            $(document).
                                trigger('LoadNotifications');
                                dateStats.vfStatsWidget("reRender");
                        }
                    });
                },
                "LoadNotifications": function () {
                    $moreButton.hide();
                    hideNotifications();
                    notificationXHR = $.ajax({
                        url: "notifications",
                        success: function (data) {
                            var lastIndex = data.notifications.length - 1;
                            if (data.notifications.length) {
                                $noNotifications.fadeOut('fast');
                                latest_dt = data.notifications[0].pubdate;
                                earliest_dt = data.notifications[lastIndex].pubdate;
                                //$.each(data.notifications, preprocessNotificationObject);
                            } else {
                                $notificationList.
                                    queue(function () {
                                        $noNotifications.
                                            removeClass('hidden').
                                            fadeIn('slow');
                                        $(this).dequeue();
                                    });
                            }
                            $notificationList.
                                queue(function () {
                                    $(this).html($("#notification-template").tmpl(data.notifications));
                                    $(document).
                                        trigger('UpdateNotificationTimes');
                                    $('.avatar.with-user-id').userIdMe();
                                    showNotifications();
                                    $(this).dequeue();
                                }).
                                queue(function () {
                                    if (data.more) {
                                        $moreButton.fadeIn();
                                    } else {
                                        $moreButton.fadeOut();
                                    }
                                    $(this).dequeue();
                                });
                            // dateStats.vfStatsWidget("updateParams", {"date_end": "2016-05-16", "date_start": "2016-05-13"});
                        }
                    });
                },
                "LoadNotificationRange": function () {
                    $moreButton.hide();
                    hideNotifications();
                    notificationXHR = $.ajax({
                        url: "notifications",
                        data: {
                            from_dt: earliest_dt,
                            to_dt: latest_dt
                        },                        
                        success: function (data) {
                            var lastIndex = data.notifications.length - 1;
                            if (data.notifications.length) {
                                $noNotifications.fadeOut('fast');
                                latest_dt = data.notifications[0].pubdate;
                                earliest_dt = data.notifications[lastIndex].pubdate;
                                //$.each(data.notifications, preprocessNotificationObject);
                            } else {
                                $notificationList.
                                    queue(function () {
                                        $noNotifications.
                                            removeClass('hidden').
                                            fadeIn('slow');
                                        $(this).dequeue();
                                    });
                            }
                            $notificationList.
                                queue(function () {
                                    $(this).html($("#notification-template").tmpl(data.notifications));
                                    $(document).
                                        trigger('UpdateNotificationTimes');
                                    $('.avatar.with-user-id').userIdMe();
                                    showNotifications();
                                    $(this).dequeue();
                                }).
                                queue(function () {
                                    if (data.more) {
                                        $moreButton.fadeIn();
                                    } else {
                                        $moreButton.fadeOut();
                                    }
                                    $(this).dequeue();
                                });
                        }
                    });
                },
                "LoadMoreNotifications": function () {
                    $.ajax({
                        url: "notifications",
                        data: {
                            to_dt: new Date(new Date(earliest_dt).getTime() - 1).toISOString()
                        },
                        success: function (data) {
                            var lastIndex = data.notifications.length - 1;
                            if (data.notifications.length) {
                                earliest_dt = data.notifications[lastIndex].pubdate;
                                //$.each(data.notifications, preprocessNotificationObject);
                            }
                            $loadingMore.hide();
                            $("#notification-template").
                                tmpl(data.notifications).
                                appendTo($notificationList).
                                animate({
                                    top: '100%',
                                    opacity: 0
                                }, 0).
                                animate({
                                    top: 0,
                                    opacity: 1
                                }).
                                queue(function () {
                                    if (data.more) {
                                        $moreButton.fadeIn();
                                    } else {
                                        $moreButton.fadeOut();
                                    }
                                    $(this).dequeue();
                                });
                            $(document).
                                trigger('UpdateNotificationTimes');
                            $('.avatar.with-user-id').userIdMe();
                        }
                    });
                },
                "UpdateNotifications": function () {
                    $.ajax({
                        url: "notifications",
                        data: {
                            from_dt: new Date(new Date(latest_dt).getTime() + 1).toISOString()
                        },
                        success: function (data) {
                            if (data.notifications.length && updateInterval) {
                                $noNotifications.fadeOut('fast');
                                latest_dt = data.notifications[0].pubdate;
                                //$.each(data.notifications, preprocessNotificationObject);
                            }
                            $("#notification-template").
                                tmpl(data.notifications).
                                prependTo($notificationList).
                                animate({
                                    height: 'hide',
                                    bottom: '100%',
                                    opacity: 0
                                }, 0).
                                animate({
                                   height: 'show'
                                }).
                                animate({
                                    bottom: 0,
                                    opacity: 1
                                });
                            $(document).
                                trigger('UpdateNotificationTimes');
                            $('.avatar.with-user-id').userIdMe();
                        }
                    });
                },
                "UpdateNotificationTimes": function () {
                    $('.notification-time').each(function () {
                        $(this).text($vf.relativeDate($(this).attr('datetime')));
                    });
                }
            }).
            trigger('LoadFilters').
            trigger('LoadNotifications');

        $moreButton.
            hide().
            removeClass('hidden').
            bind('click', function () {
                $moreButton.hide();
                $loadingMore.show();
                $(document).trigger('LoadMoreNotifications');
            });

        $selectAll.
            bind('click', function () {
                $(document).trigger('SelectAllFilters');
            });

        $unselectAll.
            bind('click', function () {
                $(document).trigger('UnselectAllFilters');
            });

        $selectNew.
             bind('click', function () {
                $(document).trigger('SelectNewFilters');
            });
           
        $filterList.
            delegate(".app_config-filter-checkbox", 'change', function () {
                if (filterXHR) {
                    filterXHR.abort();
                }
                if (notificationXHR) {
                    notificationXHR.abort();
                }
                var $checkbox = $(this),
                    app_config_id = $checkbox.val(),
                    checked = $checkbox.is(":checked"),
                    url = (checked) ? 'enable_app_config' : 'disable_app_config';
                $.ajax({
                    url: url,
                    data: {
                        _id: app_config_id
                    },
                    success: function () {
                        $(document).
                            trigger('LoadNotifications');
                            dateStats.vfStatsWidget("reRender");
                    }
                });
            }).
            delegate('.project-filter-checkbox', 'change', function () {
                if (filterXHR) {
                    filterXHR.abort();
                }
                if (notificationXHR) {
                    notificationXHR.abort();
                }
                var $checkbox = $(this),
                    project_id = $checkbox.val(),
                    checked = $checkbox.is(":checked"),
                    url = (checked) ? 'enable_project' : 'disable_project';
                $.ajax({
                    url: url,
                    data: {
                        _id: project_id
                    },
                    success: function () {
                        $(document).
                            trigger('LoadFilters').
                            trigger('LoadNotifications');
                        dateStats.vfStatsWidget("reRender");
                    }
                });
            }).
            delegate('.exchange-filter-checkbox', 'change', function () {
                if (filterXHR) {
                    filterXHR.abort();
                }
                if (notificationXHR) {
                    notificationXHR.abort();
                }
                var $checkbox = $(this),
                    exchange_uri = $checkbox.val(),
                    checked = $checkbox.is(":checked"),
                    url = checked ? 'enable_exchange' : 'disable_exchange';
                $.ajax({
                    url: url,
                    data: {
                        uri: exchange_uri
                    },
                    success: function () {
                        $(document).
                            trigger('LoadFilters').
                            trigger('LoadNotifications');
                        dateStats.vfStatsWidget("reRender");
                    }
                });
            });

        $notificationList.
            delegate(".notification-open", "click", function () {
                $(this).
                    hide().
                    closest(".notification-container").
                    find('.notification-body').
                    slideDown().
                    end().
                    find('.notification-close').
                    show();
            }).
            delegate(".notification-close", "click", function () {
                $(this).
                    hide().
                    closest(".notification-container").
                    find('.notification-body').
                    slideUp().
                    end().
                    find('.notification-open').
                    show();
            });
    });

}(jQuery, window.$vf));

