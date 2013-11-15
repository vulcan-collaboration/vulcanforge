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
                    that.bindEvents();
                    $.each(that._projectData, function (i, project) {
                        if (project.chatChannel) {
                            vfSocket.subscribe(project.chatChannel);
                            $.each(project.chatMessages, function (i, msg) {
                                that.renderMessageToProject(msg.data, project.shortname);
                            });
                            if (!activeProjectName) {
                                activeProjectName = project.shortname;
                            }
                        }
                    });
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
                this.$projects = $('<div/>').
                    addClass('vf-chat-projects-list').
                    appendTo(this.$header);
                this.$users = $('<div/>').
                    addClass('vf-chat-users').
                    appendTo(this.$header);
                this.$content = $('<div/>').
                    addClass('vf-chat-content').
                    appendTo(this.$panelContainer);
                this.$formContainer = $('<div/>').
                    addClass('vf-chat-form-container').
                    appendTo(this.$panelContainer);
                this.$form = $('<form/>').
                    addClass('vf-chat-form').
                    appendTo(this.$formContainer);
                this.$textarea = $('<textarea name="message">').
                    addClass('vf-chat-textarea').
                    appendTo(this.$form);
                this.$submit = $('<input type="submit" value="&#xe047;" disabled="disabled">').
                    addClass('vf-chat-submit').
                    appendTo(this.$form);
                $.each(this._projectData, function (i, v) {
                    if (!v.chatChannel) {
                        return true;  // Skip if project doesn't have chat
                    }
                    $('<div/>').
                        addClass('vf-chat-project-button').
                        html('<img class="vf-chat-project-button-icon" src="'+ v.icon_url +'">' +
                             '<span class="vf-chat-project-button-label">' + v.name + '</span>').
                        attr('data-project', v.shortname).
                        appendTo(that.$projects);
                    $('<div/>').
                        addClass('vf-chat-project-content').
                        attr('data-project', v.shortname).
                        appendTo(that.$content);
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
                    }).
                    on('keydown', '.vf-chat-textarea', function (e) {
                        if (e.keyCode === 13 && !e.shiftKey) {
                            e.preventDefault();
                            e.stopPropagation();
                            that.$form.submit();
                        }
                    }).
                    on('keyup', '.vf-chat-textarea', function (e) {
                        var value;
                        value = that.$textarea.val();
                        if (value.trim().length > 0) {
                            that.$submit.removeAttr('disabled');
                        } else {
                            that.$submit.attr('disabled', 'disabled');
                        }
                    });
                this.$content.
                    on('scroll', function (e) {
                        that._autoScroll = that.$content.prop('scrollHeight') - that.$content.height() - 10 <= that.$content.scrollTop();
                    });
                // register socket message handlers
                vfSocket.
                    addHandler(/^project\.([^\.]+).chat/, function (match, msg) {
                        var data = JSON.parse(msg.data);
                        if (data.type === 'Post') {
                            that.renderMessageToProject(data.data, match[1]);
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
            //
            getProjectDataByShortname: function (shortname) {
                return this._projectData[this._projectNameIndex[shortname]];
            },
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
            jumpToBottomOfChat: function () {
                if (this._autoScroll) {
                    this.$content.scrollTop(this.$content.prop('scrollHeight'));
                }
            },
            selectProject: function (projectName) {
                this._autoScroll = true;
                this._activeProjectName = projectName;
                this.pref('project', projectName);
                $('.vf-chat-project-content', this.$container).
                    each(function () {
                        $(this).toggle($(this).attr('data-project') === projectName);
                    });
                $('.vf-chat-project-button', this.$container).
                    each(function () {
                        var $this = $(this);
                        $this.toggleClass('vf-chat-project-active', $this.attr('data-project') === projectName);
                    });
            },
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
            },
            renderMessageToProject: function (messageData, projectName) {
                var $projectContent = $('.vf-chat-project-content[data-project="'+projectName+'"]'),
                    $messageContainer = $("<div/>").
                        addClass('vf-chat-message-container').
                        toggleClass('vf-chat-current-user-message', messageData.author === $vf.logged_in_as).
                        attr('data-timestamp', messageData.timestamp),
                    $author = this.renderAuthorWidget(messageData.author, $messageContainer),
                    $messageContent = $('<div/>').
                        addClass('vf-chat-message-content').
                        appendTo($messageContainer).
                        html(messageData.html);
                $projectContent.append($messageContainer);
            },
            renderAuthorWidget: function (username, $container) {
                var that = this,
                    userProfile = this._userProfiles[username];
                if (typeof userProfile === 'undefined') {
                    this.loadUserProfile(username, function () {
                        that.renderAuthorWidget.call(that, username, $container);
                    });
                } else {
                    $('<img/>').
                        attr('src', userProfile.profileImage).
                        attr('title', userProfile.fullName + ' (' + username + ')').
                        addClass('vf-chat-user-icon').
                        appendTo($container);
                }
            },
            loadUserProfile: function (username, opt_callback) {
                var that = this;
                $.ajax({
                    'url': '/u/'+username+'/profile/get_user_profile',
                    'dataType': 'json',
                    'success': function (profileData) {
                        that._userProfiles[username] = profileData;
                        if (typeof opt_callback !== 'undefined') {
                            opt_callback.call(that);
                        }
                    }
                })
            }
        };

        window.VF_CHAT = vfChat;
        vfChat.init();
    });

})(jQuery);
