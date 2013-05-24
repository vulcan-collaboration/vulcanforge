/**
 * isis.js
 *
 * :author: ISIS - Institute for Software Integrated Systems
 *                 Vanderbilt University School of Engineering
 * :date: 2012-01-16
 */

(function () {

    var isis = window.isis = {};

    /**
     * Return a boolean representing if the argument has been defined
     *
     * @param obj       the object to test
     * @rtype bool
     */
    isis.isDefined = function (obj) {
        return typeof obj !== 'undefined';
    };

    /**
     * Return a boolean representing if the argument is a function
     *
     * @param obj       the object to test
     */
    isis.isFunction = function (obj) {
        return Object.prototype.toString.call(obj) === "[object Function]";
    };

    /**
     * Freeze a static object if Object.freeze exists in this environment
     *
     * @param obj       the object to freeze
     */
    isis.freeze = function (obj) {
        return (Object && Object.freeze) ? Object.freeze(obj) : obj;
    };


    /**
     * class: ProtoObject
     *
     * An abstract root class
     *
     * @param opt_properties    Extend the new ProtoObject instance with
     *   these properties
     */
    isis.ProtoObject =  function (opt_properties) {
        var key;
        for (key in opt_properties) {
            this[key] = opt_properties[key];
        }
    };

}());
