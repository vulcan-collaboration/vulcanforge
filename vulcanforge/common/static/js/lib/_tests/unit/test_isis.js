/**
 * isis
 *
 * :author: tannern
 * :date: 3/5/12
 */

test("structure", function () {
    ok(isis, "expose isis object");
    ok(isis.isDefined, "expose isis.isDefined");
    ok(isis.isFunction, "expose isis.isFunction");
    ok(isis.freeze, "expose isis.freeze");
    ok(isis.ProtoObject, "expose isis.ProtoObject");
});

module("isis");

test("isDefined", function () {
    equal(isis.isDefined(), false, "no argument");
    equal(isis.isDefined(undefined), false, "undefined argument");
    equal(isis.isDefined(true), true, "true bool argument");
    equal(isis.isDefined(false), true, "false bool argument");
    equal(isis.isDefined(0), true, "falseish number argument");
    equal(isis.isDefined(1), true, "trueish number argument");
    equal(isis.isDefined('false'), true, "falseish string argument");
    equal(isis.isDefined('true'), true, "trueish string argument");
    equal(isis.isDefined([]), true, "empty array argument");
    equal(isis.isDefined([0]), true, "falseish array argument");
    equal(isis.isDefined([0,1,2]), true, "array argument");
    equal(isis.isDefined({}), true, "empty object argument");
});

test("isFunction", function () {
    var functions, nonFunctions, i, obj;
    functions = [Array.prototype.filter, function () {}];
    nonFunctions = [undefined, null, 0, 1, [], [0], [0,1,2], {}];
    for (i = 0; i < functions.length; ++i) {
        obj = functions[i];
        ok(isis.isFunction(obj), "function "+JSON.stringify(obj));
    }
    for (i = 0; i < nonFunctions.length; ++i) {
        obj = nonFunctions[i];
        ok(!isis.isFunction(obj), "non function "+JSON.stringify(obj));
    }
});

test("freeze", function () {
    var obj;
    obj = {};
    obj = isis.freeze(obj);
    if (typeof Object.isFrozen !== 'undefined') {
        ok(Object.isFrozen(obj), "object is frozen");
    } else {
        ok(true, "freeze is not available on this system");
    }
});

test("ProtoObject", function () {
    var obj;

    obj = new isis.ProtoObject();
    ok(obj, "empty ProtoObject instance");

    obj = new isis.ProtoObject({a:0});
    ok(obj, "ProtoObject instance");
    equal(obj.a, 0, "ProtoObject instance attribute");

    obj = new isis.ProtoObject({a:{b:0}});
    ok(obj, "ProtoObject instance");
    equal(obj.a.b, 0, "ProtoObject instance deep attribute");
});
