/**
 * Utilities for forms and form inputs
 */
(function($){
    'use strict';

    $.widget('vf.multicomplete', $.ui.autocomplete, {
        options: $.extend(true, {}, $.ui.autocomplete.options, {
            ignoreRe: null,
            select: function(ev, ui) {
                var terms = this.value.split( /,\s*/);
                terms.pop();
                terms.push(ui.item.value);
                terms.push("");
                this.value = terms.join(", ");
                return false;
            }
        }),
        _extractLast: function(term) {
            return term.split( /,\s*/).pop();
        },
        search: function(v, e) {
            var value = this.element.val();
            if (value){
                value = this._extractLast(value);
                if ( this.options.ignoreRe !== null && this.options.ignoreRe.test(value) ) {
                    return false;
                }
            }
            return this._super(value, e);
        }
    });

}(jQuery));