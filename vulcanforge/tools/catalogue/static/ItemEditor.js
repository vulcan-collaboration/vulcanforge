/**
 * Core code for the Publish New page of ForgeExchange tool.
 *
 *
 * @author Papszi
 *
 */

var $catalogue = $catalogue || {};

(function (global) {
    "use strict";

    // Import Globals

    var $ = global.jQuery,
        trace = global.trace,
        qq = global.qq,
        $vf = global.$vf;

    /**
     * Main class for Publishing components.
     *
     * @class Publisher
     * @namespace $catalogue
     * @constructor
     *
     */

    $catalogue.Publisher = function (config) {
        this.$step1Holder = $('#step1');
        this.$step2Holder = $('#step2');
        this.$step3Holder = $('#step3');

        this.$step2Condom = new $vf.ClickCondom(this.$step2Holder);
        this.$step3Condom = new $vf.ClickCondom(this.$step3Holder);

        this.$uploadHolder = $('#uploadHolder');
        this.$addFileButton = $('#addFileButton');

        this.$metaDescContainer = $('#metaDescriptorContainer');
        this.$metaDescriptor = $('#metaDescriptor');

        this.$propertiesHolder = $('#itemProperties');

        $.extend(this, config);

        $vf.itemEditor = this;

        var config = {mode:'INPUT'};
        $catalogue.baseProperties.config(config);
        $.each($catalogue.features, function (featureName, feature) {
            feature.config(config);
        });

        if (this.publishPleaseWait) {
            this.publishPleaseWait.update('Updating information...');
        } else {
            this.publishPleaseWait = new $vf.PleaseWait('Updating information...', $('#itemContainer'));
        }

        this._resumable = new Resumable({
            target: this.getResumableUploadUrl,
            uploadMethod: "PUT",
            simultaneousUploads: 5,
            generateUniqueIdentifier: this.computeMD5Signature,
            throttleProgressCallbacks: 1, // How often should progress updates be called
            fileType: $catalogue.metaFileExts,
            maxFiles: 1,
            maxChunkRetries: 1,
            headers: {
                'VFSessionID': $.cookie('_session_id')
            }
        });
        this._resumable.assignDrop(this.$addFileButton);
        this._resumable.assignBrowse(this.$addFileButton);
        this._resumable.on('fileAdded', this._fileAdded);
        this._resumable.on('fileSuccess', function(file){
            $vf.webflash();
            $vf.itemEditor.updateDisplay();
        });

        $("#deleteButton").data('host', this);
        $("#deleteButton").click(function () {
            var host = $(this).data('host');
            $catalogue.deleteItem($catalogue.versionedItemType,
                $catalogue.versionedItemUrl, $catalogue.versionedItemSL.url);
            return false;
        });

        $("#releaseButton").data('host', this);
        $("#releaseButton").click(function () {
            var host = $(this).data('host');
            host.upsertVersionedItem("release");
            return false;
        });

        $("#saveButton").data('host', this);
        $("#saveButton").click(function () {
            var host = $(this).data('host');
            host.upsertVersionedItem("save");
            return false;
        });

        $vf.itemEditor._showEverything();
        $vf.itemEditor.updateDisplay();
    };

    $catalogue.Publisher.prototype = {
        state: null,

        versionedItemUrl: null,

        $uploadHolder: null,
        $addFileButton: null,

        $metaDescContainer: null,
        $metaDescriptor: null,

        $propertiesHolder: null,

        // UI elements
        $step1Holder: null,
        $step2Holder: null,
        $step3Holder: null,

        $step1Condom: null,
        $step2Condom: null,
        $step3Condom: null,

        publishPleaseWait: null,

        // Data structures
        itemData: null,
        resumableFile: null,
        metaFileDict: null,
        selectedMetaFile: null,

        firstUpdateTime: null,
        timeRemaining: null,
        firstProgressPoint: null,

        getResumableUploadUrl: function(file, params){
            return null;
        },

        computeMD5Signature: function(file){
            var fileName = file.fileName||file.name; // Some confusion in different versions of Firefox
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
                    var stringToHash = fileName + reader.result;
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
                    stringToHash1 = fileName + reader1.result;
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

        _fileAdded: function(resumableFile){
            var that = $vf.itemEditor,
                data = that.prepareAjaxData();

            that.resumableFile = resumableFile;
            that.resumableFile.pause(true);

            data.append("metaFileName", resumableFile.fileName);
            data.append("metaFile", resumableFile.file);
            that.upsertVersionedItem("set_meta", data);
        },

        _hideEverything: function() {
            this.$step1Holder.hide();
            this.$step2Holder.hide();
            this.$step3Holder.hide();
        },

        _showEverything: function() {
            this.$step1Holder.show();
            this.$step2Holder.show();
            this.$step3Holder.show();
        },

        _canRelease: function(){
            if (this.itemData != null &&
                !this.itemData.released &&
                this.itemData.name &&
                this.itemData.version &&
                this.itemData.meta_file){

                return true;
            }

            return false;
        },

        _canSave: function(){
            return (typeof $catalogue.versionedItemId !== 'undefined');
        },

        _canDelete: function(){
            // the versioned Item id is set
            return (typeof $catalogue.versionedItemId !== 'undefined');
        },

        initPropertySheet: function () {
            this._hideEverything();
            this.publishPleaseWait.show();

            $.ajax({
                url: $catalogue.versionedItemSL.url + $catalogue.versionedItemId + '/data',
                type: "GET",
                data: {},
                dataType: 'json',
                context: this,
                complete: function () {
                    $vf.itemEditor.publishPleaseWait.hide();
                },
                success: function (result) {
                    $vf.itemEditor.update(result);
                },
                error: $catalogue.ajaxErrorHandler
            });
        },

        setFileDescriptor: function (meta_file) {
            this.$metaDescriptor.empty();

            var metaDesc = meta_file.key.replace(/^(\S*\/+)/g, '') +
                " (" + meta_file.pretty_size + ")";
            $('<span/>', {
                'text': metaDesc
            }).appendTo(this.$metaDescriptor);
        },

        _getFileSize: function() {
            if (this.itemData && this.itemData.zip_file) {
                return this.itemData.zip_file.pretty_size;
            }

            if (this.resumableFile){
                return $vf.prettyPrintByteSize(this.resumableFile.size);
            }
        },

        setValues: function (response) {
            this.itemData = response;
            $catalogue.versionedItemId = response.id;
            $catalogue.versionedItemUrl = response.url;


            var $errorList = $('.validation-container-errors ul'),
                $warningList = $('.validation-container-warnings ul');
            $catalogue.baseProperties.setValues(response);
            if (typeof(response.meta_file) !== 'undefined'){
                this.setFileDescriptor(response.meta_file);
            }
            if (response.zip_file){
                this.uploadProgress = response.zip_file.progress;
            }
            $.each($catalogue.features, function (featureName, feature) {
                if (typeof(response[featureName]) !== 'undefined'){
                    feature.setValues(response[featureName]);
                }

            });
        },

        update: function (response) {
            $catalogue.webflash();
            this._showEverything();
            var versionedItemId = $catalogue.versionedItemId;
            if (!response.error) {
                this.setValues(response);
                this.updateDisplay();
            }
            var newUrl = $catalogue.versionedItemId
            if (versionedItemId == null){
                history.replaceState(null, null, $catalogue.versionedItemId + '/edit');
            }
        },

        prepareAjaxData: function () {
            var data = new FormData();
            data.append('baseProperties', JSON.stringify($catalogue.baseProperties.getValues()));

            $.each($catalogue.features, function (featureName, feature) {
                data.append(featureName, JSON.stringify(feature.getValues()));
            });

            if (this.resumableFile){
                data.append('md5Signature', this.resumableFile.uniqueIdentifier);
                data.append('zipFileName', this.resumableFile.fileName);
                data.append('zipFileSize', this.resumableFile.size);
            }

            return data;
        },

        upsertVersionedItem: function(command, data){
            if (!data){
                var data = this.prepareAjaxData();
            }
            if (command){
                data.append('command', command);
            }

            var method = "POST",
                url = $catalogue.versionedItemSL.url;

            if (this.itemData){
                method = "PUT";
                url = this.itemData.url;
            }

            $vf.itemEditor.publishPleaseWait.show();
            $.ajax({
                url: url,
                type: method,
                data: data,
                dataType: "json",
                context: this,
                processData: false,
                contentType: false,
                headers: {
                    'VFSessionID': $.cookie('_session_id')
                },
                complete: function () {
                    $vf.itemEditor.publishPleaseWait.hide();
                },
                success: function (result) {
                    $catalogue.webflash();
                    //window.location.href = $catalogue.versionedItemSL.url;
                    $vf.itemEditor.update(result);
                },
                error: $catalogue.ajaxErrorHandler
            });
        },

        updateDisplay:function () {
            // STEP 1: Add archive
            this.$step1Holder.addClass('on');

            this.$metaDescContainer.hide();
            if (this.itemData && this.itemData.meta_file){
                this.$metaDescContainer.show();
                this.$uploadHolder.hide();
            }
            if (this.resumableFile) {
                this.$uploadHolder.hide();
            }

            // STEP 2: Describe
            if (this.itemData){
                this.$step2Holder.addClass('on');
                $('#NA2').hide();
                this.$step2Condom.hide();
                $('#baseProperties').show();
                if (this.itemData.properties){
                    this.$propertiesHolder.show();
                    $catalogue.baseProperties.render();
                    $.each($catalogue.features, function (featureName, feature) {
                        feature.render();
                    });
                } else {
                    this.$propertiesHolder.hide();
                }

            } else {
                this.$step2Holder.removeClass('on');
                $('#baseProperties').hide();
                this.$step2Condom.show();
                $('#NA2').show();
            }

            // STEP 3: Finalize
            if (this._canDelete() || this._canSave() || this._canRelease()){
                this.$step3Condom.hide();
                this.$step3Holder.addClass('on');
            } else {
                this.$step3Condom.show();
                this.$step3Holder.removeClass('on');
            }

            if (this._canSave()){
                $('#saveButton').removeAttr("disabled");
            } else {
                $('#saveButton').attr("disabled", "disabled");
            }
            if (this._canRelease()){
                $('#releaseButton').removeAttr("disabled");
            } else {
                $('#releaseButton').attr("disabled", "disabled");
            }
            if (this._canDelete()){
                $('#deleteButton').removeAttr("disabled");
            } else {
                $('#deleteButton').attr("disabled", "disabled");
            }

        }
    };

}(window));
