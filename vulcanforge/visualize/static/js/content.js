(function (global) {
    "use strict";
    var $ = global.jQuery,
        AltResourceManager;

    /* Alternate Resource Manager */
    AltResourceManager = function(altRest, config) {

        /* locals */
        var that = this;

        /* spec parameters */
        this.altRest = altRest;
        this.pollInterval = config.pollInterval || 5000;
        this.processor = config.processor || null;
        this.renderFunc = config.render || $.noop;
        this.loadingFunc = config.loading || $.noop;
        this.errorFunc = config.errorFunc || $.noop;
        this.context = config.context || "ondemand";
        this.data = config.data || {};

        this.requested = false;

        this.poll = function() {
            var data = $.extend({}, that.data, {context: that.context});
            $.ajax({
                url: that.altRest,
                type: "GET",
                dataType: 'json',
                data: data,
                success: function(response) {
                    if (response['status'] === 'dne') {
                        if (that.requested){
                            that.processingError();
                        } else {
                            that.triggerProcessing();
                        }
                    } else if (response['status'] == 'loading') {
                        that.loadingFunc();
                        setTimeout(that.poll, that.pollInterval);
                    } else if (response['url']) {
                        that.renderResource(response['url']);
                    } else {
                        that.processingError();
                    }
                },
                error: this.processingError
            });
        };

        this.triggerProcessing = function() {
            var data = $.extend({}, that.data, {
                context: that.context,
                processor: that.processor,
                _session_id: $.cookie('_session_id')
            });
            that.requested = true;
            $.ajax({
                url: that.altRest,
                type: "POST",
                dataType: 'json',
                data: data,
                success: function(response) {
                    if (response['success']) {
                        that.poll();
                    } else {
                        that.processingError();
                    }
                },
                error:this.processingError
            });
        };

        this.renderResource = function(url) {
            console.log('rendering ' + url);
            this.renderFunc(url);
        };

        this.processingError = function() {
            console.log('processing error');
            that.errorFunc();
        };

    };

    AltResourceManager.prototype = {};

    window.AltResourceManager = AltResourceManager;

}(window));
