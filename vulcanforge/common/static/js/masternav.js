/* Assumed Globals: jQuery, _, window */
(function ( $, _, config ) {
    "use strict";

    function isNonEmptyArray(x) {
        return typeof x !== 'undefined' && typeof x.length === 'number' && x.length > 0;
    }

    $vf.afterInit(function () {
        var current = $vf.nav_context;
        config = config || {};
        config = _.defaults(config, {
            timeoutDuration: 10,
            smartFilter: false,
            bottomBuffer: 64,
            scrollBuffer: 10,
            rootIcon: $vf.resourceURL + "images/vf_plus_fang_logo.png",
            hoodsIcon: $vf.resourceURL + "images/project_default.png",
            submenuNudge: 8,
            popupDelay: 175,
            animateIntro: 250,
            preferREST: true,
            filterShortname: "--init--"
        });

        var $master = $("ul.masternav");
        if (!$master.length) { console.log("Masternav Error: No ul.masternav found");
        } else {
            var masterTimeout, submenuTimeout;

            var _renderMaster = function(data) {
                var hood = {};
                var project = {};
                var tool = {};
                // Render default rootIcon
                $master.append(_master({ label: data.label, icon: data.icon, shortname: "_globals", url: data.url }));
                if (current.length > 0) {
                    hood = _.findWhere(data.hoods, { shortname: current[0] });
                    if (typeof hood !== 'undefined') {
                        $master.append(_master(hood));
                        // Do we render the current project
                        if (current.length > 1) {
                            project = _.findWhere(hood.children, { shortname: current[1] });
                            if (typeof project !== 'undefined') {
                                if (current[1] !== '--init--') {
                                    $master.append(_master(project));
                                }
                                if (current.length > 2) {
                                    tool = _.findWhere(project.tools, { shortname: current[2] });
                                    if (typeof tool !== 'undefined') {
                                        $master.append(_master(tool));
                                    }
                                }
                            }
                        }
                    }
                }
                // Is the root menu animated?
                if (config.animateIntro) {
                    $master.animate({ left: 0 }, config.animateIntro);
                } else {
                    $master.css("left", "auto");
                }

                $("li.masternav-item").bind("mouseenter", function(event) {
                    var $this = $(this), $target = $(event.delegateTarget);
                    clearTimeout(masterTimeout);
                    clearTimeout(submenuTimeout);
                    _popState(0);
                    var content = data.globals;
                    switch ($target.attr('data-shortname')) {
                    case current[0]:
                        content = hood;
                        break;
                    case current[1]:
                        content = project;
                        break;
                    case current[2]:
                        content = {};
                        break;
                    default:
                    }
                    _renderPopup($master, 0, event.delegateTarget.id, content, $target.outerHeight(), $target.position().left, $this);
                })
                .bind("mouseleave", function() {
                    masterTimeout = setTimeout(_checkHover, config.timeoutDuration);
                });
            };

            var _renderPopup = function($container, depth, name, content, top, left, $triggeredBy) {
                // Filter out those things that are already visible in the menu
                //if (config.smartFilter && depth == 0) {
                //    content.children = _.reject(content.children, function(item) {
                //        return _.contains(current, item.shortname);
                //    });
                //}
                // Filter out anything that has a specific shortname
                if (config.filterShortname) {
                    content.children = _.reject(content.children, function(item) {
                        return item.shortname == config.filterShortname;
                    });
                }
                var maxHeight = $(window).height() - top - (config.bottomBuffer * (4 - depth));
                var $popup = $(_popupBase({ id: name + "-pop" })).appendTo($container)
                    .css("top", top)
                    .css("left", left);
                var $list = $popup.children("ul")
                    .css("max-height", maxHeight);

                clearTimeout(submenuTimeout);
                _pushState($popup, depth);

                // Render each link first
                var items = [];
                if ($triggeredBy.attr('data-shortname') === '_globals') {
                    items = items.concat(data.hoods);
                }
                if (isNonEmptyArray(content.tools)) {
                    items = items.concat(content.tools);
                }
                if (isNonEmptyArray(content.children)) {
                    if (items.length > 0) {
                        items.push('-');
                    }
                    items = items.concat(content.children);
                }
                _.each(items, function(link) {
                    if (link === '-') {
                        $list.append("<li><hr></li>");
                        return;
                    }
                    _.defaults(link, { shortname: "" });
                    var hasChildren = (_.has(link, "children") && (link.children.length > 0)) || (_.has(link, "tools") && (link.tools.length > 0));
                    _.extend(link, { hasChildren: hasChildren });
                    // Create the Link element
                    var $item = $(_popupLink(link)).appendTo($list);
                    // Handle going to a submenu - if there is content for it
                    if (hasChildren) {
                        $item.bind("mouseenter", function() {
                            // Adjust for the 0.5em on the top of the overall list
                            var subTop = top + $item.position().top - config.submenuNudge;
                            var width = left + $item.width();
                            var subcontent = _.findWhere(items, { shortname: link.shortname });
                            _renderPopup($container, depth+1, link.shortname, subcontent, subTop, width, $item);
                        });
                    } else $item.bind("mouseenter", function() { _popState(depth + 1); });
                });
                // Add a separator if there are Actions
                if (content.actions && content.actions.length > 0) {
                    $list.append("<li><hr></li>");
                }
                // Render each Action element - And respond to its mounterenter event
                _.each(content.actions, function(action) {
                    $(_popupAction(action)).appendTo($list).bind("mouseenter", function() { _popState(depth + 1); });
                });
                // Is it scrollable
                if ($list.prop("scrollHeight") > maxHeight) {
                    $popup.addClass("scrollable-bottom");
                    $list.bind("scroll", function() {
                        // Check if top scroll arrow is needed
                        if ($list.prop("scrollTop") > config.scrollBuffer) $popup.addClass("scrollable-top");
                        else $popup.removeClass("scrollable-top");
                        // Check if top scroll arrow is needed
                        var scrollBottom = $list.prop("scrollHeight") - $list.prop("scrollTop") - $list.height();
                        if (scrollBottom < config.scrollBuffer) $popup.removeClass("scrollable-bottom");
                        else $popup.addClass("scrollable-bottom");
                        // TODO: Allow overall page to scroll
                    })
                }
                $popup.bind("mouseleave", function() {
                    submenuTimeout = setTimeout(_checkHover, config.timeoutDuration);
                })
                .animate({ opacity: 1 }, config.popupDelay);
            };

            var _checkHover = function () {
                if (!_.some(data.state, function($menu) {
                    return $menu.is(":hover");
                })) _popState(0);
            };

            var _pushState = function($item, depth) {
                _popState(depth);
                data.state.push($item);
            };

            var _popState = function(depth) {
                while (data.state.length > depth) data.state.pop().remove();
            };

            /***************************** Initialization ******************************/

            var _master = _.template(
                '<li data-shortname="<%= shortname %>" class="masternav-item">' +
                '<a href="<%= url %>">' +
                '<% if (icon) { %><img class="masternav-item-icon" src="<%= icon %>" /><% } %>' +
                '<% if (label) { %><span class="masternav-item-label"><%= label %></span><% } %>' +
                '</a>' +
                '</li>'
            );
            var _popupBase = _.template(
                '<div class="popup-container">' +
                '<ul id="<%= id %>" class="masternav-popup"></ul>' +
                '</div>');
            var _popupLink = _.template(
                '<li data-shortname="<%= shortname %>">' +
                '<a class="link<% if (hasChildren) { %> children<% } %>" href="<%= url %>">' +
                '<% if (icon) { %><img class="masternav-item-icon" src="<%= icon %>" /><% } %>' +
                '<% if (label) { %><span class="masternav-item-label"><%= label %></span><% } %>' +
                '</a>' +
                '</li>'
            );
            var _popupAction = _.template(
                '<li>' +
                '<a class="action" href="<%= url %>">' +
                '<span><%= label %></span>' +
                '</a>' +
                '</li>');

            var data = { globals: [], hoods:[], state: [] };
            if (config.preferREST) {
    //            console.log("$master.url: " + $master.data("url"));
                $.ajax({ url: $master.data("url") }).then(
                    function(fetch) {
                        data = _.defaults(fetch || {}, data);
    //                    console.log("Data: " + JSON.stringify(data));
                        _renderMaster(data);
                    }
                );
            } else {
                data = _.defaults($master.data("content") || {}, data);
                _renderMaster(data);
            }
        }
    });
} (jQuery, _));
