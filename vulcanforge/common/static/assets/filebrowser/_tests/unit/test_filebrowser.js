/**
 * test_XCNG.Widgets.js
 *
 * QUnit tests [http://docs.jquery.com/QUnit]
 *
 * :author: tannern
 * :date: 3/2/12
 */

/*globals
 module, test, ok, equal,
 jQuery, $,
 $vf
 */
(function () {
    "use strict";

    var fixtures = {

        '/': {
            "name": "",
            "modified": "2000-01-01T01:01:01",
            "href": "/",
            "path": "/",
            "type": "DIR"
        },

        '/simpleFile': {
            "name": "simpleFile",
            "modified": "2000-01-01T01:01:01",
            "href": "/simpleFile",
            "path": "/simpleFile",
            "type": "FILE"
        },

        '/simpleFile.txt': {
            "name": "simpleFile.txt",
            "modified": "2000-01-01T01:01:01",
            "href": "/simpleFile.txt",
            "path": "/simpleFile.txt",
            "type": "FILE"
        },

        '/simpleDir/': {
            "name": "simpleDir",
            "modified": "2000-01-01T01:01:01",
            "href": "/simpleDir/",
            "path": "/simpleDir/",
            "type": "DIR"
        },

        '/simpleDir/deepDir/deeperDir/': {
            "name": "deeperDir",
            "modified": "2000-01-01T01:01:01",
            "href": "/simpleDir/deepDir/deeperDir/",
            "path": "/simpleDir/deepDir/deeperDir/",
            "type": "DIR"
        }

    };

    module("$vf.fileBrowser");

    test("test environment", function () {
        ok(jQuery, "jQuery library");
        ok($, "$ jQuery shortcut");
        equal($().jquery, '1.7.1', "jQuery version 1.7.1");
        ok(jQuery.ui, "jQuery.ui library");
    });

    module("$vf.fileBrowser.PathDataObject");

    test("constructor", function () {
        ok(new $vf.fileBrowser.PathDataObject(), "no args");
        ok(new $vf.fileBrowser.PathDataObject({}), "empty object");
        ok(new $vf.fileBrowser.PathDataObject({path: '/'}), "data object");
    });

    test("dir at path depth 1", function () {
        var d, parts;
        d = new $vf.fileBrowser.PathDataObject(fixtures['/simpleDir/']);

        d.childrenLoaded = true;
        d.expiresAt = Number(new Date()) + 60 * 1000;
        equal(d.isCurrent(), true, 'isCurrent true');
        d.expiresAt = Number(new Date()) - 1000;
        equal(d.isCurrent(), false, 'isCurrent false');


        equal(d.isType('DIR'), true, 'isType exact');
        equal(d.isType('dir'), true, 'isType different case');
        equal(d.isType('FILE'), false, 'isType wrong type');

        parts = d.getPathParts();
        ok(parts, 'getPathParts');
        equal(parts.length, 2, "getPathParts length");
        equal(parts[0].part, '/', "getPathParts 0.part");
        equal(parts[0].full, '/', "getPathParts 0.full");
        equal(parts[1].part, 'simpleDir/', "getPathParts 1.part");
        equal(parts[1].full, '/simpleDir/', "getPathParts 1.full");

        equal(d.getPathDepth(), 1, 'getPathDepth');

        equal(d.getParentPath(), '/', 'getParentPath');
    });

    test("dir at path depth 3", function () {
        var d, parts;
        d = new $vf.fileBrowser.PathDataObject(
            fixtures['/simpleDir/deepDir/deeperDir/']
        );

        d.childrenLoaded = true;
        d.expiresAt = Number(new Date()) + 60 * 1000;
        equal(d.isCurrent(), true, 'isCurrent true');
        d.expiresAt = Number(new Date()) - 1000;
        equal(d.isCurrent(), false, 'isCurrent false');


        equal(d.isType('DIR'), true, 'isType exact');
        equal(d.isType('dir'), true, 'isType different case');
        equal(d.isType('FILE'), false, 'isType wrong type');

        parts = d.getPathParts();
        ok(parts, 'getPathParts');
        equal(parts.length, 4, "getPathParts length");
        equal(parts[0].part, '/', "getPathParts 0.part");
        equal(parts[0].full, '/', "getPathParts 0.full");
        equal(parts[1].part, 'simpleDir/', "getPathParts 1.part");
        equal(parts[1].full, '/simpleDir/', "getPathParts 1.full");
        equal(parts[2].part, 'deepDir/', "getPathParts 2.part");
        equal(parts[2].full, '/simpleDir/deepDir/', "getPathParts 2.full");
        equal(parts[3].part, 'deeperDir/', "getPathParts 3.part");
        equal(parts[3].full, '/simpleDir/deepDir/deeperDir/', "getPathParts 3.full");

        equal(d.getPathDepth(), 3, 'getPathDepth');

        equal(d.getParentPath(), '/simpleDir/deepDir/', 'getParentPath');
    });

    test("dir at path depth 3", function () {
        var d, parts;
        d = new $vf.fileBrowser.PathDataObject(
            fixtures['/simpleFile.txt']
        );

        d.childrenLoaded = true;
        d.expiresAt = Number(new Date()) + 60 * 1000;
        equal(d.isCurrent(), true, 'isCurrent true');
        d.expiresAt = Number(new Date()) - 1000;
        equal(d.isCurrent(), false, 'isCurrent false');


        equal(d.isType('FILE'), true, 'isType exact');
        equal(d.isType('file'), true, 'isType different case');
        equal(d.isType('DIR'), false, 'isType wrong type');

        equal(d.isFileType(['txt']), 'txt', 'isFileType exact');

        parts = d.getPathParts();
        ok(parts, 'getPathParts');
        equal(parts.length, 2, "getPathParts length");
        equal(parts[0].part, '/', "getPathParts 0.part");
        equal(parts[0].full, '/', "getPathParts 0.full");
        equal(parts[1].part, 'simpleFile.txt', "getPathParts 1.part");
        equal(parts[1].full, '/simpleFile.txt', "getPathParts 1.full");

        equal(d.getPathDepth(), 1, 'getPathDepth');

        equal(d.getParentPath(), '/', 'getParentPath');
    });

}());
