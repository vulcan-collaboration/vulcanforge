/**
 * Utilities for forms and form inputs
 */
(function ($) {
    'use strict';

    $.widget('vf.multicomplete', $.ui.autocomplete, {
        options: $.extend(true, {}, $.ui.autocomplete.options, {
            ignoreRe: null
        }),
        _value: function (value) {
            var terms;
            if (value !== undefined) {
                if (this.term) {
                    if (this.term === value) {
                        return this._super(value);
                    }
                    terms = this.term.split( /,\s*/);
                } else {
                    terms = [];
                }
                terms.pop();
                terms.push(value);
                terms.push("");
                value = terms.join(", ");
                return this._super(value);
            }
            return this._super();
        },
        _extractLast: function (term) {
            return term.split( /,\s*/).pop();
        },
        search: function (v, e) {
            var value = this.element.val();
            if (value) {
                value = this._extractLast(value);
                if (this.options.ignoreRe !== null && this.options.ignoreRe.test(value)) {
                    return false;
                }
            }
            return this._super(value, e);
        }
    });

}(window.jQuery));