/**
 * Created by PyCharm.
 * User: tannern
 * Date: 11/8/11
 * Time: 12:55 PM
 */

(function ($) {

    "use strict";

    var settings = {
        jsonURL:false,
        jsonData:null,
        jsonProperty:'',
        updateDelay:false,
        queueName:'updateFromJson',
        callback:false
    };

    var methods = {
        init:function (options) {
            return this.each(function () {
                var $this = $(this);
                if (options) {
                    $.extend(settings, options);
                }

                if (!settings.jsonURL) $.error('jsonURL option is required');

                $this.updateFromJSON('start');
            });
        },
        update:function (data) {
            return this.each(function () {
                var $this = $(this);

                var successCallback = function (data, status, xhr) {
                    $this.text(data[settings.jsonProperty]);
                    if (settings.callback) {
                        settings.callback.call($this, data, status, xhr);
                    }
                };

                if (data) {
                    successCallback(data);
                }
                else {
                    $.ajax({
                        url:settings.jsonURL,
                        dataType:'json',
                        data:settings.jsonData,
                        context:$this,
                        success:successCallback
                    });
                }
            });
        },
        start:function () {
            return this.each(function () {
                var $this = $(this);
                $this.updateFromJSON('update');
                if (settings.updateDelay) {
                    var fn = function () {
                        $this.updateFromJSON('update');
                    };
                    var interval = setInterval(fn, settings.updateDelay);
                    $this.data('interval', interval);
                }
            });
        },
        stop:function () {
            return this.each(function () {
                var interval = $(this).data('interval');
                clearInterval(interval);
            });
        }
    };

    $.fn.updateFromJSON = function (method) {
        if (methods[method]) {
            return methods[method].apply(this, Array.prototype.slice.call(arguments, 1));
        } else if (typeof method === 'object' || !method) {
            return methods.init.apply(this, arguments);
        } else {
            $.error('Method ' + method + ' does not exist on updateFromJSON');
        }
    };

})(jQuery);
