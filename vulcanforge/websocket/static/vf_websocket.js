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
    var wsProtocol = (window.location.protocol === 'https:') ? 'wss' : 'ws',
        vfSocket = $vf.webSocket = {
            socketURL: wsProtocol + '://' + window.location.host + '/ws/',
            _socket: null,
            _handlers: [],
            _subscriptions: [],
            _retryCount: 0,
            _init: function () {
                vfSocket._connect();
                $(window).trigger('VFWebSocketInit', vfSocket);
            },
            _connect: function () {
                vfSocket._socket = new WebSocket(vfSocket.socketURL);
                vfSocket._socket.addEventListener('open', vfSocket._handleOpen);
                vfSocket._socket.addEventListener('message', vfSocket._handleMessage);
                vfSocket._socket.addEventListener('close', vfSocket._handleClose);
                vfSocket._socket.addEventListener('error', vfSocket._handleError);
            },
            _testHandler: function (handler, channel) {
                return channel.match(handler.pattern);
            },
            // ## events
            _handleOpen: function (e) {
                if (vfSocket._subscriptions.length) {
                    vfSocket.subscribe(vfSocket._subscriptions);
                }
            },
            _handleClose: function (e) {
                var delay = Math.pow(2, vfSocket._retryCount) * 1000;
                vfSocket._retryCount += 1;
                setTimeout(vfSocket._connect, delay);
            },
            _handleError: function (e) {
                console.error(e);
            },
            _handleMessage: function (e) {
                var msg = JSON.parse(e.data);
                vfSocket._retryCount = 0;  // TODO: find a better way to reset the retry count
                if (DEBUG) {
                    console.debug(msg);
                }
                switch (msg.type) {
                case 'error':
                    console.warn(msg.data.kind + ': ' + msg.data.message);
                    break;
                case 'message':
                    $.each(vfSocket._handlers, function (i, handler) {
                        var match = vfSocket._testHandler(handler, msg.channel);
                        if (match) {
                            handler.func(match, msg);
                        }
                    });
                    break;
                case 'subscribe':
                    if (vfSocket._subscriptions.indexOf(msg.channel) === -1) {
                        vfSocket._subscriptions.push(msg.channel);
                    }
                    break;
                case 'unsubscribe':
                    vfSocket._subscriptions =
                        vfSocket._subscriptions.filter(function (item) {
                            return item !== msg.channel;
                        });
                    break;
                }
            },
            // ## interface
            subscribe: function (channels) {
                if (!(channels instanceof Array)) {
                    channels = [channels];
                }
                vfSocket._socket.send(JSON.stringify({
                    'subscribe': channels
                }));
                return vfSocket;
            },
            unsubscribe: function (channels) {
                if (!(channels instanceof Array)) {
                    channels = [channels];
                }
                vfSocket._socket.send(JSON.stringify({
                    'unsubscribe': channels
                }));
                return vfSocket;
            },
            trigger: function (eventSpec) {
                vfSocket._socket.send(JSON.stringify({
                    'trigger': eventSpec
                }));
                return vfSocket;
            },
            publish: function (channels, message) {
                if (!(channels instanceof Array)) {
                    channels = [channels];
                }
                vfSocket._socket.send(JSON.stringify({
                    'publish': {
                        'channels': channels,
                        'message': message
                    }
                }));
                return vfSocket;
            },
            addHandler: function (channelPattern, func) {
                vfSocket._handlers.push({
                    'pattern': channelPattern,
                    'func': func
                });
                return vfSocket;
            },
            removeHandlers: function (pattern) {
                vfSocket._handlers = vfSocket._handlers.filter(function (handler) {
                    return !vfSocket._testHandler(handler, pattern);
                });
                return vfSocket;
            }
        };
    if (WebSocket) {
        $vf.afterInit(vfSocket._init, []);
    } else {
        console.warn("WebSocket is not available in this browser.");
    }
})(jQuery);
