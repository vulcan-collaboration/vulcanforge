(function ($) {

    var deltaSecondsToString = function (oldDate, newDate) {
        var delta = Math.floor((newDate - oldDate) / 1000);
        if (delta < 60) {
            return 'less than a minute ago';
        }
        if (delta < 120) {
            return 'about a minute ago';
        }
        if (delta >= 120 && delta < 60 * 60) {
            return Math.floor(delta / 60) + ' minutes ago';
        }
        if (delta >= 60 * 60 && delta < 60 * 60 * 2) {
            return Math.floor(delta / (60 * 60)) + ' hour ago';
        }
        if (delta >= 60 * 60 * 2 && delta < 60 * 60 * 24) {
            return Math.floor(delta / (60 * 60)) + ' hours ago';
        }
        if (delta >= 60 * 60 * 24 && delta < 60 * 60 * 24 * 2) {
            return 'yesterday';
        }
        if (delta >= 60 * 60 * 24 && delta < 60 * 60 * 24 * 30) {
            return Math.floor(delta / (60 * 60 * 24)) + ' days ago';
        }
        return oldDate.toString();
    };

    $.fn.relativeDate = function () {
        return this.each(function() {
            $(this).bind('relativeDate',
                function () {
                    var d = $(this).data('timestamp');
                    $(this).text(deltaSecondsToString(d, new Date()));
                }).trigger('relativeDate');
            var $this = $(this);
            setInterval(function () {
                $this.trigger('relativeDate');
            }, 10000);
        });
    };

})(jQuery);
