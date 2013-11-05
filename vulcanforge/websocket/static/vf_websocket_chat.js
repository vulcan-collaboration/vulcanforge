/**
 * vf_websocket_chat
 *
 * :author: tannern
 * :date: 10/29/13
 */
(function ($) {
    'use strict';
    if (!$vf || !$vf.webSocket) {
        console.warn("vf_websocket_chat.js depends on vf_websocket.js and must be loaded after it");
        return;
    }

    $(window).on('VFWebSocketInit', function (event, vfSocket) {
        var vfChat = {
            _chatIndex: {},
            isOpen: false,
            _projectData: [],
            init: function () {
                var that = this;
                this.loadInitalData(function () {
                    that.initUI();
                    that.bindEvents();
                });
            },
            loadInitalData: function (opt_callback) {
                var that = this;
                $.ajax({
                    'url': '/webs/websocket/chat/projects',
                    'error': function () {
                        console.warn(arguments);
                    },
                    'success': function (projectData) {
                        that._projectData = projectData.projects;
                        if (opt_callback) {
                            opt_callback();
                        }
                    }
                });
            },
            initUI: function () {
                var that = this;
                this.$container = $('<div/>').
                    attr('id', 'vf-chat-container').
                    addClass('closed');
                this.$tab = $('<div/>').
                    addClass('vf-chat-tab').
                    text('chat').
                    appendTo(this.$container);
                this.$projects= $('<div/>').
                    addClass('vf-chat-projects').
                    appendTo(this.$container);
                $.each(this._projectData, function (i, v) {
                    $('<div/>').
                        addClass('vf-chat-project-button').
                        html('<img src="'+ v.icon_url +'"> ' + v.name).
                        attr('data-project', v.shortname).
                        appendTo(that.$projects);
                });
                this.$users = $('<div/>').
                    addClass('vf-chat-users').
                    appendTo(this.$container);
                this.$container.appendTo('body');
            },
            bindEvents: function () {
                var that = this,
                    hoverTimeout;
                this.$tab.bind({
                    'click': function () {
                        that.toggleChat.call(that);
                    },
                    'mouseenter': function () {
                        if (!that.isOpen) {
                            hoverTimeout = setTimeout(function () {
                                that.openChat.call(that);
                            }, 300);
                        }
                    },
                    'mouseleave': function () {
                        clearTimeout(hoverTimeout);
                    }
                });
                this.$container.
                    on('click', '.vf-chat-project-button', function () {
                        that.selectProjectByShortname.call(that, $(this).attr('data-project'));
                    }).
                    bind('projectSelected', function () {
                        that.buildSelectedProjectUI.call(that);
                    });
            },
            setIsOpen: function (value) {
                this.isOpen = !!value;
                this.$container.
                    toggleClass('open', this.isOpen).
                    toggleClass('closed', !this.isOpen);
            },
            openChat: function () {
                this.setIsOpen(true);
            },
            closeChat: function () {
                this.setIsOpen(false);
            },
            toggleChat: function () {
                this.setIsOpen(!this.isOpen);
            },
            selectProjectByShortname: function (shortname) {
                var project;
                $.each(this._projectData, function (i, v) {
                    if (v.shortname === shortname) {
                        project = v;
                        return false;
                    }
                });
                if (project) {
                    this._selectedProject = project;
                    this.$container.trigger('projectSelected', {
                        'shortname': shortname,
                        'project': this._selectedProject
                    });
                } else {
                    console.warn('project not found with shortname: ' + shortname);
                }
            },
            buildSelectedProjectUI: function () {
                this.$users.empty();
            }
        };
        vfChat.init();
        // get available chats

        // register handlers
        vfSocket.
            addHandler(/^project\.([^\.]+)\.chat$/, function (match, msg) {
                console.log(msg);
            });
    });

})(jQuery);
