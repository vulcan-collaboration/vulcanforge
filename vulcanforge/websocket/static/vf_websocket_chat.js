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
            _isOpen: false,
            _localStorage: typeof Storage !== 'undefined',
            _storagePrefix: 'vf_chat_',
            _projectData: [],
            _projectNameIndex: {},
            _projectsWithChat: [],
            _unreadCounts: {},
            _activeProjectName: null,
            _userProfiles: {},
            _autoScroll: true,
            _scrollTimeout: null,
            init: function () {
                var that = this,
                    activeProjectName = this.pref('project');
                this._isOpen = this.prefBool('open');
                this.loadState(function () {
                    if (that._projectsWithChat.length === 0) {
                        console.log('No projects with chat found, disabling chat');
                        return;
                    }
                    that.initUI();
                    $.each(that._projectData, function (i, project) {
                        if (project.chatChannel) {
                            vfSocket.subscribe(project.chatChannel);
                            $.each(project.chatMessages, function (i, msg) {
                                that.renderMessageToProject(msg.data, project.shortname);
                            });
                            $.each(project.users, function (i, username) {
                                that.renderUserListWidgetToProject(username, project.shortname);
                            });
                            vfSocket.subscribe($.map(project.users, function (v, i) {
                                return 'user.' + v;
                            }));
                            if (!activeProjectName) {
                                activeProjectName = project.shortname;
                            }
                        }
                    });
                    that.bindEvents();
                    that.selectProject(activeProjectName);
                });
            },
            loadState: function (opt_callback) {
                var that = this;
                $.ajax({
                    'url': '/webs/websocket/chat/state',
                    'error': function () {
                        console.warn(arguments);
                    },
                    'success': function (projectData) {
                        that._projectData = projectData.projects;
                        $.each(that._projectData, function (i, project) {
                            that._projectNameIndex[project.shortname] = i;
                            if (project.chatChannel) {
                                that._projectsWithChat.push(project.shortname);
                                that._unreadCounts[project.shortname] = 0;
                            }
                        });
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
                    toggleClass('vf-chat-open', this._isOpen).
                    toggleClass('vf-chat-closed', !this._isOpen);
                this.$tab = $('<div/>').
                    addClass('vf-chat-tab').
                    text('chat').
                    appendTo(this.$container);

                this.$panelContainer = $('<div/>').
                    addClass('vf-chat-panel-container').
                    appendTo(this.$container);

                this.$header = $('<div/>').
                    addClass('vf-chat-header').
                    appendTo(this.$panelContainer);
                this.$content = $('<div/>').
                    addClass('vf-chat-content').
                    appendTo(this.$panelContainer);
                this.$formContainer = $('<div/>').
                    addClass('vf-chat-form-container').
                    appendTo(this.$panelContainer);

                this.$projects = $('<div/>').
                    addClass('vf-chat-projects-list').
                    appendTo(this.$header);

                this.$form = $('<form/>').
                    addClass('vf-chat-form').
                    appendTo(this.$formContainer);
                this.$textarea = $('<textarea name="message">').
                    addClass('vf-chat-textarea').
                    appendTo(this.$form);
                this.$submit = $('<input type="submit" value="&#xe047;" disabled="disabled">').
                    addClass('vf-chat-submit').
                    appendTo(this.$form);

                $.each(this._projectData, function (i, project) {
                    var $projectContent;
                    if (!project.chatChannel) {
                        return;  // Skip if project doesn't have chat
                    }
                    $('<div/>').
                        addClass('vf-chat-project-button').
                        html('<img class="vf-chat-project-button-icon" src="'+ project.icon_url +'">' +
                             '<span class="vf-chat-project-button-label">' + project.name + '</span>').
                        attr('data-project', project.shortname).
                        appendTo(that.$projects);
                    $projectContent = $('<div/>').
                        addClass('vf-chat-project-content').
                        attr('data-project', project.shortname).
                        appendTo(that.$content);
                    $('<div/>').
                        addClass('vf-chat-project-users').
                        attr('data-project', project.shortname).
                        appendTo($projectContent);
                    $('<div/>').
                        addClass('vf-chat-project-messages').
                        attr('data-project', project.shortname).
                        appendTo($projectContent);
                });
                this.$container.appendTo('body');
            },
            bindEvents: function () {
                var that = this;
                this.$tab.bind({
                    'click': function () {
                        that.toggleChat.call(that);
                    }
                });
                this.$container.
                    bind('click', function () {
                        that.$textarea.focus();
                    }).
                    on('click', '.vf-chat-project-button', function () {
                        that.selectProject.call(that, $(this).attr('data-project'));
                    }).
                    on('submit', '.vf-chat-form', function (e) {
                        e.preventDefault();
                        e.stopPropagation();
                        that.postMessageToProject(that.$textarea.val().trim(), that._activeProjectName);
                        that.$textarea.val('');
                        that.$submit.attr('disabled', 'disabled');
                        that._autoScroll = true;
                    }).
                    on('keydown', '.vf-chat-textarea', function (e) {
                        if (e.keyCode === 13 && !e.shiftKey) {
                            e.preventDefault();
                            e.stopPropagation();
                            if (!that.$submit.prop('disabled')) {
                                that.$form.submit();
                            }
                        }
                    }).
                    on('keyup change focus blur', '.vf-chat-textarea', function (e) {
                        var value;
                        value = that.$textarea.val();
                        if (value.trim().length > 0) {
                            that.$submit.removeAttr('disabled');
                        } else {
                            that.$submit.attr('disabled', 'disabled');
                        }
                    });
                $('.vf-chat-project-messages').
                    on('scroll', function (e) {
                        var $messages = $(this);
                        that._autoScroll = $messages.prop('scrollHeight') - $messages.height() - 2 <= $messages.scrollTop();
                    });
                // register socket message handlers
                vfSocket.
                    addHandler(/^project\.([^\.]+).chat/, function (match, msg) {
                        var data = JSON.parse(msg.data),
                            shortname = match[1];
                        if (data.type === 'Post') {
                            that.renderMessageToProject(data.data, shortname);
                            if (shortname !== that._activeProjectName) {
                                that._unreadCounts[shortname] += 1;
                                console.log(that.$container.
                                    find('.vf-chat-project-button[data-project="' + shortname + '"]').
                                    attr('data-unread-count', that._unreadCounts[shortname]));
                            }
                        }
                    }).
                    addHandler(/^user\.([^\.]+)/, function (match, msg) {
                        var data = JSON.parse(msg.data);
                        if (data.type === 'UserOnline') {
                            that.updateUserOnline(match[1], true);
                        } else if (data.type === 'UserOffline') {
                            that.updateUserOnline(match[1], false);
                        }
                    });
            },
            // Preference storage/access methods
            pref: function (name, opt_value) {
                var key = this._storagePrefix + name,
                    method = (this._localStorage) ? this._prefLocalStorage : this._prefCookieStorage;
                return method.call(this, key, opt_value);
            },
            prefBool: function (name, opt_value) {
                return this.pref.call(this, name, opt_value) === 'true';
            },
            prefInt: function (name, opt_value) {
                return parseInt(this.pref.call(this, name, opt_value));
            },
            _prefLocalStorage: function (key, opt_value) {
                if (typeof opt_value !== 'undefined') {
                    localStorage[key] = opt_value;
                }
                return localStorage[key];
            },
            _prefCookieStorage: function (key, opt_value) {
                var response = $.cookie(key, opt_value);
                return typeof opt_value === 'undefined' ? response : opt_value.toString();
            },
            // states
            setIsOpen: function (value) {
                this.prefBool('open', this._isOpen = !!value);
                this.$container.
                    toggleClass('vf-chat-open', this._isOpen).
                    toggleClass('vf-chat-closed', !this._isOpen);
            },
            openChat: function () {
                this.setIsOpen(true);
            },
            closeChat: function () {
                this.setIsOpen(false);
            },
            toggleChat: function () {
                this.setIsOpen(!this._isOpen);
            },
            // scrolling
            scrollToBottom: function () {
                var $messages;
                if (this._autoScroll) {
                    $messages = this.$content.find('.vf-chat-project-messages:visible');
                    $messages.scrollTop($messages.prop('scrollHeight'));
                }
            },
            // projects
            getProjectDataByShortname: function (shortname) {
                return this._projectData[this._projectNameIndex[shortname]];
            },
            selectProject: function (shortname) {
                var that = this;
                this._autoScroll = true;
                this._activeProjectName = shortname;
                this.pref('project', shortname);
                $('.vf-chat-project-content', this.$container).
                    each(function () {
                        $(this).toggle($(this).attr('data-project') === shortname);
                    });
                $('.vf-chat-project-button', this.$container).
                    each(function () {
                        var $this = $(this),
                            newlySelected = $this.attr('data-project') === shortname;
                        $this.toggleClass('vf-chat-project-active', newlySelected);
                    });
                this._unreadCounts[shortname] = 0;
                this.$container.
                    find('.vf-chat-project-button[data-project="' + shortname + '"]').
                    removeAttr('data-unread-count');
                this.scrollToBottom();
            },
            // messages
            postMessageToProject: function (messageContent, projectName) {
                var projectData = this.getProjectDataByShortname(projectName);
                vfSocket.trigger({
                    'type': 'PostChatMessage',
                    'targets': [projectData.chatChannel],
                    'params': {
                        'message': messageContent,
                        'timestamp': new Date().toISOString()
                    }
                });
                this._autoScroll = true;
            },
            renderMessageToProject: function (messageData, projectName) {
                var that = this,
                    $projectMessages = $('.vf-chat-project-messages[data-project="'+projectName+'"]'),
                    $messageContainer = $("<div/>").
                        addClass('vf-chat-message-container').
                        toggleClass('vf-chat-current-user-message', messageData.author === $vf.logged_in_as).
                        attr('data-timestamp', messageData.timestamp);
                    this.renderUserWidget(messageData.author, $messageContainer);
                    $('<div/>').
                        addClass('vf-chat-message-content').
                        appendTo($messageContainer).
                        html(messageData.html).
                        find('img').
                        on('load', function () {
                            that.scrollToBottom.call(that);
                        });
                $projectMessages.append($messageContainer);
                that.scrollToBottom();
            },
            // users
            renderUserWidget: function (username, $container) {
                var that = this,
                    $widget = $('<img/>').
                        attr('data-username', username).
                        addClass('vf-chat-user-icon').
                        appendTo($container);
                this.withUserProfile(username, function (profile) {
                    $widget.
                        attr('title', profile.fullName + ' (' + username + ')').
                        attr('src', profile.profileImage).
                        qtip({
                            content: {
                                text: false
                            },
                            style: {
                                classes: 'vf-title-tip'
                            },
                            position: {
                                viewport: $(window),
                                at: 'bottom middle',
                                my: 'top right'
                            }
                        });
                });
            },
            renderUserListWidgetToProject: function (username, projectName) {
                var $projectUsers = $('.vf-chat-project-users[data-project="'+projectName+'"]');
                    this.renderUserWidget(username, $projectUsers);
            },
            withUserProfile: function (username, callback) {
                var that = this,
                    profile = this._userProfiles[username];
                if (typeof profile === 'undefined') {
                    this.loadUserProfile(username, function () {
                        var profile = this._userProfiles[username];
                        callback.call(that, profile);
                    });
                } else {
                    callback.call(this, profile);
                }
            },
            loadUserProfile: function (username, opt_callback) {
                var that = this;
                $.ajax({
                    'url': '/webs/websocket/chat/user/'+username,
                    'dataType': 'json',
                    'success': function (profileData) {
                        that._userProfiles[username] = profileData;
                        if (typeof opt_callback !== 'undefined') {
                            opt_callback.call(that);
                        }
                        that.updateUserOnline(username, profileData.online);
                    }
                });
            },
            updateUserOnline: function (username, value) {
                var profile = this._userProfiles[username];
                profile.online = value;
                this.$container.
                    find('.vf-chat-user-icon[data-username="' + username + '"]').
                    toggleClass('vf-chat-user-online', profile.online).
                    toggleClass('vf-chat-user-offline', !profile.online);
                this.sortUserLists();
            },
            sortUserLists: function () {
                var that = this;
                this.$container.
                    find('.vf-chat-project-users').
                    each(function (i) {
                        $(this).
                            find('.vf-chat-user-icon').
                            sort(function (a, b) {
                                var $a = $(a),
                                    $b = $(b);
                                if ($a.hasClass('vf-chat-user-online') === $b.hasClass('vf-chat-user-online')) {
                                    if ($a.attr('data-username') < $b.attr('data-username')) {
                                        return -1;
                                    } else if ($a.attr('data-username') > $b.attr('data-username')) {
                                        return 1;
                                    }
                                } else if ($a.hasClass('vf-chat-user-online') && !$b.hasClass('vf-chat-user-online')) {
                                    return -1;
                                } else {
                                    return 1;
                                }
                            }).
                            appendTo($(this));
                    });
            }
        };

        window.vfChat = vfChat;

        vfChat.init();
    });

})(jQuery);
