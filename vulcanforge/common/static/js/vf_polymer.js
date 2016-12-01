'use strict';

// include additional polyfills related to stupid browsers
if (!String.prototype.endsWith) {
  String.prototype.endsWith = function(searchString, position) {
      var subjectString = this.toString();
      if (typeof position !== 'number' || !isFinite(position) || Math.floor(position) !== position || position > subjectString.length) {
        position = subjectString.length;
      }
      position -= searchString.length;
      var lastIndex = subjectString.lastIndexOf(searchString, position);
      return lastIndex !== -1 && lastIndex === position;
  };
}

// utilitiy functions
var vffuncs = {
    humanSize: function (size) {
        if (size === 1) {
            return "1 byte";
        }
        var steps = [
                    1,
                    1000,
                    Math.pow(1000, 2),
                    Math.pow(1000, 3),
                    Math.pow(1000, 4),
                    Math.pow(1000, 5)
                ],
                labels = [
                    'bytes', 'KB', 'MB', 'GB', 'TB', 'PB'
                ],
                i, x;
        for (i = steps.length; i >= 0; --i) {
            x = size / steps[i];
            if (x > 1) {
                return vffuncs.roundToDecimal(x, 2) + ' ' + labels[i];
            }
        }
    },
    roundToDecimal: function (i, places) {
        var factor = Math.pow(10, places);
        return Math.round(i * factor) / factor;
    },
    convertUTC: function(ts) {
        var d = new Date((isNaN(Date.parse(ts))) ? ts.replace(' ', 'T') : ts);
        var isSafari = (navigator.userAgent.search("Safari") >= 0 && navigator.userAgent.search("Chrome") < 0);
        if (!isSafari) {
            var nd = new Date();
            nd.setUTCDate(d.getDate());
            nd.setUTCFullYear(d.getFullYear());
            nd.setUTCMonth(d.getMonth());
            nd.setUTCHours(d.getHours());
            nd.setUTCMinutes(d.getMinutes());
            nd.setUTCSeconds(d.getSeconds());
            return nd;
        }
        return d;
    },
    formatDate: function(date) {
        if (date) {
            var dobj = vffuncs.convertUTC(date);
            return dobj.toLocaleDateString('en', {
                day : 'numeric',
                month : 'short',
                year : 'numeric'
            });
        }
        return "";
    },
    formatTime: function(ts) {
        return vffuncs.convertUTC(ts).toLocaleString();
    },
    ago: function(olderDate, newerDate) {
        if (typeof olderDate == "string") {
            olderDate = new Date(olderDate);
        }
        if (typeof newerDate == "string") {
            newerDate = vffuncs.convertUTC(newerDate);
        } else if (typeof newerDate == "undefined") {
            var isMS = !(window.ActiveXObject) && "ActiveXObject" in window || /Edge/.test(navigator.userAgent);
            newerDate = new Date();
            if (isMS) {
                var utc_offset_ms = newerDate.getTimezoneOffset() * 60 * 1000;
                newerDate = new Date(new Date().getTime() + utc_offset_ms);
            }
        }
        var milliseconds = newerDate - olderDate;
        var conversions = [
            ["years", 31518720000],
            ["months", 2626560000 /* assumes there are 30.4 days in a month */],
            ["days", 86400000],
            ["hours", 3600000],
            ["minutes", 60000],
            ["seconds", 1000]
        ];
        for (var i=0;i<conversions.length; i++) {
            var result = Math.floor(milliseconds / conversions[i][1]);
            if (result >= 2) {
                return result + " " + conversions[i][0] + " ago";
            }
        }
        return "1 second ago";
    },
    removeElement: function(arr) {
        var what, a = arguments, L = a.length, ax;
        while (L > 1 && arr.length) {
            what = a[--L];
            while ((ax= arr.indexOf(what)) !== -1) {
                arr.splice(ax, 1);
            }
        }
        return arr;
    }
};
