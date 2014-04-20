//
// VulcanForge File browser widget
//
// @author tannern
//
// @requires jQuery (~1.7.1)
// @requires jQuery UI (~1.8.17)
//

/*jslint
 nomen: true
 */
/*globals
 console, parseInt
 */

(function ($vf, $) {
    "use strict";

    var fileBrowser, schema, exc, h, PathDataObject;
    fileBrowser = $vf.fileBrowser = {};

    //
    // # prepare jQuery
    //
    jQuery.event.props.push('dataTransfer');

    //
    // # exceptions
    //
    exc = fileBrowser.exc = {
        pathDataLookupError: function (path) {
            var e = new Error("The path data could not be loaded for " + path);
            e.name = "PathDataLookupError";
            return e;
        },
        notImplementedError: function (msg) {
            var e = new Error(msg || "This functionality is not yet " +
                "implemented or should be overridden.");
            e.name = "NotImplementedError";
            return e;
        },
        assertionError: function (msg) {
            var e = new Error(msg || "Assertion failed.");
            e.name = "AssertionError";
            return e;
        }
    };

    //
    // # helper methods
    //
    h = fileBrowser.helpers = {
        assert: function (statement, failMessage) {
            if (!statement) {
                throw exc.assertionError(failMessage);
            }
        },
        toAbsolute: function (url) {
            if (url[0] === '/') {
                url = window.location.origin + url;
            }
            return url;
        }
    };

    //
    // # JSON Schemas for fileBrowser API
    //
    schema = fileBrowser.schema = {};
    schema.pathData = {
        pathData: {
            // TODO: define the pathData JSONSchema
        }
    };

    //
    // # pathData object
    //
    PathDataObject = fileBrowser.PathDataObject = function (pathData) {
        $.extend(this, pathData);
        // TODO: Validate pathData with $vf.fileBrowser.schema.pathData
        return this;
    };
    $.extend(PathDataObject.prototype, {

        isCurrent: function () {
            return (this.childrenLoaded && this.expiresAt &&
                this.expiresAt > Number(new Date())) || false;
        },

        isType: function (typeName) {
            return this.type.toUpperCase() === typeName.toUpperCase();
        },

        isFileType: function (filetypes) {
            var i, type, start, end;
            for (i = 0; i < filetypes.length; i += 1) {
                type = filetypes[i].toLowerCase();
                start = this.name.length - type.length;
                end = this.name.length - 1;
                if (this.name.substr(start, end).toLowerCase() === type) {
                    return type;
                }
            }
            return false;
        },

        isImage: function () {
            return this.isFileType([
                'jpg', 'gif', 'png'
            ]);
        },

        getPathParts: function () {
            var i, loopChar,
                partIndex = 0,
                pathParts = [],
                loopPart;
            if (!this._CACHE_pathParts) {
                for (i = 0; i < this.path.length; i += 1) {
                    loopChar = this.path[i];
                    if (!pathParts[partIndex]) {
                        pathParts[partIndex] = loopPart = {
                            part: '',
                            full: undefined
                        };
                    }
                    loopPart.part += loopChar;
                    if (loopChar === '/') {
                        loopPart.full = this.path.substring(0, i + 1);
                        partIndex += 1;
                    }
                }
                this._CACHE_pathParts = pathParts;
            }
            return this._CACHE_pathParts;
        },

        getLastSlashIndex: function () {
            if (!this._CACHE_lastSlashIndex) {
                this._CACHE_lastSlashIndex = this.path.
                    lastIndexOf('/', this.path.length - 2) + 1;
            }
            return this._CACHE_lastSlashIndex;
        },

        getPathDepth: function () {
            return this.getPathParts().length - 1;
        },

        getParentPath: function () {
            if (!this._CACHE_parentPath) {
                if (this.path.length > 1) {
                    this._CACHE_parentPath = this.path.
                        substr(0, this.getLastSlashIndex());
                } else {
                    this._CACHE_parentPath = false;
                }
            }
            return this._CACHE_parentPath;
        },

        getDisplayName: function () {
            return this.isType('DIR') ? this.name + '/' : this.name;
        }

    });

    //
    // # vf.fileBrowser jQuery UI widget
    //
    // instantiate with:
    //
    //      $('...container selector...').fileBrowser({ ... });
    //
    $.widget("vf.fileBrowser", {

        // ## defaults
        "options": {

            // should assertions be run and errors thrown?
            assertions: false,

            // label of the fileBrowser widget
            // shown in the header
            label: "",

            // page title string
            // used when creating history states
            // replacements:
            //      {path}          the current path
            //      {filename}      the filename of the current path file
            pageTitleFormat: "{filename} - {path}",

            // extra fields to show as columns
            extraFields: [],

            // HTML class prefix will be prepended to all elements
            classPrefix: "vf-filebrowser-",

            // optionally set the height of the widget and the list view will
            // scroll to accommodate larger lists.
            // false-ish values will default to automatic resizing
            height: false,

            // the initial path to load
            // ¡Trailing slash is important!
            initialPath: '/',

            // optionally preload with data object
            data: null,

            // how long to cache pathData (in milliseconds)
            // a timeout of zero (0) means that it never times out.
            // actually any "falsy" value means this as well.
            dataCacheTimeout: 5 * 60 * 1000,

            //
            canUpload: false,

            // folderOperations
            //
            // A list of functions that return a jQuery DOM element with events
            // already bound.
            // Preferred to be 'button' elements.
            // example: [
            //      function (pathData) {
            //          return $('<button>A Button</button>').
            //              bind('click', funciton () {
            //                  console.log('hi from ' + pathData.path);
            //              })
            //      }
            // ]
            folderOperations: null,

            // this function should return the url a path should link to
            getURLForPath: function (path) {
                throw exc.notImplementedError("You must define the " +
                    "getURLForPath method");
            },

            prepareRawPathData: function(rawData) {
                return rawData;
            },

            // this function should take a path to and return an object
            // that will validate against $vf.fileBrowser.schema.pathData
            getDataForPath: function (path) {
                throw exc.notImplementedError("You must define the " +
                    "getDataForPath method");
            },

            //
            getUploadFormDataForFileAndPath: function (file, path) {
                throw exc.notImplementedError("You must define the " +
                    "getUploadFormDataForFileAndPath method");
                //// example
                //
                //var formData = new FormData();
                //formData.append("file", file);
                //formData.append("path", path);
                //return formData;
                //
            },

            getUploadURLForFileAndPath: function (file, path) {
                throw exc.notImplementedError("You must define the " +
                    "getUploadURLForFileAndPath method");
            }
        },

        //
        //
        // ## widget methods
        //
        //

        _create: function () {
            var that = this;

            // set up path instance variables
            this.data = this.options.data || {};
            if (this.data){
                this._convertPathData(that.data, that.options.initialPath);
            }
            this._activePath = null;
            this._selectedPath = null;

            // create widget elements
            this._createElements();

            // attach event listeners
            this._createEventListeners();

            // go to the initial path
            that.goToPath(that.options.initialPath);
        },

        _createElements: function () {
            var that = this;
            // store original element contents
            this.originalHTML = this.element.html();

            // initialize element
            this.element.empty();

            // create widget elements
            this.$container = $('<div/>').
                addClass(this._class('container')).
                addClass(this._class('root-container')).
                appendTo(this.element);
            if (this.options.height) {
                this.$container.css('height', this.options.height);
            }
            this.$statusContainer = $('<div/>').
                addClass(this._class('container')).
                addClass(this._class('status-container')).
                appendTo(this.$container);
            this.$headerContainer = $('<div/>').
                addClass(this._class('container')).
                addClass(this._class('header-container')).
                appendTo(this.$container);
            this.$headerLiner = $('<div/>').
                addClass(this._class('liner')).
                addClass(this._class('header-liner')).
                appendTo(this.$headerContainer);
            if (this.options.label) {
                $('<span/>', {'html': this.options.label}).
                    addClass(this._class('label')).
                    addClass(this._class('header-label')).
                    appendTo(this.$headerLiner);
            }
            this.$pathContainer = $('<div/>').
                addClass(this._class('container')).
                addClass(this._class('path-container')).
                appendTo(this.$headerLiner);
            this.$pathList = $('<ul/>').
                addClass(this._class('pathList')).
                addClass(this._class('pathList-root')).
                appendTo(this.$pathContainer);
            this.$listContainer = $('<div/>').
                addClass(this._class('container')).
                addClass(this._class('list-container')).
                height(200).
                appendTo(this.$container);
            this.$listLiner = $('<div/>').
                addClass(this._class('liner')).
                addClass(this._class('list-liner')).
                appendTo(this.$listContainer);

            this.$footerContainer = $('<div/>').
                addClass(this._class('container')).
                addClass(this._class('footer-container')).
                appendTo(this.$container);

            this.pleaseWait = new $vf.PleaseWait('Loading...',
                this.$listContainer);
        },

        _createEventListeners: function () {
            var that = this;

            this.$listContainer.
                bind({
                    'mouseleave': function (e) {
                        that.selectPath(null);
                    },
                    'dragenter dragover': function (e) {
                        e.preventDefault();
                        e.stopPropagation();
                    },
                    'drop': function (e) {
                        var path = that.getActivePath();
                        e.stopPropagation();
                        e.preventDefault();
                        that.unhighlightAllDropTargets();

                        $.each( e.dataTransfer.files, function(i, file){
                            that.uploadFileToPath(file, path, function () {
                                that.refreshActivePath();
                            }, function () {
                                alert('There was an error while uploading ' + file.name);
                            });
                        });
                    }
                }).
                delegate('a[draggable]', 'dragstart', function (e) {
                    var fileDetails;
                    if (typeof this.dataset === 'undefined') {
                        fileDetails = $(this).attr('data-downloadurl');
                    } else {
                        fileDetails = this.dataset.downloadurl;
                    }
                    if (typeof e.dataTransfer !== 'undefined' && fileDetails) {
                        e.dataTransfer.setData('DownloadURL', fileDetails);
                    }
                });

            if (this.options.canUpload) {
                $(window).
                    bind('drop', function (e) {
                        e.stopPropagation();
                        e.preventDefault();
                        that.unhighlightAllDropTargets();
                    }).
                    bind('dragenter', function (e) {
                        var dt = e.originalEvent.dataTransfer;
                        if(dt.types != null && (dt.types.indexOf ? dt.types.indexOf('Files') != -1 : dt.types.contains('application/x-moz-file'))) {
                            that.highlightAllDropTargets();
                        }
                    }).
                    bind('dragend mouseup', function (e) {
                        that.unhighlightAllDropTargets();
                    });
            }

            $(window).
                bind({
                    'popstate': function (e) {
                        var path = (e && e.originalEvent &&
                            e.originalEvent.state &&
                            e.originalEvent.state.path);
                        if (path) {
                            that.goToPath(path);
                        }
                    },
                    'keydown': function (e) {
                        switch (e.keyCode) {

                        case 37: // left
                            that.goToParentOfPath(that._activePath);
                            e.preventDefault();
                            break;

                        case 13: // enter
                            that.goToSelectedPath();
                            break;

                        case 39: // right
                            that.goToSelectedPath();
                            e.preventDefault();
                            break;

                        case 38: // up
                            that.selectPreviousPath();
                            e.preventDefault();
                            break;

                        case 40: // down
                            that.selectNextPath();
                            e.preventDefault();
                            break;

                        default: // any other
                            break;

                        }
                    }
                });
        },

        destroy: function () {
            // undo changes made to the DOM
            this.element.html(this.originalHTML);
        },

        //
        //
        // ## public-ish methods
        //
        //

        lockInterface: function (opt_message) {
            var message = typeof opt_message === 'undefined' ?
                "Please Wait..." :
                opt_message;
            this.pleaseWait.update(message);
            this.pleaseWait.show();
        },

        unlockInterface: function () {
            this.pleaseWait.hide();
        },

        getActivePath: function(){
            return this._activePath;
        },

        refreshActivePath: function () {
            this.goToPath(this._activePath, undefined, true);
        },

        goToPath: function (path, opt_selectPath, opt_reload) {
            var that = this,
                selectPath,
                reload;
            selectPath = typeof opt_selectPath === "undefined" ?
                null : opt_selectPath;
            reload = typeof opt_reload === 'undefined' ?
                false : opt_reload;

            if (!path) {
                return;
            }
            this._activePath = path;
            this._withPathDataForPath(path, function (pathData) {
                // go directly to files, refresh directories
                if (pathData && pathData.type.toLowerCase() === 'file') {
                    that.goToPathData(pathData);
                    that.selectPath(selectPath);
                } else {
                    that._withPathDataForPath(path, function (pathData) {
                        that.goToPathData(pathData);
                        that.selectPath(selectPath);
                    });
                }
            }, {
                reload: reload
            });

        },

        goToPathData: function (pathData, opt_event) {
            var that = this;
            this.element.trigger('gotopath', {
                'filebrowser': this,
                'pathData': pathData
            });
            if (typeof pathData === 'undefined') {
                this.lockInterface("Could not load data.");
                return;
            }
            // middle or right click
            if (!opt_event || (opt_event.which && opt_event.which !== 1)) {
                if (pathData.isType('DIR')) {
                    that.goToDirForPathData(pathData);
                } else if (pathData.isType('FILE')) {
                    that.goToFileForPathData(pathData);
                }
            } else {
                window.location.href = pathData.href;
            }
        },

        goToDirForPathData: function (pathData) {
            var newTitle;
            // animations
            this._animateListToPathData(pathData);
            this._animatePathToPathData(pathData);
            // history & location management
            if (window.location.pathname !== pathData.href) {
                newTitle = this.options.pageTitleFormat.
                    replace('{path}', pathData.path).
                    replace('{filename}', pathData.name);
                window.history.pushState({path: pathData.path},
                    newTitle, pathData.href);
            } else {
                window.history.replaceState({path: pathData.path},
                    $('head title').text(), window.location.href);
            }
        },

        goToFileForPathData: function (pathData) {
            window.location.href = pathData.href;
        },

        goToSelectedPath: function () {
            this.goToPath(this._selectedPath, null);
        },

        goToParentOfPath: function (path) {
            var that = this;
            if (path) {
                this._withPathDataForPath(path, function (pathData) {
                    var parentPath = pathData.getParentPath();
                    that.goToPath(parentPath, path);
                });
            }
        },

        selectPath: function (path) {
            var that = this,
                className,
                oldPath;
            oldPath = this._selectedPath;

            this.element.trigger('selectpath', {
                'filebrowser': this,
                'path': path,
                'oldPath': oldPath
            });

            this._selectedPath = path;
            if (oldPath !== this._selectedPath) {
                className = this._class('listItem-selected');
                this.$listContainer.
                    find('.' + className).
                    removeClass(className);
                this._findListItemByPath(path).
                    addClass(className);
            }
        },

        selectSiblingPath: function (direction) {
            var listItemSelector,
                $listItem,
                $targetListItem,
                siblingSelectMethod,
                $listPanel,
                badDirectionError,
                path;

            badDirectionError = exc.notImplementedError("selectSiblingPath()" +
                " requires a direction argument of either " +
                "`up` or `down`.");
            listItemSelector = '.' + this._class('listItem');

            if (this._selectedPath) {
                $listItem = this._findListItemByPath(this._selectedPath);
                switch (direction) {
                case 'up':
                    siblingSelectMethod = $listItem.prev;
                    break;
                case 'down':
                    siblingSelectMethod = $listItem.next;
                    break;
                default:
                    throw badDirectionError;
                }
                $targetListItem = siblingSelectMethod.call(
                    $listItem,
                    listItemSelector
                );
            } else {
                $listPanel = this._findListPanelByPath(this._activePath);
                $targetListItem = $listPanel.find(listItemSelector);
                switch (direction) {
                case 'up':
                    $targetListItem = $targetListItem.last();
                    break;
                case 'down':
                    $targetListItem = $targetListItem.first();
                    break;
                default:
                    throw badDirectionError;
                }
            }

            if ($targetListItem.length) {
                path = this._unescapePath($targetListItem.attr('data-vf-path'));
                this.selectPath(path);
            }
        },

        selectPreviousPath: function () {
            this.selectSiblingPath('up');
        },

        selectNextPath: function () {
            this.selectSiblingPath('down');
        },

        highlightAllDropTargets: function () {
            this.$listContainer.
                addClass('vf-ui-droptarget');
        },

        unhighlightAllDropTargets: function () {
            this.$listContainer.
                removeClass('vf-ui-droptarget').
                removeClass('vf-ui-dragover');
        },

        //
        //
        // ## private-ish methods
        //
        //

        _class: function (name) {
            return this.options.classPrefix + name;
        },

        //
        // ### data methods
        //

        _withPathDataForPath: function (path, callback, options) {
            var pathData,
                opt = $.extend({
                    // reload can be `true`, `false`, anything else is auto
                    reload: 'auto',
                    showPleaseWait: true
                }, options);
            // get cached data
            pathData = this.data[path];

            if (typeof pathData !== 'undefined' && opt.reload === false) {
                return callback(pathData);
            }
            // load new data if missing or expired
            if (path && (
                opt.reload === true || !pathData || (this.options.dataCacheTimeout && !pathData.isCurrent())
                )) {
                this._loadPathData(path, callback, opt.showPleaseWait);
            } else {
                callback(pathData);
            }
        },

        _withPathDataForPaths: function (paths, callback) {
            var that = this;
            $.each(paths, function (i, path) {
                that._withPathDataForPath(path, callback);
            });
        },

        _loadPathData: function (path, callback, showPleaseWait) {
            var that = this;

            this.element.trigger('loadpathdata', {
                'filebrowser': this,
                'path': path
            });

            if (showPleaseWait) {
                this.lockInterface('Fetching data for ' + path);
            }
            this.options.getDataForPath(path, function (data) {
                that._receivePathData(path, data, callback);
                if (showPleaseWait) {
                    that.unlockInterface();
                }
            });
        },

        _receivePathData: function (path, loadedData, callback) {
            var pathData;
            var that = this;

            this.element.trigger('receivepathdata', {
                'filebrowser': this,
                'path': path,
                'loadedData': loadedData
            });

            $.each(this._getChildrenDataForPath(path), function (k, v) {
                if (that.data && typeof that.data[v.path] !== 'undefined'){
                    delete that.data[v.path];
                }
            });
            pathData = that._convertPathData(loadedData, path);
            callback.call(this, pathData);
        },

        _convertPathData: function(loadedData, path){
            var pathData, that = this;
            $.each(loadedData, function (k, v) {
                v = that.options.prepareRawPathData.call(that, v);
                loadedData[k] = new PathDataObject(v);
            });
            $.extend(this.data, loadedData);
            pathData = this.data[path];
            if (pathData) {
                pathData.childrenLoaded = true;
                if (this.options.dataCacheTimeout && !pathData.expiresAt) {
                    pathData.expiresAt = Number(new Date()) +
                        this.options.dataCacheTimeout;
                }
            }
            return pathData;
        },

        _escapePath: function(path){
            if (typeof path === "string"){
                path = path.replace('"', '&quot;');
            }
            return path;
        },

        _unescapePath: function(path){
            if (typeof path === "string"){
                path = path.replace('&quot;', '"');
            }
            return path;
        },

        uploadFileToPath: function (file, path, success, failure) {
            var that = this,
                url = this.options.getUploadURLForFileAndPath(file, path),
                formData = this.options.getUploadFormDataForFileAndPath(file, path),
                $loadingProgress = $('<progress></progress>').
                    attr('max', 1).
                    attr('value', 0),
                $loadingLabel = $('<span/>').
                    text('Uploading ' + file.name + '... '),
                $loadingLabelPercent = $('<span/>').
                    appendTo($loadingLabel),
                $loadingInfo = $('<div>').
                    addClass(this._class('statusEntry')).
                    append($loadingProgress).
                    append(' ').
                    append($loadingLabel).
                    appendTo(this.$statusContainer),
                confirmLeavePage = function (e) {
                    return "Leaving this page will interrupt the current processes. Continue leaving?";
                };

            $(window).scrollTo(0);

            $.ajax({
                'url': url,
                'type': 'POST',
                'data': formData,
                'headers': {
                    'VF_SESSION_ID': $.cookie('_session_id')
                },
                'xhr': function () {
                    var xhr = new window.XMLHttpRequest();
                    $(window).bind('beforeunload', confirmLeavePage);
                    xhr.upload.addEventListener('progress', function (e) {
                        var perun, percent;
                        if (e.lengthComputable) {
                            $loadingProgress.
                                attr('max', e.total).
                                attr('value', e.loaded);
                            perun = e.loaded / e.total;
                            percent = Math.round(perun * 100);
                            $loadingLabelPercent.
                                text(percent + '%');
                        }
                        if (percent >= 100) {
                            $loadingProgress.
                                removeAttr('value');
                            $loadingLabel.
                                text('Saving ' + file.name + '...');
                        }
                    }, false);
                    return xhr;
                },
                'success': function (responseData) {
                    $loadingProgress.
                        attr('max', 1).
                        attr('value', 1);
                    $loadingLabel.
                        text('Uploaded ' + file.name);
                    if (typeof success !== 'undefined') {
                        success();
                    }
                    $vf.webflash();
                },
                'error' : function () {
                    $loadingProgress.
                        attr('max', 1).
                        attr('value', 0);
                    $loadingLabel.
                        text('Could not upload ' + file.name);
                    if (typeof failure !== 'undefined') {
                        failure();
                    }
                },
                'complete': function () {
                    $(window).
                        unbind('beforeunload', confirmLeavePage);
                    $loadingInfo.
                        delay(5000).
                        fadeOut('slow').
                        queue(function () {
                            $(this).
                                dequeue().
                                remove();
                        });
                },
                'processData': false,
                'contentType': false
            });
        },

        //
        // ### lookup methods
        //

        _findByPath: function ($container, selector, path) {
            selector += '[data-vf-path="' + this._escapePath(path) + '"]';
            return $container.find(selector);
        },

        _findListPanelByPath: function (path) {
            var selector;
            selector = '.' + this._class('listPanel');
            return this._findByPath(
                this.$listContainer,
                selector,
                path
            );
        },

        _findListItemByPath: function (path) {
            var selector;
            selector = '.' + this._class('listItem');
            return this._findByPath(
                this.$listContainer,
                selector,
                path
            );
        },

        _findPathNodeByPath: function (path) {
            var selector;
            selector = '.' + this._class('pathNode');
            return this._findByPath(
                this.$pathContainer,
                selector,
                path
            );
        },

        _findPathListByPath: function (path) {
            var selector;
            selector = '.' + this._class('pathList');
            return this._findByPath(
                this.$pathContainer,
                selector,
                path
            );
        },

        _getListPanels: function () {
            var selector;
            selector = '.' + this._class('listPanel');
            return this.$listContainer.find(selector);
        },

        _getListItems: function () {
            var selector;
            selector = '.' + this._class('listItem');
            return this.$listContainer.find(selector);
        },

        _getPathNodes: function () {
            var selector;
            selector = '.' + this._class('pathNode');
            return this.$pathContainer.find(selector);
        },

        _getChildrenDataForPath: function (path) {
            var childrenData = [];
            $.each(this.data, function (itemPath, itemData) {
                if (itemData.getParentPath() === path) {
                    childrenData.push(itemData);
                }
            });
            childrenData.sort(function (a, b) {
                var nameA, nameB;
                // sort by type first
                if (a.type < b.type) {
                    return -1;
                }
                if (a.type > b.type) {
                    return 1;
                }
                // sort by name second
                nameA = a.path.toLowerCase();
                nameB = b.path.toLowerCase();
                if (nameA < nameB) {
                    return -1;
                }
                if (nameA > nameB) {
                    return 1;
                }
                //
                return 0;
            });
            return childrenData;
        },

        _getListPanelForPathData: function (pathData) {
            var $listPanel;
            $listPanel = this._findListPanelByPath(pathData.path);
            $listPanel.remove();
            $listPanel = this._makeListPanelForPathData(pathData);
            return $listPanel;
        },

        _getListItemForPathData: function (pathData) {
            var $listItem,
                $listPanel;
            $listItem = this._findListItemByPath(pathData.path);
            $listPanel = this._findListPanelByPath(pathData.getParentPath());
            if (!$listItem.length) {
                $listItem = this._makeListItemForPathData(
                    pathData,
                    $listPanel
                );
            }
            return $listItem;
        },

        _getPathNodeForPath: function (path) {
            var $pathNode;
            $pathNode = this._findPathNodeByPath(path);
            if (!$pathNode.length) {
                $pathNode = this._makePathNodeForPath(path);
            }
            return $pathNode;
        },

        //
        // ### animation methods
        //

        _animateListToPathData: function (pathData) {
            var that = this,
                $listPanels,
                $listPanel,
                listPanelLeftOffset;

            $listPanel = this._getListPanelForPathData(pathData);
            $listPanels = this._getListPanels();

            $.each($listPanels, function (i, item) {
                var $itemListPanel, itemPath;
                $itemListPanel = $(item);
                itemPath = that._unescapePath($itemListPanel.attr('data-vf-path'));
                if (pathData.path.indexOf(itemPath) === 0) {
                    $itemListPanel.
                        clearQueue().
                        fadeIn('fast');
                } else {
                    $itemListPanel.
                        clearQueue().
                        fadeOut('fast');
                }
            });

            this.$listContainer.
                clearQueue().
                animate({
                    'height': $listPanel.height() + 'px'
                }, 'slow');

            listPanelLeftOffset = $listPanel[0].style.left;
            this.$listLiner.
                clearQueue().
                animate({
                    left: '-' + listPanelLeftOffset
                });
        },

        _animatePathToPathData: function (pathData) {
            var that = this,
                iterPath,
                $iterNode;

            this._getPathNodes().
                each(function (i, item) {
                    $iterNode = $(item);
                    iterPath = that._unescapePath($iterNode.attr('data-vf-path'));
                    if (pathData.path.indexOf(iterPath) === -1) {
                        $iterNode.
                            clearQueue().
                            fadeOut('fast').
                            find('a').
                            qtip('hide');
                    }
                });

            $.each(pathData.getPathParts(), function (i, pathPart) {
                that._getPathNodeForPath(pathPart.full).
                    clearQueue().
                    fadeIn();
            });
        },

        //
        // ### rendering methods
        //

        _makeListPanelForPathData: function (pathData) {
            var that = this,
                pathDepth,
                $listPanel,
                listHeight,
                $listControlPanel,
                $list,
                headers,
                $listHeader;

            pathDepth = pathData.getPathDepth();

            $listPanel = $('<div/>').
                addClass(this._class('listPanel')).
                attr('data-vf-path', that._escapePath(pathData.path)).
                css({
                    'top': 0,
                    'left': (100 * pathDepth) + '%'
                }).
                appendTo(this.$listLiner);

            if (this.options.height) {
                listHeight = this.options.height -
                    this.$headerContainer.height();
                if (listHeight) {
                    $listPanel.css({
                        'height': listHeight,
                        'overflow-x': 'hidden',
                        'overflow-y': 'scroll'
                    });
                }
            }

            if (this.options.folderOperations) {
                $listControlPanel = $('<div/>').
                    addClass(this._class('listControlPanel')).
                    appendTo($listPanel);
                $.each(this.options.folderOperations, function (index, fn) {
                    var result = fn(pathData);
                    if (result) {
                        result.appendTo($listControlPanel);
                    }
                });
            }

            $list = $('<ul/>').
                addClass(this._class('list')).
                appendTo($listPanel);

            // make headers
            headers = ['file'].concat(this.options.extraFields);
            $listHeader = $('<li/>').
                addClass(this._class('listItem-row')).
                addClass(this._class('listItem-header-row')).
                appendTo($list);
            $.each(headers, function (k, v) {
                $('<span/>').
                    addClass(that._class('listItem-cell')).
                    addClass(that._class('listItem-header-cell')).
                    text(v).
                    appendTo($listHeader);
            });

            $.each(this._getChildrenDataForPath(pathData.path),
                function (i, itemData) {
                    that._makeListItemForPathData(itemData, $list);
                });

            this.element.trigger('listpanel-created', {
                'filebrowser': this,
                '$listPanel': $listPanel,
                '$list': $list,
                'pathData': pathData
            });

            return $listPanel;
        },

        _makeListItemForPathData: function (pathData, $list) {
            var that = this,
                $listItem,
                $listItemFile,
                $listItemLink,
                $listItemIcon,
                $listItemLinkName,
                artifactLinkParams,
                artifactLink,
                $listItemNotesContainer,
                modifiedDate,
                typeName = pathData.type.toLowerCase(),
                fileDetails;

            $listItem = $('<li/>').
                addClass(this._class('listItem')).
                addClass(this._class('listItem-row')).
                addClass(this._class('listItem-row-' + typeName)).
                attr('data-vf-path', that._escapePath(pathData.path)).
                appendTo($list).
                bind('mouseenter', function (e) {
                    that.selectPath(pathData.path);
                });

            $listItemFile = $('<div/>').
                addClass(this._class('listItem-cell')).
                addClass(this._class('listItem-cell-file')).
                addClass(this._class('listItem-cell-file-' + typeName)).
                appendTo($listItem);

            $listItemLink = $('<a/>').
                addClass(this._class('listItem-link-file')).
                addClass(this._class('listItem-link-file-' + typeName)).
                attr('href', pathData.href).
                appendTo($listItemFile).
                bind('click', function (e) {
                    if (pathData.type === 'DIR' && e.which === 1) {
                        e.preventDefault();
                        that.goToPath(pathData.path);
                    }
                });

            if (pathData.downloadURL) {
                fileDetails = "application/octet-stream" +
                    ":" + pathData.name +
                    ":" + h.toAbsolute(pathData.downloadURL);
                $listItemLink.
                    attr('draggable', true).
                    attr('data-downloadurl', fileDetails);
            }

            if (pathData.extra && pathData.extra.iconURL && pathData.extra.iconURL.indexOf('.') !== -1) {
                $listItemIcon = $('<img/>').
                    attr('src', pathData.extra.iconURL);
            } else {
                $listItemIcon = $('<span/>').
                    addClass(this._class('listItem-link-file-icon-' + typeName));
                if (pathData.extra && pathData.extra.iconURL) {
                    $listItemIcon.
                        addClass(this._class('listItem-link-file-icon-' +
                            $vf.slugify(pathData.extra.iconURL)));
                }
            }
            $listItemIcon.
                addClass(this._class('listItem-link-file-icon')).
                appendTo($listItemLink);

            $listItemLinkName = $('<span/>').
                addClass(this._class('listItem-link-file-name')).
                addClass(this._class('listItem-link-file-name-' + typeName)).
                text(pathData.name).
                appendTo($listItemLink);

            // if artifact attributes are present render as an artifact link
            if (pathData.artifact) {
                if ((!pathData.artifact.type ||
                    !pathData.artifact.reference_id)) {
                    throw {
                        name: "MissingRequiredAttribute",
                        message: "The path data's `artifact` attribute " +
                            "must be an object with `type` and " +
                            "`reference_id` attributes."
                    };
                }
                artifactLinkParams = {
                    label: pathData.name,
                    artifactType: pathData.artifact.type,
                    containerE: $listItemLink,
                    refId: pathData.artifact.reference_id
                };
                if (pathData.extra.iconURL) {
                    artifactLinkParams.iconURL = pathData.extra.iconURL;
                }
                artifactLink = new $vf.ArtifactLink(artifactLinkParams);
                $listItemLink.data('artifactLink', artifactLink);
                $listItemLink.empty();
                artifactLink.render();
            }

            $listItemNotesContainer = $('<div/>').
                addClass(this._class('listItem-notes')).
                addClass(this._class('listItem-notes-file')).
                appendTo($listItemFile);

            if (pathData.modified) {
                modifiedDate = $vf.parseISO8601(pathData.modified);
                $('<time/>').
                    addClass(this._class('listItem-note')).
                    addClass(this._class('listItem-note-modified')).
                    attr('datetime', pathData.modified).
                    attr('title', modifiedDate).
                    text($vf.relativeDate(modifiedDate)).
                    appendTo($listItemNotesContainer);
            }

            $.each(this.options.extraFields, function (k, v) {
                $('<span/>').
                    addClass(that._class('listItem-cell')).
                    addClass(that._class('listItem-cell-' + v)).
                    html((pathData.extra && pathData.extra[v]) || "").
                    appendTo($listItem);
            });

            // confirm it exists
            if (this.options.assertions) {
                h.assert($listItem, "$listNode failed to render");
            }

            this.element.trigger('listitem-created', {
                'filebrowser': this,
                '$listItem': $listItem,
                'pathData': pathData
            });
            return $listItem;
        },

        _makePathNodeForPath: function (path) {
            var that = this,
                $parentPathNode,
                lastSlashIndex,
                parentPath,
                pathName,
                pathURL,
                pathType,
                $pathNode,
                $pathLink,
                $tipContainer,
                $tipLoader;

            lastSlashIndex = path.lastIndexOf('/', path.length - 2) + 1;
            parentPath = path.substr(0, lastSlashIndex);
            pathName = path.substr(lastSlashIndex) || '/';
            pathURL = this.options.getURLForPath(path);
            pathType = path[path.length - 1] === '/' ? 'dir' : 'file';

            $pathNode = $('<li/>').
                addClass(this._class('pathNode')).
                attr('data-vf-path', that._escapePath(path)).
                fadeOut(0);

            $parentPathNode = this._findPathNodeByPath(parentPath);
            if ($parentPathNode.length) {
                $pathNode.insertAfter($parentPathNode);
            } else {
                $pathNode.appendTo(this.$pathList);
            }

            $pathLink = $('<a/>').
                addClass(this._class('pathNode-link')).
                attr('href', pathURL).
                appendTo($pathNode).
                bind('click', function (e) {
                    if (e.which === 1) {
                        e.preventDefault();
                        that.goToPath(path);
                    }
                });

            $('<span/>').
                addClass(that._class('iconInline')).
                addClass(that._class('iconInline-' + pathType)).
                text(pathName).
                appendTo($pathLink);

            $tipContainer = $('<div/>').
                css('min-width', $pathLink.outerWidth() + 'px');
            $tipLoader = $('<div/>').
                addClass(that._class('loader')).
                appendTo($tipContainer);

            $pathLink.qtip({
                content: {
                    text: $tipContainer
                },
                show: {
                    solo: true,
                    effect: function (offset) {
                        $(this).animate({
                            'height': 'show',
                            'opacity': 'show'
                        }, 'fast');
                    }
                },
                hide: {
                    delay: 100,
                    event: 'unfocus mouseleave',
                    fixed: true,
                    effect: function (offset) {
                        $(this).animate({
                            'height': 'hide',
                            'opacity': 'hide'
                        }, 'fast');
                    }
                },
                style: {
                    classes: this._class('pathTip'),
                    tip: false
                },
                position: {
                    at: 'bottom left'
                },
                events: {
                    render: function (event, api) {
                        that._withPathDataForPath(path, function (pathData) {
                            var $tipContent;
                            $tipContent = that.
                                _makeQTipForPathDataAndQTipAPI(pathData, api);
                            $tipContainer.
                                animate({
                                'opacity': 0,
                                'height': 'hide'
                            }, 'fast').
                                queue(
                                function () {
                                    $tipContainer.
                                        html($tipContent).
                                        dequeue();
                                }).
                                animate({
                                    'opacity': 1,
                                    'height': 'show'
                                }, 'fast');
                        }, {
                            reload: false,
                            showPleaseWait: false
                        });
                    },
                    toggle: function (event, api) {
                        api.elements.target.toggleClass(
                            that._class('pathNode-link-active'),
                            event.type === 'tooltipshow'
                        );
                    }
                }
            });

            this.element.trigger('pathnode-created', {
                'filebrowser': this,
                '$pathNode': $pathNode,
                'path': path
            });

            return $pathNode;
        },

        _makeQTipForPathDataAndQTipAPI: function (pathData, qTipAPI) {
            var that = this,
                $pathTip,
                childrenData;

            $pathTip = $('<ul/>').
                addClass(this._class('pathTip-list'));

            childrenData = this._getChildrenDataForPath(pathData.path);
            $.each(childrenData, function (i, childData) {
                var $child, $link, clickFn, childType;

                childType = childData.type.toLowerCase();

                clickFn = function (e) {
                    if (e.which === 1 && childData.isType('DIR')) {
                        e.preventDefault();
                        that.goToPath(childData.path);
                        qTipAPI.hide();
                    }
                };

                $child = $('<li/>').
                    addClass(that._class('pathTip-child')).
                    appendTo($pathTip);

                $link = $('<a/>').
                    addClass(that._class('pathTip-childLink')).
                    attr('href', childData.href).
                    bind('click', clickFn).
                    appendTo($child);

                $('<span/>').
                    addClass(that._class('iconInline')).
                    addClass(that._class('iconInline-' + childType)).
                    text(childData.name).
                    appendTo($link);

            });

            this.element.trigger('pathtip-created', {
                'filebrowser': this,
                '$pathTip': $pathTip,
                'pathData': pathData
            });

            return $pathTip;
        }
    });

}(window.$vf, window.jQuery));
