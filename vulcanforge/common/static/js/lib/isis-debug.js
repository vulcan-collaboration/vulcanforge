/**
 * isis-debug
 *
 * :author: tannern
 * :date: 2/6/12
 */

(function(isis){

    var debug = isis.debug = {};

    /**
     * define log levels
     */
    debug.Level = isis.freeze({
        DEFAULT:2,
        OFF:0,
        MINIMAL:1,
        NORMAL:2,
        DETAILED:3,
        TIMED:4
    });

    /**
     * Wraps a given prototype's methods with logging groups to track log
     * statements and execution path.
     *
     * @param prototype     the prototype to wrap
     * @param className     the class name since it cannot be reliably inferred
     *                      across browsers
     * @param level         the log level
     *                          default: debug.Level.MINIMAL
     */
    debug.logObject = function (prototype, className, level) {
        /** defaults */
        path = isis.isDefined(className) ? className : path + '.' + className;
        level = isis.isDefined(level) ? level : debug.Level.DEFAULT;

        /** define decorators */
        var wrapFunction = function (fn, key, path) {
            var name = path + '.' + key;
            var wrapped = function () {
                var result;
                var error = null;
                if (level >= debug.Level.MINIMAL) {
                    console.group(name);
                }
                if (level >= debug.Level.TIMED) {
                    console.time(name);
                }
                if (level >= debug.Level.NORMAL) {
                    if (level >= debug.Level.TIMED) {
                        console.timeEnd(name);
                    }
                    if (level >= debug.Level.DETAILED) {
                        console.debug('caller:', arguments.callee.caller);
                    }
                    console.debug('context:', this);
                    console.debug('arguments:', arguments);
                }
                try {
                    result = fn.apply(this, arguments);
                } catch (err) {
                    error = err;
                }
                if (error !== null) {
                    console.warn('threw:', err);
                } else {
                    console.debug('returned:', result);
                }
                if (level >= debug.Level.MINIMAL) {
                    console.groupEnd(name);
                }
                if (error !== null) {
                    throw error;
                } else {
                    return result;
                }
            };
            wrapped.isis_debug_wrapped = true;
            wrapped.constructor = fn;
            wrapped.prototype = fn.prototype;
            return wrapped;
        };
        var wrapMethods = function (prototype, className, path) {
            /** defaults */
            path = (typeof path === "undefined")
                ? className : path + '.' + className;

            /** wrap the functions */
            console.info('wrapping', path);
            for (var key in prototype) {
                var fn = prototype[key];
                if (isis.isFunction(fn) && fn.isis_debug_wrapped !== true) {
                    prototype[key] = wrapFunction(fn, key, path);
                }
                if (fn && fn.prototype) {
                    wrapMethods(fn.prototype, key, path);
                }
            }
        };
        console.group('isis.debug');
        wrapMethods(prototype, className)
        console.groupEnd();
    };

}(window.isis));
