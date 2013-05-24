/*global window*/

/*
 * Initializing auto_resize_textarea widget.
 *
 * @author Naba Bana
 */
(function (global) {
    "use strict";

    // Local globals
    var $ = global.$;

    $(function() {
        $('textarea.auto_resize').elastic().focus(function(){
            $(this).keyup();
        });
    });
}(window));