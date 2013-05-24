/**
 * test_naba_utils.js
 *
 * :author: tannern
 * :date: 3/5/12
 */

test("environtment", function () {
    ok(jQuery, "jQuery library");
    ok($, "$ jQuery shortcut");
    equal($().jquery, '1.7.1', "jQuery version 1.7.1");
});

module("naba_utils.js");

test("module structure", function () {
    ok($.isFunction(window.getCSS), "getCSS function");
    ok($.isFunction($.fn.textWidth), "jQuery textWidth extension");
    ok($.isFunction(window.S4), "S4 function");
    ok($.isFunction(window.guid), "guid function");
    ok($.isFunction(window.isSet), "isSet function");
    ok($.isFunction(window.trace), "trace function");
    /** prototype objects */
    ok($.isFunction(window.ProcessableXML),
        "ProcessableXML function");
    ok($.isPlainObject(window.ProcessableXML.prototype),
        "ProcessableXML prototype");
    ok($.isFunction(window.EventDispatcher),
        "EventDispatcher function");
    ok($.isPlainObject(window.EventDispatcher.prototype),
        "EventDispatcher prototype");
    /** Array extensions */
    ok($.isFunction(Array.prototype.diff), "Array diff");
    ok($.isFunction(Array.prototype.indexOf), "Array indexOf");
    ok($.isFunction(Array.prototype.removeElement), "Array removeElement");
    /** Object extensions */
    ok($.isFunction(Object.size), "Object size");
    ok($.isFunction(Object.equals), "Object equals");
    /** */
    ok($.isFunction(window.isIE8Browser), "isIE8Browser function");
    ok($.isFunction(window.detectIfBrowserSUpported),
        "detectIfBrowserSUpported function");
});

test("calculate scrollbar size", function () {
    equal(typeof window.SCROLLBAR_WIDTH, 'number', "exported SCROLLBAR_WIDTH");
});

module("Array.prototype");

test("diff", function () {
    var a, b;
    deepEqual([].diff([]), [], 'empty arrays');
    deepEqual([0, 1, 2].diff([0, 1, 2]), [], 'matching arrays');
    deepEqual([0, 1, 2].diff([]), [0, 1, 2],
        'missing from second are returned');
    deepEqual([].diff([0, 1, 2]), [], 'missing from first are ignored');
    deepEqual([
        [0],
        [1]
    ].diff([
        [0],
        [1]
    ]), [
        [0],
        [1]
    ],
        "arrays are ignored");
    deepEqual([
        {a:0},
        {b:1}
    ].diff([
        {a:0},
        {b:1}
    ]), [
        {a:0},
        {b:1}
    ],
        "objects are ignored");
    a = [0];
    deepEqual([a].diff([a]), [], "array pointers are included");
    b = {a:0};
    deepEqual([b].diff([b]), [], "object pointers are included");
});

test("indexOf", function () {
    var a, b;
    equal([0, 1, 0].indexOf(0), 0, "number multiple finds first");
    equal([true, false, true].indexOf(true), 0, "bool multiple finds first");
    equal([
        {a:0},
        {a:1},
        {a:0}
    ].indexOf({a:0}), -1, "objects not included");
    equal([
        [0],
        [1],
        [0]
    ].indexOf([0]), -1, "arrays not included");
    a = [0];
    equal([a].indexOf(a), 0, "pointers to same array are included");
    b = {a:0};
    equal([b].indexOf(b), 0, "pointers to same object are included");
});

test("removeElement", function () {
    var a, _array, _object;

    a = [0, 1, 2];
    a.removeElement(1);
    deepEqual(a, [0, 2], 'remove single number');
    a = [0, 1, 0];
    a.removeElement(0);
    deepEqual(a, [1], 'remove multiple numbers');
    a = ['a', 'b', 'a'];
    a.removeElement('b');
    deepEqual(a, ['a', 'a'], 'remove single string');
    a = ['a', 'b', 'a'];
    a.removeElement('a');
    deepEqual(a, ['b'], 'remove multiple strings');
    a = [
        [0],
        [1]
    ];
    a.removeElement([1]);
    deepEqual(a, [
        [0],
        [1]
    ], 'ignore matching arrays');
    a = [
        {a:0},
        {a:1}
    ];
    a.removeElement({a:1});
    deepEqual(a, [
        {a:0},
        {a:1}
    ], 'ignore matching objects');
    _array = [1];
    a = [0, _array, 2];
    a.removeElement(_array);
    deepEqual(a, [0, 2], 'remove array pointers');
    _object = {a:1};
    a = [0, _object, 2];
    a.removeElement(_object);
    deepEqual(a, [0, 2], 'remove object pointers');
});

module("Object.size");

test("basic functionality", function () {
    equal(Object.size(null), 0, "null");
    equal(Object.size(undefined), 0, "undefined");
    equal(Object.size(1), 0, "plain number");
    equal(Object.size(true), 0, "plain bool");
    equal(Object.size('hello'), 5, "plain string use string length");
    equal(Object.size({}), 0, "empty object");
    equal(Object.size({a:0}), 1, "non-empty object");
    equal(Object.size([]), 0, "empty array");
    equal(Object.size([0, 1, 2]), 3, "non-empty array use array length");
});

module("Object.equals");

test("basic functionality", function () {
    ok(Object.equals(null, null), "null === null");
    ok(Object.equals(undefined, undefined), "undefined === undefined");
    ok(Object.equals(true, true), "bool === bool");
    ok(Object.equals(0, 0), "zero === zero");
    ok(Object.equals(1, 1), "number === number");
    ok(Object.equals([], []), "empty array === empty array");
    ok(Object.equals([0, 1], [0, 1]), "array === array");
    ok(Object.equals([
        [0, 1]
    ], [
        [0, 1]
    ]), "nested array === nested array");
    ok(Object.equals({}, {}), "empty object === empty object");
    ok(Object.equals({a:1}, {a:1}), "object === object");
    ok(Object.equals({a:{a:1}}, {a:{a:1}}), "deep object === deep object");
});

test("ambiguous equalities", function () {
    /** test all ambiguous equalities */
    var ambiguous, i, j, a, b, expected;
    ambiguous = [
        null, undefined, false, 0, [], [0], {}
    ];

    for (i = 0; i < ambiguous.length; i += 1) {
        for (j = 0; j < ambiguous.length; j += 1) {
            a = ambiguous[i];
            b = ambiguous[j];
            expected = a === b;
            equal(Object.equals(a, b), expected,
                "( " + JSON.stringify(a) + " === " + JSON.stringify(b) +
                    " ) === " + expected);
        }
    }
});

test("instantiated prototypes", function () {
    var A, B, a1, a2, b;
    A = function () {
        this.typeName = 'A';
    };
    a1 = new A();
    a2 = new A();
    ok(Object.equals(a1, a2), "instantiated same class are equal");
    B = function () {
        this.typeName = 'B';
    };
    B.prototype = new A();
    b = new B();
    ok(!Object.equals(a1,b), "instantiated subclass are not equal");
});
