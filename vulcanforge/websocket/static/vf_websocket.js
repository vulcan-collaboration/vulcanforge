/**
 * vf_websocket
 *
 * :author: tannern
 * :date: 7/8/13
 */

(function ($) {
    'use strict';
    if (!$vf) {
        console.warn("vf_websocket.js depends on vf.js and must be loaded after it");
        return;
    }
    var VFSOCK = $vf.webSocket = {
        socketURL: 'ws://' + window.location.host + '/ws',
        ws: null,
        handlers: [],
        subscriptions: [],
        _init: function () {
            if ($vf.logged_in_as) {
                VFSOCK.userChannel = 'user.username.' + $vf.logged_in_as;
                VFSOCK.subscriptions.push(VFSOCK.userChannel);
            }
            VFSOCK._connect();
        },
        _connect: function () {
            VFSOCK.ws = new WebSocket(VFSOCK.socketURL, "vulcanForge");
            VFSOCK.ws.addEventListener('open', VFSOCK._handleOpen);
            VFSOCK.ws.addEventListener('message', VFSOCK._handleMessage);
            VFSOCK.ws.addEventListener('close', VFSOCK._handleClose);
        },
        _testHandler: function (handler, channel) {
            return channel.match(handler.pattern);
        },
        // ## events
        _handleOpen: function (e) {
            if (VFSOCK.subscriptions.length) {
                VFSOCK.subscribe(VFSOCK.subscriptions);
            }
        },
        _handleClose: function (e) {
            setTimeout(VFSOCK._connect, 1000);  // connection lost wait 1 sec and try again
        },
        _handleMessage: function (e) {
            var msg = JSON.parse(e.data);
            switch (msg.type) {
            case 'error':
                console.warn(msg.data.kind + ': ' + msg.data.message);
                break;
            case 'message':
                $.each(VFSOCK.handlers, function (i, handler) {
                    var match = VFSOCK._testHandler(handler, msg.channel);
                    if (match) {
                        handler.func(match, msg);
                    }
                });
                break;
            case 'subscribe':
                if (VFSOCK.subscriptions.indexOf(msg.channel) === -1) {
                    VFSOCK.subscriptions.push(msg.channel);
                }
                break;
            case 'unsubscribe':
                VFSOCK.subscriptions = VFSOCK.subscriptions.filter(function (item) {
                    return item !== msg.channel;
                });
                break;
            }
        },
        // ## interface
        subscribe: function (channels) {
            VFSOCK.ws.send(JSON.stringify({
                'subscribe': channels
            }));
        },
        unsubscribe: function (channels) {
            VFSOCK.ws.send(JSON.stringify({
                'unsubscribe': channels
            }));
        },
        trigger: function (eventSpec) {
            VFSOCK.ws.send(JSON.stringify({
                'trigger': eventSpec
            }));
        },
        publish: function (channels, message) {
            VFSOCK.ws.send(JSON.stringify({
                'publish': {
                    'channels': channels,
                    'message': message
                }
            }));
        },
        addHandler: function (pattern, func) {
            VFSOCK.handlers.push({
                'pattern': pattern,
                'func': func
            });
        },
        removeHandlers: function (pattern) {
            VFSOCK.handlers = VFSOCK.handlers.filter(function (handler) {
                return VFSOCK._testHandler(handler, pattern);
            });
        }
    };
    if (WebSocket) {
        $vf.afterInit(VFSOCK._init, []);
    } else {
        console.warn("WebSocket is not available in this browser.");
    }
})(jQuery);
