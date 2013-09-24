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
                    var filename = $(this).attr('data-filename'),
                        mimetype = $(this).attr('data-mimetype');
                    that.attachments[filename] = {
                        is_image: mimetype.match(/image.*/),
                        $el: $(this)
                    };
                    that.attachments[filename].url = $(this).attr('data-url') ? $(this).attr('data-url') : null;
                });
            }
        }

        function parseUploadFields(){
            that.uploadAttachments = {};
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
            if (this.uploadAttachments.hasOwnProperty(decodeURIComponent(filename))){
                att = this.uploadAttachments[decodeURIComponent(filename)];
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
                if (this.attachments.hasOwnProperty(fname) && this.attachments[fname]['is_image']){
                    available.push({
                        filename: fname,
                        url: this.attachments[fname].url
                    });
                }
            }
            this.parseUploadFields();
            for (fname in this.uploadAttachments){
                if (this.uploadAttachments.hasOwnProperty(fname) && this.uploadAttachments[fname]['is_image']){
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
            attachmentManager: null,
            previewHeight: null
        },
        _create: function() {
            var that = this;
            this.element.find('.markdown-help-button').click(function(evt){
                return that._help(evt, that);
            });
            this.$textarea = this.element.find('textarea');
            this.$textarea.tabby({tabString : "    "});
            this.context_id = this.element.attr("data-context-id");
            that.$preview = this.element.find('#wmd-preview-' + this.context_id);
            if (that.$preview){
                if (this.options.previewHeight === 'auto'){
                    this.$textarea.resize(function(){
                        that.$preview.height(that.$textarea.height());
                    });
                    this.$textarea.resize();
                } else if (this.options.previewHeight) {
                    that.$preview.height(this.options.previewHeight);
                } else {
                    that.$preview.css('min-height', that.$textarea.height());
                }
            }
            this.attachmentManager = this.options.attachmentManager;
            if (this.attachmentManager === null){
                this._setupAttachmentManager();
            }

            this.converter = this.options.converter;
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
            this.converter = Markdown.getSanitizingConverter();

            /* add wrapper */
            this.converter.hooks.chain("postConversion", function(text){
                return '<div class="markdown_content">' + text + '</div>';
            });

            /* prettyprint code plugin */
            this.converter.hooks.chain("postConversion", function(text){
                var rePattern = /<pre><code>([^<]+)<\/code><\/pre>/gm;
                return text.replace(rePattern, function(whole, inner){
                    return '<pre><code class="prettyprint">'+ prettyPrintOne(inner) + '</code></pre>';
                });
            });

            /* custom img tag */
            this.converter.hooks.chain("postSpanGamut", function(text){
                var rePattern = /\[\[(img[^\]]+src="?([^"\s]+)"?[^\]]+)\]\]/g;
                return text.replace(rePattern, function (whole, attributes, src) {
                    if (! /[A-z]:\/\//.test(src)){  // if not absolute
                        attributes = attributes.replace(src, that.attachmentManager.getLocalUrlforFilename(src));
                    }
                    return '<' + attributes + '/>';
                });
            });

            /* shortlink conversion */
            this.converter.hooks.chain("postSpanGamut", function(text){
                var rePattern = /(\[)?\[([^\]\[]+)\]/g;
                return text.replace(rePattern, function (whole, extraBracket0, shortLink) {
                    if (extraBracket0){
                        return whole;
                    }
                    return '<a href="##" class="shortlink-placeholder">' + whole + '</a>';
                });
            });

            /* oembed */
            this.converter.hooks.chain("preSpanGamut", function(text){
                var rePattern = /!\[([^\]]+)\]\((https?:\/\/[^\)]+)(png|jpg|jpeg|gif)?\)/g;
                return text.replace(rePattern, function (whole, altText, url, imgExt) {
                    if (imgExt){
                        return whole;
                    } else {
                        return '<div class="markdownPlaceholder oembedPlaceholder">'
                            + '<p>Video at ' + url + ' will be rendered here</p>'
                            + '</div>';
                    }
                });
            });

            /* embedded visualization */
            this.converter.hooks.chain("preSpanGamut", function(text){
                var rePattern = /\^v\(([^\)]+)\)(?:\(([^\)]*)\))?/g;
                return text.replace(rePattern, function (whole, resourceUrl, props) {
                    return '<div class="markdownPlaceholder visualizerPlaceholder">' +
                        '<p>Visualizer for ' + resourceUrl + ' will be embedded here...</p>' +
                        '</div>';
                });
            });

            /* include */
            this.converter.hooks.chain("preSpanGamut", function(text){
                var rePattern = /\[\[include +ref="?([^\]"]+)"?\]\]/g;
                return text.replace(rePattern, function (whole, pageName) {
                    return '<div class="markdownPlaceholder wikiPlaceholder">' +
                        '<p>Contents of *' + pageName + '* will be rendered here...</p>' +
                        '</div>';
                });
            });

            /* fenced code */
            this.converter.hooks.chain("preBlockGamut", function(text, runBlockGamut) {
                var rePattern = /^ {0,3}~T~T~T~T *\n((?:.*?\n)+?) {0,3}~T~T~T~T *$/gm;
                return text.replace(rePattern, function(whole, inner){
                    var indented = $.map(inner.split('\n'), function(line){
                        return '    ' + line;
                    }).join('\n');
                    return indented;
                });
            });

            /* read more */
            this.converter.hooks.chain("preBlockGamut", function(text, runBlockGamut) {
                var rePattern = /^ {0,3}\/\/(.*)(\n\n)?/gm;
                return text.replace(rePattern, function(whole, inner){
                     return '<div class="md-read-more">' + runBlockGamut(inner) + '</div>';
                });
            });

            /* comments */
            this.converter.hooks.chain("preSpanGamut", function(text){
                var rePattern = /\/\*.*?\*\//g;
                return text.replace(rePattern, '');
            });
            this.converter.hooks.chain("preBlockGamut", function(text, runBlockGamut) {
                var rePattern = /\/\*(?:.*?\n?)*?\*\//gm;
                return text.replace(rePattern, '');
            });

            /* tables */
            var leadingPipe = new RegExp(
                  ['^'                         ,
                   '[ ]{0,3}'                  , // Allowed whitespace
                   '[|]'                       , // Initial pipe
                   '(.+)\\n'                   , // $1: Header Row

                   '[ ]{0,3}'                  , // Allowed whitespace
                   '[|]([ ]*[-:]+[-| :]*)\\n'  , // $2: Separator

                   '('                         , // $3: Table Body
                     '(?:[ ]*[|].*\\n?)*'      , // Table rows
                   ')',
                   '(?:\\n|$)'                   // Stop at final newline
                  ].join(''),
                  'gm'
                );

            var noLeadingPipe = new RegExp(
                ['^'                         ,
                '[ ]{0,3}'                  , // Allowed whitespace
                '(\\S.*[|].*)\\n'           , // $1: Header Row

                '[ ]{0,3}'                  , // Allowed whitespace
                '([-:]+[ ]*[|][-| :]*)\\n'  , // $2: Separator

                '('                         , // $3: Table Body
                 '(?:.*[|].*\\n?)*'        , // Table rows
                ')'                         ,
                '(?:\\n|$)'                   // Stop at final newline
                ].join(''),
                'gm'
            );
            this.converter.hooks.chain("preBlockGamut", function(text, runBlockGamut){

                text = text.replace(leadingPipe, doTable);
                text = text.replace(noLeadingPipe, doTable);

                function trim(str) {
                    return str.replace(/^\s+|\s+$/g, '');
                }

                // $1 = header, $2 = separator, $3 = body
                function doTable(match, header, separator, body, offset, string) {
                    var alignspecs, align = [];
                    // remove any leading pipes and whitespace
                    header = header.replace(/^ *[|]/m, '');
                    separator = separator.replace(/^ *[|]/m, '');
                    body = body.replace(/^ *[|]/gm, '');

                    // remove trailing pipes and whitespace
                    header = header.replace(/[|] *$/m, '');
                    separator = separator.replace(/[|] *$/m, '');
                    body = body.replace(/[|] *$/gm, '');

                    // determine column alignments
                    alignspecs = separator.split(/ *[|] */);
                    for (var i = 0; i < alignspecs.length; i++) {
                    var spec = alignspecs[i];
                    if (spec.match(/^ *-+: *$/m))
                        align[i] = ' style="text-align:right;"';
                    else if (spec.match(/^ *:-+: *$/m))
                        align[i] = ' style="text-align:center;"';
                    else if (spec.match(/^ *:-+ *$/m))
                        align[i] = ' style="text-align:left;"';
                    else align[i] = '';
                    }

                    // TODO: parse spans in header and rows before splitting, so that pipes
                    // inside of tags are not interpreted as separators
                    var headers = header.split(/ *[|] */);
                    var colCount = headers.length;

                    // build html
                    var html = ['<table>\n', '<thead>\n', '<tr>\n'].join('');

                    // build column headers.
                    for (i = 0; i < colCount; i++) {
                    var headerHtml = that.converter.hooks.postSpanGamut(trim(headers[i]));
                    html += ["  <th", align[i], ">", headerHtml, "</th>\n"].join('');
                    }
                    html += "</tr>\n</thead>\n";

                    // build rows
                    var rows = body.split('\n');
                    for (i = 0; i < rows.length; i++) {
                        if (rows[i].match(/^\s*$/)) // can apply to final row
                            continue;

                        // ensure number of rowCells matches colCount
                        var rowCells = rows[i].split(/ *[|] */);
                        var lenDiff = colCount - rowCells.length;
                        for (var j = 0; j < lenDiff; j++)
                            rowCells.push('');

                        html += "<tr>\n";
                        for (j = 0; j < colCount; j++) {
                            var colHtml = that.converter.hooks.postSpanGamut(trim(rowCells[j]));
                            html += ["  <td", align[j], ">", colHtml, "</td>\n"].join('');
                        }
                        html += "</tr>\n";
                    }

                    html += "</table>\n";

                    return html;
                }

                return text;
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
            var $container = $('<div/>', {"class": "modal markdown-img-container"}),
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
                .append($('<div/>', {"class": "markdown-img-add-btn-row"})
                    .append($('<input/>', {
                        "type": "submit",
                        "value": "OK"
                    }))
                    .append($('<input/>', {
                        'type': "button",
                        "value": "Cancel",
                        "class": "close"
                    })))
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
