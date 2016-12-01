/* globals jQuery, window */
(function ($, $vf) {
    "use strict";
    var regForm,
        DEFAULT_LIMIT = 25,
        loadImg;

     $vf.afterInit(function () {
         loadImg = $('<img src="' + $vf.resourceURL + 'images/loading_small_white.gif" alt="Loading..."/>');
     });
    /****
     * RegistrationRequestForm
     *
     * Singleton rendered on demand.
     *
     * @constructor
     */
    function RegistrationRequestForm() {
        this.template = $("#registration-request-template");
        this.$el = null;
        this.$form = null;
    }
    RegistrationRequestForm.prototype = {
        "render": function (projectData) {
            var that = this;
            this.projectData = projectData;
            if (this.$el === null) {
                this.$el = this.template.tmpl();
                this.$form = this.$el.find('form');
                this.$form.append('<input name="_session_id" type="hidden" value="' + $.cookie('_session_id') + '">');
                this.$el.on('click', '.close', function () {
                    that.$el.trigger('close');
                    return false;
                });
            }
            this.$form.attr("action", this.projectData.home_url_s + 'request_membership');
            this.$el.find('.registration-request-project')
                .text("to " + this.projectData.name_s);
            this.$el.lightbox_me();
        }
    };
    regForm = new RegistrationRequestForm();

    /*****
     * TeamListItem
     *
     * controls one project list item in the join a team project listing
     *
     * @param config
     * @constructor
     */
    function TeamListItem(config) {
        var dataDefaults = {
            icon_url_s: $vf.resourceURL + "images/project_default.png"
        };
        this.el = config.el;
        this.data = $.extend({}, dataDefaults, config.data);
        this.template = config.template;
        this.expanded = false;
        this.requested = false;
        this.render();
    }
    TeamListItem.prototype = {
        "render": function () {
            this.el.html(this.template.tmpl(this.data));
            this.controlsContainer = this.el.find(".teamup-team-controls");
            this.expandContainer = this.el.find(".teamup-team-users");
            this.expandBtn = this.el.find(".see-users");
            this.requestBtn = this.el.find(".request-membership");
            this.bindEvents();
        },
        "bindEvents": function () {
            var that = this;

            /* Display/Hide Controls */
            this.el.on("mouseenter", function () {
                that.controlsContainer.css("visibility", "visible");
            }).on("mouseleave", function () {
                if (!that.expanded) {
                    that.controlsContainer.css("visibility", "hidden");
                }
            }).on("click", function () {
                var curVisibility;
                if (!that.expanded) {
                    curVisibility = that.controlsContainer.css("visibility");
                    that.controlsContainer.css(
                        "visibility",
                        curVisibility === "visible" ? "hidden" : "visible");
                }
            });

            /* View Members Button */
            this.expandBtn.on('click', function (event) {
                if (that.expanded) {
                    that.contract();
                } else {
                    that.expand();
                }
                event.stopPropagation();
                return false;
            });

            /* Request Membership Button */
            this.requestBtn.on('click', function (event) {
                if (!that.requested) {
                    that.requestMembershipStatus();
                }
                event.stopPropagation();
                return false;
            });
        },
        "renderExpanded": function (memberData) {
            /* render the list of members */
            var avatarList = $('<div/>', {"class": "avatar-list"});
            $.each(memberData, function (role, avatars) {
                var i;
                for (i = 0; i < avatars.length; i++) {
                    avatarList.append(avatars[i]);
                }
            });
            this.expandContainer.append(avatarList);
        },
        "expand": function () {
            /* request the list of members, then render using renderExpanded */
            var that = this;
            if (!this.expanded) {
                this.expandBtn.addClass('expanded');
                this.expanded = true;
                this.expandContainer.html(loadImg);
                $.ajax({
                    "url": this.expandContainer.attr("data-target"),
                    "dataType": "json",
                    "success": function (resp) {
                        loadImg.detach();
                        that.renderExpanded(resp);
                    },
                    "error": function () {
                        that.expandContainer.html("<p>You do not have access to that data</p>");
                    }
                });
            }
        },
        "contract": function () {
            /* hide the list of members */
            if (this.expanded) {
                this.expanded = false;
                this.expandBtn.removeClass('expanded');
                this.expandContainer.empty();
            }
        },
        "requestMembershipStatus": function () {
            var that = this, xhr;
            xhr = $.ajax({
                "url": this.data.home_url_s + 'get_membership_status',
                "dataType": "json",
                "success": function (resp) {
                    var status = resp.status, msg;
                    if (status === "none") {
                        that.renderRequestMembershipForm();
                    } else {
                        if (status === "no-register") {
                            msg = "You do not have the necessary permissions to join this team.";
                        } else if (status === "member") {
                            msg = "You are already a member of this team!";
                        } else if (status === "requested") {
                            msg = "Your membership request is currently under review.";
                        } else {
                            msg = "You may not join this team.";
                        }
                        $("#messages").notify(msg);
                    }
                }
            });
            return xhr;
        },
        "renderRequestMembershipForm": function () {
            regForm.render(this.data);
        }
    };

    /************
     * TeamUp
     *
     * controls the entire TeamUp page
     *
     * @param config
     * @constructor
     */
    function TeamUp(config) {
        var defaults = {
                "q": "",
                "limit": DEFAULT_LIMIT,
                "page": 0
            };
        config = $.extend(defaults, config);
        this.el = config.el;
        this.listEl = this.el.find("#teamup-teamlist");
        this.searchForm = this.el.find("#teamup-search");
        this.pagerContainer = this.el.find("#teamup-pager");
        this.searchUrl = config.searchUrl || this.searchForm.attr("action");

        this.q = this.DEFAULT_Q = config.q;
        this.limit = this.DEFAULT_LIMIT = config.limit;
        this.page = this.DEFAULT_PAGE = config.page;

        this.data = {};
        this.teamListItems = [];

        this.bindEvents();
        this.fetch();
    }
    TeamUp.prototype = {
        "bindEvents": function () {
            var that = this;
            this.searchForm.bind("submit", function () {
                that.q = that.searchForm.find("input").val();
                that.page = 0;
                that.fetch();
                that.pushState();
                return false;
            });
            window.onpopstate = function (event) {
                var state = event.state;
                if (state === null) {
                    state = {
                        q: that.DEFAULT_Q,
                        limit: that.DEFAULT_LIMIT,
                        page: that.DEFAULT_PAGE
                    };
                }
                that.q = state.q;
                that.page = state.page;
                that.limit = state.limit;
                that.searchForm.find("input").val(that.q);
                that.fetch();
            };
        },
        "fetch": function () {
            var that = this, start = this.page * this.limit;
            return $.ajax({
                "url": this.searchUrl,
                "dataType": "json",
                "data": {
                    q: this.q,
                    page: this.page,
                    limit: this.limit,
                    start: start
                },
                "success": function (resp) {
                    that.data = resp;
                    that.render();
                }
            });
        },
        "renderEmpty": function () {
            var resetLink, that = this;
            if (!this.q) {
                this.listEl.html("<p>No Teams to join! Perhaps it's time to create one of your own?</p>");
            } else {
                resetLink = $('<a/>', {
                    href: "#",
                    text: "Show all teams",
                    click: function () {
                        that.q = "";
                        that.searchForm.find("input").val("");
                        that.fetch();
                        that.pushState();
                        return false;
                    }
                });

                this.listEl.append($("<p>No teams found matching " + this.q + "</p>")).append(resetLink);
            }
        },
        "render": function () {
            var featuredTemplate = $('#featured-template'),
                projectTemplate = $('#project-template'),
                that = this,
                teamListItems = [];
            this.listEl.empty();
            if (this.data.total_count === 0) {
                this.renderEmpty();
                return this;
            }

            /* render featured */
            $.each(this.data.featured, function (i, doc) {
                var teamList,
                    el = $('<div/>', {
                        "class": "teamup-listitem teamup-ad projectSummaryWidget"
                    }).appendTo(that.listEl);
                teamList = new TeamListItem({
                    el: el,
                    data: doc,
                    template: featuredTemplate
                });
                teamListItems.push(teamList);
            });

            /* render projects */
            $.each(this.data.projects, function (i, doc) {
                var teamList, el;
                el = $('<div/>', {
                    "class": "teamup-listitem teamup-project projectSummaryWidget"
                }).appendTo(that.listEl);
                teamList = new TeamListItem({
                    el: el,
                    data: doc,
                    template: projectTemplate
                });
                teamListItems.push(teamList);
            });

            /* render pager */
            this.pagerContainer.empty();
            this.pager = new $vf.Pager({
                "containerE": this.pagerContainer,
                "onGotoPage": this.onGotoPage,
                "onGotoPage_ctx": this,
                "currentPage": this.page,
                "itemCount": this.data.total_count,
                "itemPerPage": this.limit
            });
            this.pager.render();

            this.teamListItems = teamListItems;
            return this;
        },
        "pushState": function () {
            var stateObj = {
                q: this.q,
                page: this.page,
                limit: this.limit
            }, url, queryObj = {};
            url = window.location.pathname;
            if (this.q) {
                queryObj.q = this.q;
            }
            if (this.page) {
                queryObj.page = this.page;
            }
            if (this.limit !== DEFAULT_LIMIT) {
                queryObj.limit = this.limit;
            }
            if (queryObj) {
                url += '?' + encodeParameters(queryObj);
            }
            window.history.pushState(stateObj, null, url);
        },
        "onGotoPage": function (page) {
            this.page = page;
            this.fetch();
            this.pushState();
        }
    };

    /* exports */
    $vf.TeamUp = TeamUp;

}(jQuery, window.$vf));