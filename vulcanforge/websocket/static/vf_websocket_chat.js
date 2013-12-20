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
                        console.debug('No projects with chat found, disabling chat');
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
                    'success': function (stateData) {
                        that._projectData = stateData.projects;
                        that._userProfiles = stateData.users;
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

                this.$projectListContainer = $('<div/>').
                    addClass('vf-chat-projects-list-container').
                    appendTo(this.$container);
                this.$projectListToolbar = $('<div/>').
                    addClass('vf-chat-toolbar').
                    addClass('vf-chat-project-list-toolbar').
                    appendTo(this.$projectListContainer);
                this.$projectList = $('<div/>').
                    addClass('vf-chat-projects-list').
                    appendTo(this.$projectListContainer);
                $('<button/>').
                    text('\u2713').
                    addClass('vf-chat-close-project-list-button').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-icon-item').
                    appendTo(this.$projectListToolbar);
                $('<h2/>').
                    text('Projects').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-stretchy-item').
                    appendTo(this.$projectListToolbar);

                this.$panelContainer = $('<div/>').
                    addClass('vf-chat-panel-container').
                    appendTo(this.$container);

                this.$header = $('<div/>').
                    addClass('vf-chat-header').
                    appendTo(this.$panelContainer);
                this.$mainToolbar = $('<div/>').
                    addClass('vf-chat-toolbar').
                    addClass('vf-chat-main-toolbar').
                    appendTo(this.$header);
                this.$content = $('<div/>').
                    addClass('vf-chat-content').
                    appendTo(this.$panelContainer);
                this.$formContainer = $('<div/>').
                    addClass('vf-chat-form-container').
                    appendTo(this.$panelContainer);

                this.$projectToolbar = $('<div/>').
                    addClass('vf-chat-toolbar').
                    addClass('vf-chat-project-toolbar').
                    appendTo(this.$header);

                // Main Toolbar
                this.$projectSelect = $('<button/>').
                    text('\ue055').
                    //text('\u25bc').
                    attr('title', 'Projects').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-icon-item').
                    addClass('vf-chat-toolbar-project-select').
                    appendTo(this.$mainToolbar);
                this.$activeProjectContainer = $('<div/>').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-active-project-container').
                    appendTo(this.$mainToolbar);
                $('<span/>').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-stretchy-item').
                    appendTo(this.$mainToolbar);
                $('<button/>').
                    text('\u2302').
                    attr('title', 'View Project Home').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-icon-item').
                    addClass('vf-chat-toolbar-project-home').
                    appendTo(this.$mainToolbar);
                $('<button/>').
                    text('\ue079').
                    attr('title', 'Browse Chat Transcripts').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-icon-item').
                    addClass('vf-chat-toolbar-chat-transcripts').
                    appendTo(this.$mainToolbar);

                // Project Toolbar
                $('<span/>').
                    text('\ue062').
                    attr('title', 'Online users').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-icon-item').
                    appendTo(this.$projectToolbar);
                this.$userListContainer = $('<div/>').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-users-container').
                    appendTo(this.$projectToolbar);
                $('<span/>').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-stretchy-item').
                    appendTo(this.$projectToolbar);
                /*$('<button/>').
                    text('\ue08a').
                    attr('title', 'Attach a file').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-icon-item').
                    addClass('vf-chat-toolbar-attach').
                    appendTo(this.$toolbar);*/
                $('<button/>').
                    text('\ue068').
                    //text('\ue02e').
                    attr('title', 'Share current page').
                    addClass('vf-chat-toolbar-item').
                    addClass('vf-chat-toolbar-icon-item').
                    addClass('vf-chat-toolbar-share-location').
                    appendTo(this.$projectToolbar);

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
                        appendTo(that.$projectList);
                    $projectContent = $('<div/>').
                        addClass('vf-chat-project-content').
                        attr('data-project', project.shortname).
                        appendTo(that.$content);
                    $('<div/>').
                        addClass('vf-chat-users').
                        attr('data-project', project.shortname).
                        appendTo(that.$userListContainer);
                });
                this.$container.appendTo('body');
            },
            bindEvents: function () {
                var that = this;
                this.$tab.bind({
                    'click': function (e) {
                        e.preventDefault();
                        e.stopPropagation();
                        that.toggleChat.call(that);
                    }
                });
                this.$container.
                    on('click', function () {
                        that.$textarea.focus();
                    }).
                    on('transitionend webkitTransitionEnd oTransitionEnd', function (e) {
                        if (that._isOpen) {
                            that.$textarea.focus();
                        }
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
                    on('keyup change focus blur refreshInputEnabled.vfChat', '.vf-chat-textarea', function (e) {
                        var value;
                        value = that.$textarea.val();
                        if (value.trim().length > 0) {
                            that.$submit.removeAttr('disabled');
                        } else {
                            that.$submit.attr('disabled', 'disabled');
                        }
                    }).
                    on('click', '.vf-chat-toolbar-share-location', function (e) {
                        var title = document.title,
                            href = window.location.href;
                        e.preventDefault();
                        e.stopPropagation();
                        /*that.shareLocationToProject(that._activeProjectName);*/
                        that.$textarea.
                            val(that.$textarea.val() + ' [' + title + '](' + href + ') ').
                            trigger('refreshInputEnabled.vfChat');
                    }).
                    on('click', '.vf-chat-toolbar-project-home', function (e) {
                        var projectData = that.getProjectDataByShortname(that._activeProjectName);
                        e.preventDefault();
                        e.stopPropagation();
                        window.location.href = projectData.url;
                    }).
                    on('click', '.vf-chat-toolbar-chat-transcripts', function (e) {
                        var projectData = that.getProjectDataByShortname(that._activeProjectName);
                        e.preventDefault();
                        e.stopPropagation();
                        window.location.href = projectData.url + 'chat/';
                    }).
                    on('click', '.vf-chat-toolbar-project-select, .vf-chat-active-project-container', function (e) {
                        that.openProjectList.call(that);
                    }).
                    /*on('mouseleave', '.vf-chat-projects-list-container', function (e) {
                        that.closeProjectList.call(that);
                    }).*/
                    on('click', '.vf-chat-close-project-list-button', function (e) {
                        that.closeProjectList.call(that);
                    }).
                    on('UserOnline.vfchat', function (e, username, data) {
                        that.updateUserOnline(username, true);
                    }).
                    on('UserOffline.vfchat', function (e, username, data) {
                        that.updateUserOnline(username, false);
                    });
                $('.vf-chat-project-content').
                    on('scroll', function (e) {
                        var $messages = $(this);
                        that._autoScroll = $messages.prop('scrollHeight') - $messages.height() - 2 <= $messages.scrollTop();
                    });
                // register socket message handlers
                vfSocket.
                    addHandler(/^project\.([^\.]+).chat/, function (match, msg) {
                        var data = JSON.parse(msg.data),
                            projectName = match[1];
                        if (data.type === 'Post') {
                            that.renderMessageToProject(data.data, projectName);
                            if (projectName !== that._activeProjectName) {
                                that._unreadCounts[projectName] += 1;
                                that.updateUnreadCountAttributes();
                            }
                        } else if (data.type === 'LocationShared') {
                            that.renderSharedLocationToProject(data.data, projectName);
                        }
                    }).
                    addHandler(/^user\.([^\.]+)/, function (match, msg) {
                        var data = JSON.parse(msg.data);
                        that.$container.trigger(data.type + '.vfchat', [match[1], data]);
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
            setProjectListIsOpen: function (value) {
                this.$projectListContainer.
                    toggleClass('vf-chat-project-list-container-open', value);
            },
            openProjectList: function () {
                this.setProjectListIsOpen(true);
            },
            closeProjectList: function () {
                this.setProjectListIsOpen(false);
            },
            // scrolling
            scrollToBottom: function () {
                var $messages;
                if (this._autoScroll) {
                    $messages = this.$content.find('.vf-chat-project-content:visible');
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
                $('.vf-chat-project-content, .vf-chat-users', this.$container).
                    each(function () {
                        $(this).toggle($(this).attr('data-project') === shortname);
                    });
                $('.vf-chat-project-button', this.$container).
                    each(function () {
                        var $this = $(this),
                            newlySelected = $this.attr('data-project') === shortname;
                        $this.toggleClass('vf-chat-project-active', newlySelected);
                        if (newlySelected) {
                            that.$activeProjectContainer.html($this.clone());
                        }
                    });
                this._unreadCounts[shortname] = 0;
                this.$container.
                    find('.vf-chat-project-button[data-project="' + shortname + '"]').
                    removeAttr('data-unread-count');
                this.scrollToBottom();
                this.closeProjectList();
                this.updateUnreadCountAttributes();
            },
            updateUnreadCountAttributes: function () {
                var that = this, total = 0;
                $.each(this._unreadCounts, function (projectName, count) {
                    var $projectButtons = that.$container.
                        find('.vf-chat-project-button[data-project="' + projectName + '"]');
                    total += count;
                    if (count > 0) {
                        $projectButtons.attr('data-unread-count', that._unreadCounts[projectName]);
                    } else {
                        $projectButtons.removeAttr('data-unread-count');
                    }
                });
                if (total > 0) {
                    this.$projectSelect.
                        add(this.$tab).
                        attr('data-unread-count', total);
                } else {
                    this.$projectSelect.
                        add(this.$tab).
                        removeAttr('data-unread-count');
                }
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
                    $projectMessages = $('.vf-chat-project-content[data-project="'+projectName+'"]'),
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
                    that.updateUserOnline(username, profile.online);
                });
            },
            renderUserListWidgetToProject: function (username, projectName) {
                var $projectUsers = $('.vf-chat-users[data-project="'+projectName+'"]');
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
                    find('.vf-chat-users').
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
            },
            // share location events
            shareLocationToProject: function(projectName) {
                var projectData = this.getProjectDataByShortname(projectName);
                vfSocket.trigger({
                    'type': 'ShareLocationWithChat',
                    'targets': [projectData.chatChannel],
                    'params': {
                        'title': document.title,
                        'href': window.location.href,
                        'timestamp': new Date().toISOString()
                    }
                });
                this._autoScroll = true;
            },
            renderSharedLocationToProject: function (msgData, projectName) {
                var $content = $('<span/>');
                this.renderUserWidget(msgData.author, $content);
                $content.append(' shared their location: ');
                $('<a/>').
                    attr('href', msgData.href).
                    text(msgData.title).
                    appendTo($content);
                this.renderNotificationToProject($content, msgData, projectName);
            },
            renderNotificationToProject: function ($content, msgData, projectName) {
                var that = this,
                    $projectContent = $('.vf-chat-project-content[data-project="'+projectName+'"]'),
                    $notificationContainer = $("<div/>").
                        addClass('vf-chat-notification-container').
                        attr('data-timestamp', msgData.timestamp);
                    $('<div/>').
                        addClass('vf-chat-notification-content').
                        appendTo($notificationContainer).
                        html($content).
                        find('img').
                        on('load', function () {
                            that.scrollToBottom.call(that);
                        });
                $projectContent.append($notificationContainer);
                that.scrollToBottom();
            }
        };

        window.vfChat = vfChat;

        vfChat.init();
    });

})(jQuery);
