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

(function ($) {

    $vf.afterInit(function () {
        var $filterList = $('#filter-list'),
            $notificationList = $('#notification-list'),
            $moreButton = $('#load-more-btn'),
            $loadingMore = $('#loading-notifications'),
            $loadingFilters = $('#loading-filters'),
            $noNotifications = $('#no-notifications'),
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
            };

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
                                $.each(data.notifications, preprocessNotificationObject);
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
                            date: earliest_dt
                        },
                        success: function (data) {
                            var lastIndex = data.notifications.length - 1;
                            if (data.notifications.length) {
                                earliest_dt = data.notifications[lastIndex].pubdate;
                                $.each(data.notifications, preprocessNotificationObject);
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
                            date: latest_dt,
                            before: false
                        },
                        success: function (data) {
                            if (data.notifications.length) {
                                latest_dt = data.notifications[0].pubdate;
                                $.each(data.notifications, preprocessNotificationObject);
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

}(jQuery));
