//
// VulcanForge File browser widget
//
// @author tannern
// @author papszi
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

    var fileBrowser, schema, exc, h, PathDataObject, UploadDataObject;
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
            var isDir = this.isType('DIR') || this.isType('ZIP_DIR');
            return isDir ? this.name + '/' : this.name;
        }

    });

    //
    // # uploadData object
    //
    UploadDataObject = fileBrowser.UploadDataObject = function (uploadData) {
        $.extend(this, uploadData);
        // TODO: Validate pathData with $vf.fileBrowser.schema.pathData
        return this;
    };
    $.extend(UploadDataObject.prototype, {

        initializing: null,
        widgetRemoved: false,
        markedDeleted: false,

        isActive: function () {
            if (!this.resumableFile){
                this.resumableFile = $vf.fileBrowser.findResumableFileById(this.md5Signature);
            }
            return (this.resumableFile !== null && typeof this.resumableFile !== 'undefined');
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

        getUploadProgress: function() {
            if (this.isActive()){
                return this.resumableFile.progress();
            } else {
                return typeof this.uploadProgress !== 'undefined' ? this.uploadProgress : 0;
            }
        },

        getUploadWidget: function(){
            var that = this;
            if (!that.loadingInfoWidget){
                var percent = Math.round(this.getUploadProgress() * 100);
                this.loadingProgress = $('<progress/>').
                    attr('max', 1).
                    attr('value', this.getUploadProgress());
                this.loadingLabelContainer = $('<span/>').
                    addClass($vf.fileBrowser._class('labelContainer'));
                this.loadingLabel = $('<span/>').
                    text(this.getDisplayInfo()).
                    appendTo(this.loadingLabelContainer);
                this.loadingLabelPercent = $('<span/>').
                    text(percent + '%').
                    appendTo(this.loadingLabelContainer);
                this.loadingInfoWidget = $('<div>').
                    addClass($vf.fileBrowser._class('statusEntry')).
                    append(this.loadingProgress).
                    append(this.loadingLabelContainer);
                    //css('display', 'none');

                this.pauseButton = $('<a/>', {
                    'class': "ico-pause icon",
                    'title': "Pause",
                    'href': ""
                });
                this.resumeButton = $('<a/>', {
                    'class': "ico-play icon",
                    'title': "Resume",
                    'href': ""
                });
                this.cancelButton = $('<a/>', {
                    'class': "ico-delete icon",
                    'title': "Cancel",
                    'href': ""
                }).on('click', function (e) {
                        $vf.fileBrowser.deleteContent(that.path, that.removeWidget, that);
                        e.preventDefault();
                    });
                this.actionContainer = $('<span/>').
                    addClass($vf.fileBrowser._class('statusActions')).
                    append(this.pauseButton).
                    append(this.resumeButton).
                    append(this.cancelButton).
                    appendTo(this.loadingInfoWidget);
            }

            this.updateClassMarker();
            this.updateProgress(this.getUploadProgress());
            return this.loadingInfoWidget;
        },

        updateProgress: function(progress){
            // Use the current progress if bigger
            if (progress != 0) {
                this.initializing = false;
            }
            if (progress < this.uploadProgress) {
                progress = this.uploadProgress;
            }

            if (this.uploadProgress != progress){
                if (this.isActive()){
                    if (this.resumableFile.isPaused()){
                        this.firstUpdateTime = null;
                        //this.uploadSpeed = null;
                        this.timeRemaining = null;
                    } else {
                        if (this.firstUpdateTime){
                            var transferedBytes = (progress - this.firstProgressPoint) * this.resumableFile.size;
                            var bytesRemaining = (1 - (progress - this.firstProgressPoint)) * this.resumableFile.size;
                            var timeDeltaInSeconds = (Date.now() - this.firstUpdateTime) / 1000;
                            //this.uploadSpeed = $vf.prettyPrintByteSpeed(transferedBytes, timeDeltaInSeconds);
                            this.timeRemaining = $vf.prettyPrintTimeRemaining(bytesRemaining, transferedBytes / timeDeltaInSeconds);
                        } else {
                            this.firstUpdateTime = Date.now();
                            this.firstProgressPoint = progress;
                        }
                    }
                }
                this.uploadProgress = progress;
            }
            if (typeof this.loadingInfoWidget !== 'undefined'){
                var percent = Math.round(this.getUploadProgress() * 100);
                var prettySize = this.extra.size;
                var speedInfo = "";
                if (this.timeRemaining != null && typeof this.timeRemaining != 'undefined'){
                    //speedInfo = " " + this.uploadSpeed;
                    speedInfo = " - About " + this.timeRemaining;
                }
                this.loadingProgress.attr('value', progress);
                this.loadingLabel.text(this.getDisplayInfo());
                this.loadingLabelPercent.text(percent + '% of ' + prettySize + speedInfo);
            }
            this.updateActions();
        },

        updateClassMarker: function(){
            if (typeof this.loadingInfoWidget === 'undefined'){
                return;
            }
            if (!this.isActive()){
                this.loadingProgress.attr('class', 'inactive');
            } else {
                this.loadingProgress.attr('class', 'active');
            }
        },

        updateActions: function(){
            var that = this;
            if (typeof this.loadingInfoWidget === 'undefined'){
                return;
            }
            if (this.isActive()){
                if (!that.resumableFile.isPaused()){
                    this.pauseButton.css('display', '');
                    this.pauseButton.off('click');
                    this.pauseButton.on('click',function (e) {
                        if (that.isActive()){
                            that.resumableFile.pause(true);
                            that.resumableFile.resumableObj.upload();
                        }
                        if (that.resumableFile.isPaused()){
                            that.firstUpdateTime = null;
                            //that.uploadSpeed = null;
                            that.timeRemaining = null;
                            that.updateProgress(that.resumableFile.progress());
                        }
                        e.preventDefault();
                    });
                    this.resumeButton.css('display', 'none');
                }
                if (this.resumableFile.isPaused()) {
                    this.pauseButton.css('display', 'none');
                    this.resumeButton.css('display', '');
                    this.resumeButton.off('click');
                    this.resumeButton.on('click',function (e) {
                        if (that.isActive()){
                            that.resumableFile.pause(false);
                            that.resumableFile.resumableObj.upload();
                        }
                        if (!that.resumableFile.isPaused()){
                            that.updateProgress(that.resumableFile.progress());
                        }
                        e.preventDefault();
                    });
                }
            }
            if (!this.isActive() || this.initializing){
                this.pauseButton.css('display', 'none');
                this.resumeButton.css('display', 'none');
            }
        },

        getDisplayInfo: function() {
            var displayInfo;
            if (this.isActive()){
                if (this.resumableFile.isUploading()){
                    if (this.resumableFile.isPaused()){
                        displayInfo = 'Pausing ' + this.name + '... ';
                    } else {
                        displayInfo = 'Saving ' + this.name + '... ';
                    }
                } else {
                    if (this.resumableFile.isComplete()){
                        displayInfo = 'Uploaded ' + this.name + '... ';
                    } else {
                        if (this.initializing){
                            displayInfo = 'Waiting to upload ' + this.name + '... ';
                        } else {
                            displayInfo = 'Paused upload ' + this.name + '... ';
                        }
                    }
                }

            } else {
                displayInfo = 'Paused upload ' + this.name + '... ';
            }
            return displayInfo;
        },

        removeWidget: function(){
            var that = this;
            if (this.isActive()){
                this.resumableFile.cancel();
            }
            if (typeof this.loadingInfoWidget !== 'undefined'){
                this.loadingInfoWidget.
                    show().
                    delay(1500).
                    fadeOut(1500).
                    queue(function () {
                        $(this).
                            dequeue().
                            remove();
                        that.widgetRemoved = true;
                });
            }
        },

        highlight: function(){
            if (typeof this.loadingInfoWidget !== 'undefined'){
                this.loadingInfoWidget.
                    hide().
                    effect("highlight", {color:"#888888"}, 1500);
            }
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

            // RESUMABLE MULTIPART UPLOAD
            // The path to post multipart files to
            getResumableUploadUrl: function (params) {
                throw exc.notImplementedError("You must define the " +
                    "getUploadURLForFileAndPath method");
            },

            //
            canUpload: false,

            //
            canDelete: false,

            //
            uploadButton: undefined,

            // The size of a chunk in bytes
            chunkSize: 4*5242880,

            //
            replaceFiles: null,

            //
            maxFiles: 50,

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

            // this function should return the url a path should link to
            getDeleteURLForPath: function (path) {
                if (this.canDelete){
                    throw exc.notImplementedError("You must define the " +
                        "getDeleteURLForPath method");
                }
            },

            getMoveUrlForPath: function(path) {
                if (this.canUpload){
                    throw exc.notImplementedError("You must define the " +
                        "getMoveUrlForPath method");
                }
            },

            prepareRawPathData: function(rawData) {
                if (rawData.name){
                    rawData.name = $vf.htmlDecode(rawData.name);
                }
                if (rawData.path){
                    rawData.path = $vf.htmlDecode(rawData.path);
                }
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
            $vf.fileBrowser = this;

            // set up path instance variables
            this.uploadData = {};
            this.data = this.options.data || {};
            if (this.data){
                this._convertPathData(that.data, that.options.initialPath);
            }
            this._activePath = null;
            this._selectedPath = null;

            if (typeof Resumable !== 'undefined'){
            this._resumable = new Resumable({
                target: that.options.getResumableUploadUrl,
                chunkSize: that.options.chunkSize,
                forceChunkSize: true,
                simultaneousUploads: 5,
                generateUniqueIdentifier: that._computeMD5Signature,
                throttleProgressCallbacks: 1, // How often should progress updates be called
                headers: {
                    'VFSessionID': $.cookie('_session_id')
                }
            });
            }

            this.folderCache = {};
            this.filesToReplace = [];

            this._lastSingleSelect = null;
            this._lastRangeSelect = null;
            this.selectedForMove = {};


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

        _dragEnterHandler: function(e){
            var that = $vf.fileBrowser;

            e.preventDefault();
            e.stopPropagation();
            that.highlightAllDropTargets();
        },

        _dragLeaveHandler: function(e){
            var that = $vf.fileBrowser;

            e.preventDefault();
            e.stopPropagation();
            that.unhighlightAllDropTargets();
        },

        _windowDragEnterHandler: function(e){
            var that = $vf.fileBrowser;

            var dt = e.originalEvent.dataTransfer;
            if(dt.types != null && (dt.types.indexOf ? dt.types.indexOf('Files') != -1 : dt.types.contains('application/x-moz-file'))) {
                that.highlightAllDropTargets();
            }
        },

        _windowDragLeaveHandler: function(e){
            var that = $vf.fileBrowser;

            that.unhighlightAllDropTargets();
        },

        _bindDropRelatedEventListeners: function(){
            var that = $vf.fileBrowser;

            if (this.options.canUpload) {
                this.$listContainer.
                    bind('dragenter dragover', that._dragEnterHandler).
                    bind('drop dragend dragleave', that._dragLeaveHandler);

                $(window).
                    bind('dragenter dragover', that._windowDragEnterHandler).
                    bind('dragend mouseup drop dragexit', that._windowDragLeaveHandler);

                if (typeof Resumable !== 'undefined'){
                    this._resumable.unAssignDrop(this.$listContainer);
                    this._resumable.assignDrop(this.$listContainer);
                }
            }

        },

        _unbindDropRelatedEventListeners: function(){
            var that = this;

            if (this.options.canUpload) {
                this.$listContainer.
                    unbind("dragenter", that._dragEnterHandler).
                    unbind("dragover", that._dragEnterHandler).
                    unbind("drop", that._dragLeaveHandler).
                    unbind("dragend", that._dragLeaveHandler).
                    unbind("dragleave", that._dragLeaveHandler);

                $(window).
                    unbind("dragenter", that._windowDragEnterHandler).
                    unbind("dragover", that._windowDragEnterHandler).
                    unbind("drop", that._windowDragLeaveHandler).
                    unbind("dragend", that._windowDragLeaveHandler).
                    unbind("dragleave", that._windowDragLeaveHandler).
                    unbind("mouseup", that._windowDragLeaveHandler);

                if (typeof Resumable !== 'undefined'){
                    this._resumable.unAssignDrop(this.$listContainer);
                }
            }
        },

        _createEventListeners: function () {
            var that = this;

            this._bindDropRelatedEventListeners();

            this.$listContainer.
                bind({
                    'mouseleave': function (e) {
                        that.selectPath(null);
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

            if (typeof Resumable !== 'undefined'){
                if (this.options.canUpload) {
                    $(window).
                        bind('beforeunload', function (e) {
                            return that._confirmLeavePage();
                        });

                    this._resumable.assignDrop(this.$listContainer);
                    if (typeof this.options.uploadButton !== 'undefined'){
                        this._resumable.assignBrowse(this.options.uploadButton);
                    }
                }
                this._resumable.on('fileAdded', that._upsertUploadEntry);
                this._resumable.on('filesAdded', function(files){
                    that.replaceFiles = null;
                    that.filesToReplace = [];
                    if (files.length > that.options.maxFiles){
                        that.confirmingTooManyFiles = true;
                        var i;
                        var proceed = confirm("You added more than " +
                                    that.options.maxFiles +
                                    " files. Are you sure you want to proceed?");

                        if (!proceed){
                            for (i = 0; i < files.length; i += 1) {
                                files[i].cancel();
                            }
                        } else {
                            for (i = 0; i < files.length; i += 1) {
                                that._upsertUploadEntry(files[i]);
                            }
                        }
                        that.confirmingTooManyFiles = false;
                    }
                });
                this._resumable.on('fileProgress', function(file){
                    var uploadEntry = that._getUploadDataForId(file.uniqueIdentifier);

                    if (typeof uploadEntry !== 'undefined') {
                        uploadEntry.updateClassMarker();
                        uploadEntry.updateProgress(file.progress());
                    }
                    $(document).trigger('resumableFileProgress');
                });

                this._resumable.on('fileSuccess', function(file){
                    $vf.webflash();
                    var uploadEntry = that._getUploadDataForId(file.uniqueIdentifier);

                    if (typeof uploadEntry !== 'undefined') {
                        uploadEntry.uploadCompleted = true;
                        uploadEntry.removeWidget();
                        if (uploadEntry.getParentPath() == that.getActivePath()){
                            that.refreshActivePath();
                        } else {
                            that._loadPathData(uploadEntry.getParentPath());
                        }
                    }
                    that._resumable.upload();

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

        _confirmLeavePage: function (e) {
            if (typeof Resumable !== 'undefined' && this._resumable.isUploading()){
                return "Leaving this page will interrupt the current processes. Continue leaving?";
            }
        },

        _confirmReplaceFiles: function () {
            var that = $vf.fileBrowser;
            var $modalContainer = $('<div/>',{
                id: "replaceFilesDialog",
                title: "Replace files"
            });
            this.$replaceFilesDialogContent = $('<span/>', {
                text: "Found files with matching name. Do you want to replace them all?"
            }).appendTo($modalContainer);
            $modalContainer.dialog({
                autoOpen: true,
                modal: true,
                width: 450,
                height: 150,
                closeOnEscape: false,
                draggable: false,
                resizable: false,

                buttons: {
                    'Yes': function(){
                        $(this).dialog('close');
                        that.replaceFiles = true;
                        var i;
                        for (i = 0; i < that.filesToReplace.length; i += 1) {
                            that._upsertUploadEntry(that.filesToReplace[i]);
                        }
                        window.setTimeout(function(){
                            that.refreshActivePath();
                        },1000);
                    },
                    'No': function(){
                        $(this).dialog('close');
                        that.replaceFiles = false;
                        var i;
                        for (i = 0; i < that.filesToReplace.length; i += 1) {
                            that.filesToReplace[i].cancel();
                        }
                    }
                }
            });
        },

        moveContent: function(path){
            // We will move the already selected files here
            var that = this,
                data = new FormData(),
                key,
                path2;

            data.append('command', 'move_files');
            data.append('file_paths', JSON.stringify(Object.keys(that.selectedForMove)));

            that.lockInterface("Working...");
            $.ajax({
                url: this.options.getMoveUrlForPath(path),
                type: 'PUT',
                headers: {
                    'VFSessionID': $.cookie('_session_id')
                },
                dataType: "json",
                data: data,
                processData: false,
                contentType: false,
                success: function () {
                    that.unlockInterface();
                    $vf.webflash();
                    // reload affected folders

                    if (Object.keys(that.selectedForMove).length > 0){
                        // refresh folder we moved to
                        if (path == that.getActivePath()){
                            that.refreshActivePath()
                        } else {
                            that._loadPathData(path);
                        }

                        // refresh folder we moved from
                        key = Object.keys(that.selectedForMove)[0];
                        path2 = that.selectedForMove[key].getParentPath()
                        if (path2 == that.getActivePath()){
                            that.refreshActivePath()
                        } else {
                            that._loadPathData(path2);
                        }

                        that.resetMoveSelection();
                    }
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    that.unlockInterface();
                    $vf.ajaxErrorHandler(jqXHR, textStatus, errorThrown);
                }
            });
        },

        deleteContent: function(path, successCallback, successCallbackCtx){
            var that = this,
                object_type = 'file';

            if (RegExp(/\/$/i).test(path)){
                object_type = 'folder';
            }
            var go = confirm("Are you certain you want to delete this " + object_type + "?");
            if (go === true) {
                that.lockInterface("Working...");

                var uploadEntry = that._getUploadDataForPath(path);
                if (uploadEntry){
                    uploadEntry.markedDeleted = true;
                }

                $.ajax({
                    url: this.options.getDeleteURLForPath(path),
                    type: 'DELETE',
                    headers: {
                        'VFSessionID': $.cookie('_session_id')
                    },
                    dataType: "json",
                    success: function () {
                        that.unlockInterface();
                        $vf.webflash();
                        if (typeof successCallback  == 'function' &&
                            successCallbackCtx){

                            successCallback.call(successCallbackCtx);
                        }
                        if (object_type == 'file'){
                            //delete $vf.fileBrowser.uploadData[path];
                        } else {
                            $.each($vf.fileBrowser.folderCache, function (folderPath, obj) {
                                if (folderPath.substring(0, path.length) == path){
                                    delete $vf.fileBrowser.folderCache[folderPath];
                                }
                            });
                        }

                        that.refreshActivePath();
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                        that.unlockInterface();
                        $vf.ajaxErrorHandler(jqXHR, textStatus, errorThrown);
                    }
                });
            }
            return false;
        },

        _computeMD5Signature: function(file){
            var fileName = file.fileName||file.name; // Some confusion in different versions of Firefox
            var relativePath = file.webkitRelativePath || file.relativePath || fileName;
            if (relativePath.indexOf("/") == 0){
                relativePath = relativePath.substring(1);
            }
            var filePath = $vf.fileBrowser.getActivePath() + relativePath;
            var func = (file.slice ? 'slice' : (file.mozSlice ? 'mozSlice' : (file.webkitSlice ? 'webkitSlice' : 'slice')));
            var returnObj = {
                done : function(cb){
                    this.done_cb = cb;
                },
                fail : function(cb){
                    this.fail_cb = cb;
                }
            };

            if (file.size < 64000){
                var bytes = file[func](0, file.size),
                    reader = new FileReader();
                reader.onload = function(event){
                    var stringToHash = filePath + reader.result;
                    returnObj.done_cb(CryptoJS.MD5(stringToHash).toString());
                };
                reader.readAsText(bytes);
            } else {
                var bytes1 = file[func](0, 32000),
                    bytes2 = file[func](file.size-32000, file.size),
                    reader1 = new FileReader(),
                    reader2 = new FileReader(),
                    stringToHash1, stringToHash2;
                reader1.onload = function(event){
                    stringToHash1 = filePath + reader1.result;
                    reader2.readAsText(bytes2);
                };
                reader2.onload = function(event){
                    stringToHash2 = reader2.result;
                    returnObj.done_cb(CryptoJS.MD5(stringToHash1 + stringToHash2).toString());
                };
                reader1.readAsText(bytes1);
            }

            return returnObj;
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
                        that._updateStatusPanelForPath(path);
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
                if (pathData.isType('DIR') || pathData.isType('ZIP_FILE') || pathData.isType('ZIP_DIR')) {
                    that.goToDirForPathData(pathData);
                } else if (pathData.isType('FILE')) {
                    that.goToFileForPathData(pathData);
                }
            } else {
                window.location.href = pathData.href;
            }
        },

        goToDirForPathData: function (pathData) {
            var newTitle,
                currentURL = window.location.pathname + window.location.hash,
                newURL = pathData.href || this.options.getURLForPath(pathData.path),
                that = $vf.fileBrowser;
            console.log(currentURL, newURL);
            // animations
            this._animateListToPathData(pathData);
            this._animatePathToPathData(pathData);
            // history & location management
            if (currentURL !== newURL) {
                console.log('pushstate');
                newTitle = this.options.pageTitleFormat.
                    replace('{path}', pathData.path).
                    replace('{filename}', pathData.name);
                window.history.pushState({path: pathData.path},
                    newTitle, newURL);
            } else {
                window.history.replaceState({path: pathData.path},
                    $('head title').text(), window.location.href);
            }

            if (pathData.isType("ZIP_FILE") || pathData.isType("ZIP_DIR")){
                // unbind drop events
                that._unbindDropRelatedEventListeners();

            }
            if (pathData.isType("DIR")){
                // re-bind drop events
                that._bindDropRelatedEventListeners();
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

        ////////////////////////////////////////
        // MOVE related functions
        ////////////////////////////////////////

        isSelectedForMove: function(pathData){
            return pathData.path in this.selectedForMove;
        },

        isMovable: function(pathData){
            return (pathData.type != 'DIR' &&
                pathData.type != 'ZIP_DIR' &&
                pathData.type != 'ZIP_CONTAINED_FILE')
        },

        resetMoveSelection: function(){
            var i, pathKey, pathData;
            for (i = Object.keys(this.selectedForMove).length - 1; i >= 0; i--){
                pathKey = Object.keys(this.selectedForMove)[i];
                pathData = this.selectedForMove[pathKey];
                this.removeFromMoveSelection(pathData);
            }

            this.selectedForMove = {};
            this._lastSingleSelect = null;
            this._lastRangeSelect = null;
        },

        resetMoveSelectionIfNeeded: function(pathData){
            var key;
            if (Object.keys(this.selectedForMove).length > 0){
                key = Object.keys(this.selectedForMove)[0];
                if (this.selectedForMove[key].getParentPath() != pathData.getParentPath() ){
                    this.resetMoveSelection();
                }
            }
        },

        addToMoveSelection: function(pathData){
            var $listItem = this._findListItemByPath(pathData.path),
                className = this._class('listItem-selected-4-move');

            if (!this.isSelectedForMove(pathData)){
                this.selectedForMove[pathData.path] = pathData;
            }
            $listItem.addClass(className);
        },

        removeFromMoveSelection: function(pathData){
            var $listItem = this._findListItemByPath(pathData.path),
                className = this._class('listItem-selected-4-move');

            if (this.isSelectedForMove(pathData)){
                delete this.selectedForMove[pathData.path];
            }
            $listItem.removeClass(className);
        },


        addSingleToMoveSelection: function(pathData){
            if (pathData.type == 'DIR' ||
                pathData.type == 'ZIP_DIR' ||
                pathData.type == 'ZIP_CONTAINED_FILE'){
                return;
            }

            this.resetMoveSelectionIfNeeded(pathData);

            if (!this.isSelectedForMove(pathData)){
                this.addToMoveSelection(pathData);
                this._lastSingleSelect = pathData;
            } else {
                this.removeFromMoveSelection(pathData);
                this._lastSingleSelect = null;
            }
        },

        addRangeToMoveSelection: function(pathData){
            if (pathData.type == 'DIR' ||
                pathData.type == 'ZIP_DIR' ||
                pathData.type == 'ZIP_CONTAINED_FILE'){
                return;
            }

            var previousRangeSelect = this._lastRangeSelect,
                $listItem = this._findListItemByPath(pathData.path),
                $targetListItem,
                $singleSelectListItem,
                $previousRangeListItem,
                path,
                targetPathData,
                idx1,
                idx2,
                idx3;

            this.resetMoveSelectionIfNeeded(pathData);

            if (this._lastSingleSelect == null){
                // Find the first suitable item in the list and designate
                // that as the single select
                $targetListItem = $listItem.parent().children().first();
                while ($targetListItem.length){
                    path = this._unescapePath($targetListItem.attr('data-vf-path'));
                    if (typeof path === 'undefined'){
                        $targetListItem = $targetListItem.next();
                        continue;
                    }
                    targetPathData = this.data[path];
                    if (targetPathData.type == 'DIR' ||
                        targetPathData.type == 'ZIP_DIR' ||
                        targetPathData.type == 'ZIP_CONTAINED_FILE'){

                        $targetListItem = $targetListItem.next();
                    } else {
                        this.addSingleToMoveSelection(targetPathData);
                        break;
                    }
                }
            }

            $singleSelectListItem = this._findListItemByPath(this._lastSingleSelect.path);
            idx1 = $singleSelectListItem.index();
            idx2 = $listItem.index();

            if (previousRangeSelect != null){
                $previousRangeListItem = this._findListItemByPath(previousRangeSelect.path);
                idx3 = $previousRangeListItem.index();

                $targetListItem = $previousRangeListItem;
                while (true){
                    path = this._unescapePath($targetListItem.attr('data-vf-path'));
                    if (typeof path === 'undefined'){
                        continue;
                    }
                    targetPathData = this.data[path];
                    if (this.isMovable(targetPathData)){

                        this.removeFromMoveSelection(targetPathData);
                    }
                    if (targetPathData.path === pathData.path){
                        break;
                    }
                    if (idx3 < idx2){
                        $targetListItem = $targetListItem.next();
                    }
                    if (idx3 > idx2){
                        $targetListItem = $targetListItem.prev();
                    }
                }
            }

            $targetListItem = $singleSelectListItem;
            while (true){
                path = this._unescapePath($targetListItem.attr('data-vf-path'));
                if (typeof path === 'undefined'){
                    continue;
                }
                targetPathData = this.data[path];
                if (this.isMovable(targetPathData)){
                    this.addToMoveSelection(targetPathData);
                }
                if (targetPathData.path === pathData.path){
                    break;
                }

                if (idx1 < idx2){
                    $targetListItem = $targetListItem.next();
                }
                if (idx1 > idx2){
                    $targetListItem = $targetListItem.prev();
                }
            }

            this._lastRangeSelect = pathData;
        },

        selectPath: function (path) {
            var that = this,
                className,
                oldPath,
                pathData;
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
                pathData = this.data[path];
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

        _upsertUploadEntry: function(resumableFile){
            var that = $vf.fileBrowser;
            if (that.confirmingTooManyFiles){
                return;
            }
            var path = that.getActivePath() + resumableFile.fileName;
            // If the relative path starts with a "/" we need to check folders
            if (resumableFile.relativePath.indexOf("/") == 0){
                path = that.getActivePath() + resumableFile.relativePath.substring(1);
                var i,
                    pathParts = resumableFile.relativePath.substring(1).split("/"),
                    parentPath = that.getActivePath();
                for (i = 0; i < pathParts.length - 1; i += 1) {
                    that._upsertFolder(parentPath, pathParts[i]);
                    parentPath = parentPath + pathParts[i] + "/";
                }
            }

            var uploadEntry = that._getUploadDataForPath(path);

            resumableFile.pause(true);

            if (typeof uploadEntry !== 'undefined' &&
                uploadEntry.md5Signature != resumableFile.uniqueIdentifier){

                if (that.replaceFiles == null){
                    that.filesToReplace.push(resumableFile);
                    if (that.filesToReplace.length == 1){
                        that._confirmReplaceFiles();
                    }
                    return;
                } else {
                    if (that.replaceFiles){
                        delete $vf.fileBrowser.uploadData[path];
                        uploadEntry.getUploadWidget().remove();
                        if (uploadEntry.isActive()){
                            uploadEntry.resumableFile.cancel();
                        }
                        uploadEntry = undefined;
                    }
                }
            }

            if (typeof uploadEntry === 'undefined' || uploadEntry.markedDeleted == true){
                var _uploadEntry = {
                    path : path,
                    name : resumableFile.fileName,
                    md5Signature : resumableFile.uniqueIdentifier,
                    type : "FILE",
                    uploadProgress : 0.0,
                    uploadCompleted : false,
                    extra : {size : $vf.prettyPrintByteSize(resumableFile.size)},
                    resumableFile : resumableFile,
                    initializing: true,
                    markedDeleted: false
                };
                uploadEntry = new UploadDataObject(_uploadEntry);
                var data = new FormData();
                data.append('resumableFilename', resumableFile.fileName);
                data.append('resumableTotalSize', resumableFile.size);
                data.append('resumableIdentifier', resumableFile.uniqueIdentifier);
                data.append('resumableChunkSize', $vf.fileBrowser.options.chunkSize);
                if (that.replaceFiles){
                    data.append('forceReplace', true);
                }

                // POST to file upload interface
                $.ajax({
                    'url': that.options.getResumableUploadUrl(resumableFile, []),
                    'type': 'POST',
                    'data': data,
                    'headers': {
                        'VFSessionID': $.cookie('_session_id')
                    },
                    'success': function (e) {
                        that._uploadEntryUpserted(uploadEntry);
                    },
                    'error' : function (e) {
                        // We found a file with the same path information
                        if (e.status == 302){
                            if (e.responseText){
                                var responseData = JSON.parse(e.responseText);
                                if (responseData.detail) {
                                    if (responseData.detail == "File already exists"){
                                        resumableFile.cancel();
                                    }
                                    if (responseData.detail == "File with different content exists"){
                                        if (that.replaceFiles == null){
                                            that.filesToReplace.push(resumableFile);
                                            if (that.filesToReplace.length == 1){
                                                that._confirmReplaceFiles();
                                            }
                                        }
                                    }
                                }
                            } else {
                                resumableFile.cancel();
                            }
                        }
                    },
                    'processData': false,
                    'contentType': false
                });

            } else {
                if (uploadEntry.uploadCompleted){
                    return;
                }
                uploadEntry.resumableFile = resumableFile;
                uploadEntry.md5Signature = resumableFile.uniqueIdentifier;
                uploadEntry.initializing = true;
                uploadEntry.markedDeleted = false;
                if (typeof uploadEntry.partNumbers !== 'undefined'){
                    var i;
                    for (i = 0; i < uploadEntry.partNumbers.length; i += 1) {
                        // Part numbers start from 1
                        var partNumber = uploadEntry.partNumbers[i] -1;
                        resumableFile.chunks[partNumber].xhr = {status: 201};
                    }
                }
                that._uploadEntryUpserted(uploadEntry);
            }
        },

        _uploadEntryUpserted: function(uploadEntry){
            $vf.fileBrowser.uploadData[uploadEntry.path] = uploadEntry;
            uploadEntry.resumableFile.pause(false);
            $vf.fileBrowser._updateStatusPanelForPath($vf.fileBrowser.getActivePath());
            $(window).scrollTo(0);
            uploadEntry.highlight();
            $vf.fileBrowser._resumable.upload();
        },

        _upsertFolder: function(parentPath, folderName){
            var that = $vf.fileBrowser;
            var folderPath = parentPath + folderName + "/";
            if (that.folderCache[folderPath]){
                return;
            }
            $.ajax({
                url: this.options.getURLForPath(parentPath),
                type: 'POST',
                data: {
                    _session_id: $.cookie('_session_id'),
                    'folder': folderName
                },
                dataType: "json",
                success: function () {
                    that.folderCache[folderPath] = true;
                    if (parentPath == that.getActivePath()){
                        that.refreshActivePath();
                    } else {
                        that._loadPathData(parentPath);
                    }
                },
                error: function (e) {
                    if (e.status == 302){
                        that.folderCache[folderPath] = true;
                    }
                }
            });
        },

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
            if (callback){
                callback.call(this, pathData);
            }
        },

        _convertPathData: function(loadedData, path){
            var pathData, uploadDataEntry,
                that = this,
                uploadData = {},
                newLoadedData = {};
            $.each(loadedData, function (k, v) {
                v = that.options.prepareRawPathData.call(that, v);
                var key = $vf.htmlDecode(k);
                var zipSafeKey = key;

                if (key.endsWith('.zip/')){
                    zipSafeKey = key.substring(0, key.length-1);
                }

                newLoadedData[key] = new PathDataObject(v);
                // Collect files that have not been uploaded into separate bucket
                if (typeof v.uploadCompleted !== 'undefined' && !v.uploadCompleted){
                    uploadDataEntry = that._getUploadDataForPath(key);
                    if (typeof uploadDataEntry == 'undefined'){
                        uploadDataEntry = uploadData[zipSafeKey] = new UploadDataObject(v);
                        uploadDataEntry.path = zipSafeKey;
                    }
                    if (!uploadDataEntry.uploadCompleted){
                        delete newLoadedData[key];
                    }
                }
            });
            $.extend(this.uploadData, uploadData);
            $.extend(this.data, newLoadedData);
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

        _listUploadDataForPath: function (path) {
            var listData = [];
            $.each(this.uploadData, function (itemPath, itemData) {
                if (itemData.getParentPath() === path) {
                    listData.push(itemData);
                }
            });
            return listData;
        },

        _getUploadDataForPath: function (path) {
            var that = this,
                uploadEntry;
            $.each(that.uploadData, function (itemPath, itemData) {
                if (itemData.path == path) {
                    uploadEntry = itemData;
                    return false;
                }
            });
            return uploadEntry;
        },

        _getUploadDataForId: function (id) {
            var that = this,
                uploadEntry;
            $.each(that.uploadData, function (itemPath, itemData) {
                if (itemData.md5Signature === id) {
                    uploadEntry = itemData;
                    return false;
                }
            });
            return uploadEntry;
        },

        findResumableFileById: function(id){
            if (typeof this._resumable !== 'undefined'){
                var i;
                for (i = 0; i < this._resumable.files.length; i += 1) {
                    var file = this._resumable.files[i];
                    if (file.uniqueIdentifier == id){
                        return file;
                    }
                }
            }
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

        _updateStatusPanelForPath: function(path) {
            var that = this;

            //that.$statusContainer.empty();
            that.$statusContainer.children().detach();
            $.each(that._listUploadDataForPath(path),
                function (i, uploadData) {
                    if (!uploadData.widgetRemoved && !uploadData.markedDeleted){
                        uploadData.getUploadWidget().appendTo(that.$statusContainer);
                        if (uploadData.uploadCompleted){
                            uploadData.removeWidget();
                        }
                    }
                });
        },

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

            if (this.options.canUpload){
                $.contextMenu({
                    selector: ".vf-filebrowser-listItem-row-file, .vf-filebrowser-listItem-row-zip_file",
                    autoHide: true,
                    build: function($trigger, e) {
                        // this callback is executed every time the menu is to be shown
                        // its results are destroyed every time the menu is hidden
                        // e is the original contextmenu event, containing e.pageX and e.pageY (amongst other data)
                        var path = that._unescapePath($trigger.attr('data-vf-path')),
                            targetPathData = that.data[path];

                        return {
                            items: {
                                "paste": {
                                    name: function (){
                                        var label = "Paste ";
                                        if (Object.keys(that.selectedForMove).length == 1){
                                            label += "1 item"
                                        } else {
                                            label += Object.keys(that.selectedForMove).length +" items"
                                        }
                                        return label;
                                    },
                                    icon: "paste",
                                    visible: function(key, opt){
                                        var key;

                                        if (Object.keys(that.selectedForMove).length > 0){
                                            key = Object.keys(that.selectedForMove)[0];
                                            if (targetPathData.getParentPath() != that.selectedForMove[key].getParentPath()){
                                                return true;
                                            }
                                        }
                                        return false;
                                    },
                                    callback: function(key, option){
                                        that.moveContent(targetPathData.getParentPath());
                                        return true;
                                    }
                                },
                                "select": {
                                    name: "Select",
                                    icon: "add",
                                    visible: function(key, opt){
                                        if (that.isMovable(targetPathData)){
                                            if (!that.isSelectedForMove(targetPathData)){
                                                return true;
                                            }
                                        }
                                        return false;
                                    },
                                    callback: function(key, options){
                                        that.addSingleToMoveSelection(targetPathData);
                                        return true;
                                    }
                                },
                                "deselect": {
                                    name: "Deselect",
                                    icon: "quit",
                                    visible: function(key, opt){
                                        if (that.isMovable(targetPathData)){
                                            if (that.isSelectedForMove(targetPathData)){
                                                return true;
                                            }
                                        }
                                        return false;
                                    },
                                    callback: function(key, options){
                                        that.removeFromMoveSelection(targetPathData);
                                        return true;
                                    }
                                },
                                "deselect_all": {
                                    name: "Deselect all",
                                    icon: "quit",
                                    visible: function(key, opt){
                                        if (that.isMovable(targetPathData)){
                                            if (Object.keys(that.selectedForMove).length > 0){
                                                return true;
                                            }
                                        }
                                        return false;
                                    },
                                    callback: function(key, options){
                                        that.resetMoveSelection();
                                        return true;
                                    }
                                },
                                "delete": {
                                    name: "Delete",
                                    icon: "delete",
                                    callback: function(key, options){
                                        // Delayed execution so that the
                                        // confirm dialog would not block the
                                        // context menu hide animation
                                        setTimeout(
                                            function() {
                                                that.deleteContent(targetPathData.path)
                                            },
                                            100);
                                        return true;
                                    }
                                },
                                "download": {
                                    name: "Download",
                                    className: "context-menu-icon vf-filebrowser-context-menu-download",
                                    visible: function(key, opt){
                                        if (targetPathData.downloadURL){
                                            return true;
                                        }
                                        return false;
                                    },
                                    callback: function(key, options){
                                        $('<iframe>', { id:'idown', src:targetPathData.downloadURL }).hide().appendTo('body');
                                        return true;
                                    }
                                },
                                "sep1": "---------",
                                "quit": {
                                    name: "Quit",
                                    icon: "quit",
                                    callback: function(key, options){
                                        return true;
                                    }
                                }
                            }
                        };
                    }
                });

                $.contextMenu({
                    selector: ".vf-filebrowser-listItem-row-dir",
                    autoHide: true,
                    build: function($trigger, e) {
                        // this callback is executed every time the menu is to be shown
                        // its results are destroyed every time the menu is hidden
                        // e is the original contextmenu event, containing e.pageX and e.pageY (amongst other data)
                        var path = that._unescapePath($trigger.attr('data-vf-path')),
                            targetPathData = that.data[path];

                        return {
                            items: {
                                "paste": {
                                    name: function (){
                                        var label = "Paste ";
                                        if (Object.keys(that.selectedForMove).length == 1){
                                            label += "1 item"
                                        } else {
                                            label += Object.keys(that.selectedForMove).length +" items"
                                        }
                                        return label;
                                    },
                                    icon: "paste",
                                    visible: function(key, opt){
                                        if (Object.keys(that.selectedForMove).length > 0){
                                            return true;
                                        }
                                        return false;
                                    },
                                    callback: function(key, option){
                                        that.moveContent(targetPathData.path);
                                        return true;
                                    }
                                },
                                "delete": {
                                    name: "Delete",
                                    icon: "delete",
                                    callback: function(key, options) {
                                        // Delayed execution so that the
                                        // confirm dialog would not block the
                                        // context menu hide animation
                                        setTimeout(
                                            function() {
                                                that.deleteContent(targetPathData.path)
                                            },
                                            100);
                                        return true;
                                    }
                                },
                                "sep1": "---------",
                                "quit": {
                                    name: "Quit",
                                    icon: "quit",
                                    callback: function(key, options){
                                        return true;
                                    }
                                }
                            }
                        };
                    }
                });

                $.contextMenu({
                    selector: ".vf-filebrowser-listItem-header-row, vf-filebrowser-listControlPanel",
                    autoHide: true,
                    build: function($trigger, e) {
                        // this callback is executed every time the menu is to be shown
                        // its results are destroyed every time the menu is hidden
                        // e is the original contextmenu event, containing e.pageX and e.pageY (amongst other data)
                        return {
                            items: {
                                "paste": {
                                    name: function (){
                                        var label = "Paste ";
                                        if (Object.keys(that.selectedForMove).length == 1){
                                            label += "1 item"
                                        } else {
                                            label += Object.keys(that.selectedForMove).length +" items"
                                        }
                                        return label;
                                    },
                                    icon: "paste",
                                    visible: function(key, opt){
                                        if (Object.keys(that.selectedForMove).length > 0){
                                            return true;
                                        }
                                        return false;
                                    },
                                    callback: function(key, option){
                                        that.moveContent(that._activePath);
                                        return true;
                                    }
                                },
                                "sep1": "---------",
                                "quit": {
                                    name: "Quit",
                                    icon: "quit",
                                    callback: function(key, options){
                                        return true;
                                    }
                                }
                            }
                        };
                    }
                });
            }


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
                fileDetails,
                moveClassName = this._class('listItem-selected-4-move');

            $listItem = $('<li/>').
                addClass(this._class('listItem')).
                addClass(this._class('listItem-row')).
                addClass(this._class('listItem-row-' + typeName)).
                attr('data-vf-path', that._escapePath(pathData.path)).
                appendTo($list).
                bind('mouseenter', function (e) {
                    that.selectPath(pathData.path);
                });

            if (pathData.mimetype) {
                $listItem.attr('data-mimetype', pathData.mimetype);
            }
            if (this.isSelectedForMove(pathData)){
                $listItem.addClass(moveClassName);
            }

            $listItemFile = $('<div/>').
                addClass(this._class('listItem-cell')).
                addClass(this._class('listItem-cell-file')).
                addClass(this._class('listItem-cell-file-' + typeName)).
                appendTo($listItem);

            if (pathData.href){
                $listItemLink = $('<a/>').
                addClass(this._class('listItem-link-file')).
                addClass(this._class('listItem-link-file-' + typeName)).
                attr('href', pathData.href).
                appendTo($listItemFile).
                bind('click', function (e) {
                    if (that.options.canUpload){
                        if (e.metaKey || e.ctrlKey){
                            e.preventDefault();
                            that.addSingleToMoveSelection(pathData);
                            return;
                        }
                        if (e.shiftKey){
                            e.preventDefault();
                            that.addRangeToMoveSelection(pathData);
                            return;
                        }
                    }

                    if ((pathData.type === 'DIR' || pathData.type === 'ZIP_FILE' || pathData.type === 'ZIP_DIR') && e.which === 1) {
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
                    if (pathData.isType("ZIP_FILE")) {
                        artifactLinkParams.iconURL = "FILE_ZIP";
                    }

                    artifactLink = new $vf.ArtifactLink(artifactLinkParams);
                    $listItemLink.data('artifactLink', artifactLink);
                    $listItemLink.empty();
                    artifactLink.render();
                }
            } else{
                $listItemLinkName = $('<span/>').
                    addClass(this._class('listItem-link-file-name')).
                    addClass(this._class('listItem-link-file-name-' + typeName)).
                    text(pathData.name).
                    appendTo($listItemFile);
                if (pathData.virus_scan_status && pathData.virus_scan_status == 'unscanned'){
                    $listItemLinkName.addClass('being-virus-scanned');
                }
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
            if (pathData.virus_scan_status && pathData.virus_scan_status == 'unscanned') {
                $listItem.attr('title', 'Status: Scanning for virus');
                $('<span/>').
                    addClass(this._class('listItem-note')).
                    text(" - [Processing]").
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
                    if (e.which === 1 && (childData.isType('DIR') || childData.isType('ZIP_DIR'))) {
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
