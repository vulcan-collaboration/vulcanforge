/**
 * test_vf
 *
 * :author: tannern
 * :date: 3/5/12
 */

test("environment", function () {
    ok(jQuery, "jQuery library");
    ok($, "$ jQuery shortcut");
    equal($().jquery, '1.7.1', "jQuery version 1.7.1");
    ok(guid, "naba_utils.js loaded");
});

module("$vf");

test("module structure", function () {
    var exposed, i;
    exposed = [
        '$vf',
        '$vf.Pager', '$vf.Pager.prototype',
        '$vf.ServiceLocation', '$vf.ServiceLocation.prototype',
        '$vf.PleaseWait', '$vf.PleaseWait.prototype',
        '$vf.ClickCondom', '$vf.ClickCondom.prototype',
        '$vf.clickConfirm',
        '$vf.parseISO8601',
        '$vf.relativeDate'
    ];
    for (i = 0; i < exposed.length; i += 1) {
        ok(exposed[i], "exposes " + exposed[i]);
    }
});

module("$vf.Pager");

test("basic usage", function () {
    var pager, $el;
    $el = $('<div/>');
    pager = new $vf.Pager({
        containerE:$el,
        totalPages:6,
        currentPage:3,
        itemCount:6,
        itemPerPage:1
    });
    ok(pager, "instantiated");
    pager.render();
    notEqual($el.find('.firstPage').length, 0, "found First Page button");
    notEqual($el.find('.prevPage').length, 0, "found Previous Page button");
    notEqual($el.find('.nextPage').length, 0, "found Next Page button");
    notEqual($el.find('.lastPage').length, 0, "found Last Page button");
});
