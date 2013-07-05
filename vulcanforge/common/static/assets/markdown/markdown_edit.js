/*global window*/

/*
 * Initializing markup-edit stuff.
 *
 * @author Naba Bana
 */
(function (global) {
    "use strict";

    // Local globals
    var $ = global.$,
        contentAreasWrapper = $('#content-areas-wrapper'),
        oldContentAreaWrapperPosition,
        $closeButton = $('<div/>', {
            "class": "icon ico-close close",
            title: 'Close Markdown Help'
        }),
        helpArea = null,
        windowURL = global.URL || global.webkitURL;

    /* AttachmentManager manages markdown attachment interaction
       (finds urls, available attachments, etc) */
    function AttachmentManager($uploadFieldList, $attachmentList){
        var that = this;
        this.attachments = {};
        this.uploadAttachments = {};

        function init(){
            parseAttachmentList();
        }

        function parseAttachmentList(){
            if ($attachmentList !== undefined && $attachmentList !== null){
                $attachmentList.find('.attachment').each(function(i){
                    var filename = $(this).attr('data-filename');
                    that.attachments[filename] = {
                        is_image: $(this).find('.img-thumb').length > 0,
                        $el: $(this)
                    };
                    that.attachments[filename].url = $(this).attr('data-url') ? $(this).attr('data-url') : null;
                });
            }
        }

        function parseUploadFields(){
            if ($uploadFieldList !== undefined && $uploadFieldList !== null){
                $uploadFieldList.find('input').each(function(i, el){
                    var file = el.files[0];
                    if (file){
                        that.uploadAttachments[file.name] = {
                            is_image: file.type.match(/image.*/),
                            $el: this
                        };
                    }
                });
            }
        }

        /* api (these are used by prototype methods) */
        this.parseUploadFields = parseUploadFields;

        init();
    }
    AttachmentManager.prototype = {
        getLocalUrlforFilename: function (filename){
            var att, previewUrl = null;
            if (this.uploadAttachments.hasOwnProperty(filename)){
                att = this.uploadAttachments[filename];
                previewUrl = windowURL.createObjectURL(att.$el.files[0]);
            } else if (this.attachments.hasOwnProperty(filename) && this.attachments[filename].url){
                previewUrl = this.attachments[filename].url;
            } else {
                previewUrl = './attachment/' + filename;
            }
            return previewUrl;
        },
        getAvailableImages: function () {
            var available = [], fname;
            for (fname in this.attachments){
                if (this.attachments.hasOwnProperty('fname') && this.attachments[fname]['is_image']){
                    available.push({
                        filename: fname,
                        url: fname
                    });
                }
            }
            this.parseUploadFields();
            for (fname in this.uploadAttachments){
                if (this.attachments.hasOwnProperty('fname') && this.uploadAttachments[fname]['is_image']){
                    available.push({
                        filename: fname,
                        url: fname
                    });
                }
            }
            return available;
        }
    };

    /* help panel */
    function openHelpPanel(evt) {
        evt.preventDefault();
        if (!helpArea){
            $.ajax({
                url: '/nf/markdown_syntax',
                type: "GET",
                success: function(response){
                    helpArea = $('<div/>', {
                        "class": "modal markdown-help"
                    }).append( $closeButton ).css("display", "none")
                        .append(response);

                    oldContentAreaWrapperPosition = contentAreasWrapper.css('position');
                    contentAreasWrapper.css('position', 'fixed');

                    helpArea.lightbox_me({
                        centered: true,
                        overlayCSS: {
                            position: 'fixed',
                            background: 'black',
                            opacity: .3
                        },
                        onClose: function () {
                            contentAreasWrapper.css('position', oldContentAreaWrapperPosition);
                        }
                    });
                }
            });
        } else {

            oldContentAreaWrapperPosition = contentAreasWrapper.css('position');
            contentAreasWrapper.css('position', 'fixed');

            helpArea.lightbox_me({
                onClose: function () {
                    contentAreasWrapper.css('position', oldContentAreaWrapperPosition);
                }
            });
        }
    }

    /* Markdown Edit Widget -- called on markdown edit container*/
    $.widget('vf.markdownEdit', {
        options: {
            converter: null,
            attachmentManager: null
        },
        _create: function() {
            var that = this;
            this.element.find('.markdown-help-button').click(function(evt){
                return that._help(evt, that);
            });
            this.$textarea = this.element.find('textarea');
            this.$textarea.tabby({tabString : "    "});
            this.context_id = this.element.attr("data-context-id");
            this.converter = this.options.converter;
            this.attachmentManager = this.options.attachmentManager;
            if (this.attachmentManager === null){
                this._setupAttachmentManager();
            }
            if (this.converter === null){
                this._setupConverter();
            }
            this._setupEditor();
        },
        _setupAttachmentManager: function(){
            var $uploadFieldList = this.element.closest('form').find('.vf-repeated-attachment-field'),
                attachmentContextId,
                $attachmentList;
            if ($uploadFieldList.length === 0){
                $uploadFieldList = null;
            }
            if (attachmentContextId = this.element.attr("data-attachment-context-id")){
                $attachmentList = $("#attachment-list-" + attachmentContextId);
            }
            this.attachmentManager = new AttachmentManager($uploadFieldList, $attachmentList);
            return this.attachmentManager;
        },
        _setupConverter: function(){
            var that = this;
            this.converter = new Markdown.Converter();
            this.converter.hooks.chain("postConversion", function(text){
                 return '<div class="markdown_content">' + text + '</div>';
            });
            this.converter.hooks.chain("postConversion", function(text){
                return text.replace(/.*<pre><code>([^<]+)<\/code><\/pre>.*/gm, function(whole, inner){
                    return '<pre><code class="prettyprint">'+ prettyPrintOne(inner) + '</code></pre>';
                });
            });
            this.converter.hooks.chain("postSpanGamut", function(text){
                return text.replace(/\[\[(img[^\]]+src="?([^"\s]+)"?[^\]]+)\]\]/g, function (whole, attributes, src) {
                    var localUrl = that.attachmentManager.getLocalUrlforFilename(src);
                    return '<' + attributes.replace(src, localUrl) + '/>';
                });
            });
            return this.converter;
        },
        _setupEditor: function(){
            var that = this;
            this.editor = new Markdown.Editor(this.converter, "-" + this.context_id);
            this.editor.hooks.set("insertImageDialog", function(callback) {
                that._insertImageDialog(callback);
                return true;
            });
            this.editor.run();
        },
        _insertImageDialog: function(callback) {
            var $container = $('<div/>', {"class": "modal"}),
                availableImages = this.attachmentManager.getAvailableImages(),
                that = this,
                $form,
                $attachmentsUL,
                $attachmentInputs,
                $urlInput,
                aCount = 0,
                i;
            $form = $('<form/>');

            /* make attachment selector */
            if (availableImages.length){
                $attachmentsUL = $('<ul/>', {
                    "class": "markdown-attachment-img-list-insert"
                });
                $.each(availableImages, function(i, el){
                    $attachmentsUL
                        .append($('<li/>')
                            .append($('<a/>', {
                                "class": 'close',
                                "text": el.filename,
                                "href": "#",
                                "click": function() {
                                    callback('attachment:' + el.url);
                                    return true;
                                }
                        })));
                });
                $form
                    .append($('<p/>', {
                        "text": "Add an image attachment: "
                    }))
                    .append($attachmentsUL);
            }

            /* standard url input */
            $urlInput = $('<input/>', {
                "name": "markdown-img-url"
            });
            $form
                .append($('<p/>', {
                    "text": "Add an image by url (e.g. http://example.com/image.jpg *optional title*)"
                }))
                .append($('<div/>')
                    .append($('<label for="markdown-img-url">Url</label>'))
                    .append($urlInput))
                .append($('<input/>', {
                    "type": "submit",
                    "value": "OK"
                }))
                .append($('<input/>', {
                    'type': "button",
                    "value": "Cancel",
                    "class": "close"
                }))
                .submit(function(){
                    callback($urlInput.val());
                    $container.trigger('close');
                    return false;
                });

            $container.append($form);
            $container.lightbox_me({
                centered: true,
                overlayCSS: {
                    position: 'fixed',
                    background: 'black',
                    opacity: .3
                },
                onClose: function () {
                    $('.wmd-prompt-background').remove();
                }
            });

        },
        _help: function(evt, ui){
            return ui.element.trigger("help", evt);
        },
        isScrolledIntoView: function () {
            var docViewTop = $(window).scrollTop(),
                docViewBottom = docViewTop + $(window).height(),
                elemTop = $(this.element).offset().top,
                elemBottom = elemTop + $(this.element).height();

            return ((elemBottom <= docViewBottom) && (elemTop >= docViewTop));
        }
    });

    $('#sidebarmenu-item-markdown-syntax').find('a.nav_child').click(openHelpPanel);

    $('div.markdown-edit')
        .markdownEdit()
        .bind({'help': openHelpPanel});

    $('.markdown-tabs').fadeIn('slow');

}(window));