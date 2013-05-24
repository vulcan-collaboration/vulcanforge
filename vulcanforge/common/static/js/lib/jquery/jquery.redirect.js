/*globals window, jQuery */
(function() {
    "use strict";
    jQuery.redirect = function(params, forceRedirect) {

        var key,
            search = window.location.search || '',
            origin = window.location.origin || '',
            pathname = window.location.pathname,
            url;

        search =  search.match(/\?/) ? search : search + '?';

        for (key in params ) {
            var re = new RegExp( ';?' + key + '=?[^&;]*', 'g' );
            search = search.replace( re, '');
            search += ';' + key + '=' + params[key];
        }
        // cleanup url
        url = origin + pathname + search;
        url = url.replace(/[;&]$/, '');
        url = url.replace(/\?[;&]/, '?');
        url = url.replace(/[;&]{2}/g, ';');
        // $(location).attr('href', url);
        if (window.history.replaceState && !forceRedirect) {
            window.history.replaceState({}, window.document.title, url);
        } else {
            window.location.assign(url);
        }
    };
}());