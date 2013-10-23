/**
 * Client side code for Artifacts
 *
 *
 * @author Tanner
 * @author naba
 */

(function (global) {
    "use strict";

    // Local globals

    var $ = global.$,
        $vf = global.$vf,
        trace = global.trace;

    var ArtifactLink;
    var defaultInfoURL = '/artifact_ref/get_references/';
    var CopyLinkButton;

    if (!$vf) {
        throw {
            name: "MissingRequirement",
            message: "Artifact.js requires vf.js to be loaded first"
        };
    }

    $.fn.makeArtifactLinks = function () {
        this.each(function (i) {
            var el, extras, labelTxt, artifactLink;

            el = $(this);

            extras = el.find('extras').html();
            el.find('extras').remove();
            labelTxt = el.text();

            artifactLink = new ArtifactLink({
                label: labelTxt,
                iconURL: el.attr('data-iconURL'),
                infoURL: el.attr('data-infoURL'),
                extras: extras,
                clickURL: el.attr('data-clickURL'),
                artifactType: el.attr('data-artifactType'),
                containerE: el,
                refId: el.attr('data-refId')
            });
            el.data('artifactLink', artifactLink);

            el.hide();
            el.empty();

            artifactLink.render();

            el.fadeIn(800);
        });
    };

    $(function () {

        // building artifactlinks from pre-pprepared DOM elements

        $('.artifact-link-container').makeArtifactLinks();

    });


    /**
     * ArtifactLink
     *
     * @param config
     */
    ArtifactLink = function (config, labelMaxWidth) {

        /* locals */
        var that = this;

        /* imports & exports */
        this.artifactType = 'generic';   // wiki, ticket, blob, tree etc. generic by defult
        this.label = null;          // will be called on the UI
        this.fullLabel = null;
        this.extras = null;         // html content added after artifact link
        this.infoURL = defaultInfoURL;  // has info button
        this.refId = null;          // referenceId
        this.clickURL = null;       // browser will take user here when artifact is clicked
        this.iconURL = null;        // iconURL, if set will be used instead of artifactType-derived icon
        this.showIcon = true;       // if false, icon will not be rendered
        this.leftTrimmed = false;
        this.shortLink = '';
        this.hideCreateLinkButton = false;
        this.hideInfoIcon = false;

        this.containerE = null;
        this.el = null;
        this.labelE = null;
        this.infoPanel = null;


        /* methods */
        this.render = function () {

            var el,
                iconE,
                infoButtonE,
                extrasE;

            if (!this.containerE) {
                return; // exit early if there is no container to render to
            }

            if (this.el) {
                this.el.remove();
            }

            if (this.clickURL) {
                el = $('<a/>', {
                    "class": 'clickable',
                    href: this.clickURL
                });
            } else {
                el = $('<span/>');
            }
            this.el = el.addClass('artifact-link');
            if (this.artifactType) {
                el.addClass('artifact-link-' + $vf.slugify(this.artifactType));
            }

            if (this.showIcon &&
                ( this.artifactType || this.iconURL )) {

                el.addClass('has-artifact-icon');

                /* render icon */
                iconE = $('<span/>', {
                    'class': 'artifact-icon'
                });

                if (this.iconURL) {

                    // if it has a specific icon, use that

                    switch (this.iconURL) {

                    case 'FILE_TEXT':
                    case 'FILE_IMAGE':
                    case 'FILE_DESIGN_SPACE':

                        iconE.addClass(this.iconURL);

                        break;

                    default:

                        iconE.css('background-image', 'url(' + this.iconURL + ')');

                        break;

                    }


                } else {

                    // we will get the css class for the given artifactType

                    iconE.addClass($vf.slugify(this.artifactType));

                }

                el.append(iconE);

            }

            /* render label */

            this.fullLabel = this.fullLabel || this.label;

            this.labelE = $('<span/>', {
                'text': this.label,
                'class': 'artifact-label',
                'title': this.fullLabel
            });

            if (this.leftTrimmed) {
                this.labelE.addClass('left-trimmed');
            }

            this.labelE.appendTo(el);

            if (!isNaN(labelMaxWidth)) {
                this.labelE.css('max-width', labelMaxWidth + 'px');
            }

            /* render infobutton and initialize tooltip */
            if ( this.infoURL && !this.hideInfoIcon ) {
                el.addClass('has-info-button');

                infoButtonE = $('<span/>', {
                    'class': 'infoButton'
                });

                that.infoPanel = new $vf.ArtifactInfoPanel({
                    parentClickURL: this.clickURL,
                    infoURL: this.infoURL,
                    refId: this.refId,
                    infoTriggerE: infoButtonE,
                    hideCreateLinkButton: this.hideCreateLinkButton
                });

                el.append(infoButtonE);
            }

            if (this.extras) {
                extrasE = $('<div/>', {
                    'class': 'artifact-extras',
                    'html': this.extras,
                    'click': function (e) {
                        e.stopPropagation();
                    }
                });

                el.append(extrasE);
            }

            this.containerE.append(el);
            this.containerE.removeClass('rendering');

            if (this.leftTrimmed) {
                $vf.handleTrimLeft(this.labelE);
            }

        };

        this.remove = function () {

            if (this.el) {
                this.el.remove();
            }

        };

        $.extend(this, config);

    };


    /**
     * ArtifactInfoPanel
     *
     * @param config
     */
    var ArtifactInfoPanel = function (config) {


        // locals
        var that = this,
            relationsInitialized = false,
            relationsE = null,
            relationsListE = null,
            createLinkButton = null,
            relationsMap = {},
            progressBar,
            postRedraw = $.noop;

        // defaults
        config.infoURL = config.infoURL || defaultInfoURL;


        var contentE = this.contentE = $('<div/>', {
            'class': 'infopanel-content'
        });

        if ( !config.embedded ) {
            contentE.append($('<div/>', {
                'class': 'artifact-pleaseWait'
            }));
        }

        if (config.infoTriggerE) {
            config.infoTriggerE.qtip({
                suppress: false,
                content: {
                    text: contentE,
                    ajax: {
                        url: config.infoURL, // URL to the JSON script
                        type: 'GET', // POST or GET
                        data: {artifact_ref: config.refId}, // Data to pass along with your request
                        dataType: 'json', // Tell it we're retrieving JSON
                        success: function (data) {
                            that.render(data);
                            this.render();
                            this.reposition();
                            postRedraw();
                            this.reposition();
                        }
                    }

                },
                position: {
                    at: 'top right', // Position the tooltip above the link
                    my: 'top left',
                    viewport: $(window), // Keep the tooltip on-screen at all times
                    effect: false // Disable positioning animation
                },
                show: {
                    event: 'mouseover',
                    solo: true // Only show one tooltip at a time
                },
                hide: 'unfocus',
                style: {
                    classes: 'ui-tooltip-artifact'
                }

            });
        } else if (config.embedded === true && config.containerE) {

            progressBar = config.containerE.find('progress');

            progressBar.attr('max', 100);
            progressBar.attr('value', 50);

            contentE.appendTo(config.containerE);

            $.ajax({
                url: config.infoURL, // URL to the JSON script
                type: 'GET', // POST or GET
                data: { artifact_ref: config.refId, embedded: true, limit: false }, // Data to pass along with your request
                dataType: 'json', // Tell it we're retrieving JSON
                success: function (data) {
                    progressBar.remove();
                    that.render(data);
                },
                error: function(){
                    progressBar.remove();
                }
            });

        }

        var initRelations = function () {

            var classStr;

            classStr = 'relations';

            if (config.embedded === true) {
                classStr += ' embedded';
            }

            relationsE = $('<div/>', {
                'class': classStr
            });

            contentE.html(relationsE);

            relationsListE = $('<ul/>', {
                'class': 'relations-list'
            });

            relationsInitialized = true;
        };

        this.render = function (data) {

            var instancesListE;
            var addRelation, hasMoreRelations = false;

            if (relationsInitialized === false) {
                initRelations();
            }

            if (data.relations) {

                // these are te columns

                if (config.hideCreateLinkButton) {
                    relationsE.addClass('noCreateLinkButton');
                }

                // Call-out version

                relationsE.append(relationsListE);

                addRelation = function (relation) {
                    var relationE, mountPointE, iconE;

                    relationE = $('<li/>', {
                        'class': 'column'
                    });

                    mountPointE = $('<div/>', {
                        'text': relation.label +
                            (relation.count ? '[' + relation.count + ']' : ''),
                        'class': 'mount-point-label'
                    });

                    /* render icon */

                    iconE = $('<span/>', {
                        'class': 'artifact-icon mount-point-icon'
                    });

                    mountPointE.prepend(iconE);

                    if (relation.tool_name) {
                        iconE.addClass(relation.tool_name);
                    }

                    if (relation.createURL) {
                        mountPointE.append($('<a/>', {
                            'class': 'relation-create-button',
                            text: '+',
                            'href': relation.createURL + '?artifact_ref=' + encodeURIComponent(config.refId),
                            title: 'Create new',
                            target: '_top'
                        }));
                    }

                    relationE.append(mountPointE);
                    relationsListE.append(relationE);

                    return relationE;
                };

                // Render Each tool

                $.each(data.relations, function (i, relation) {

                    if (relation.instances) {

                        if (!relationsMap[relation.label]) {
                            relationsMap[relation.label] = addRelation(relation);
                        }

                        //if (relation.instances.length) {

                            if ( config.embedded ) {
                                instancesListE = $('<div/>', {
                                    'class': 'instances-list'
                                });
                            } else {
                                instancesListE = $('<ul/>', {
                                    'class': 'instances-list'
                                });
                            }

                            relationsMap[relation.label].append(instancesListE);
                        //}

                        hasMoreRelations = hasMoreRelations ||
                            (relation.count &&
                                relation.count > relation.instances.length);


                        var linkList, itIsRepo = [ 'Git', 'SVN' ].indexOf( relation.tool_name ) !== -1,
                                labelMaxWidth;

                        if (config.embedded) {

                            if ( relation.instances && relation.instances.length ) {

                                if (itIsRepo) {
                                    labelMaxWidth = 95;
                                } else {
                                    labelMaxWidth = 105;
                                }

                                linkList = new $vf.ArtifactLinkList({
                                    containerE: instancesListE,
                                    referenceDescriptors: relation.instances,
                                    editable: false,
                                    hideCreateLinkButton: true,
                                    hideInfoIcon: true,
                                    showIcon: itIsRepo,
                                    labelMaxWidth: labelMaxWidth
                                });

                                linkList.render();

                            } else {

                                instancesListE.append($('<div/>', {
                                    'text': 'No references',
                                    'class': 'noReferences'
                                }));

                            }

                        } else {

                            $.each(relation.instances, function (j, relationInstance) {

                                var instanceE = $('<li/>', {
                                    text: relationInstance[0],
                                    title: relationInstance[0],
                                    click: function () {
                                        top.location.href =
                                            relationInstance[1];
                                    }
                                });

                                instancesListE.append(instanceE);

                            });

                        }


                    }

                });

                if (hasMoreRelations && config.parentClickURL) {
                    relationsListE.after($('<div/>', {
                        html: 'Show more relations &raquo;',
                        click: function () {
                            top.location.href = config.parentClickURL;
                        },
                        'class': 'show-more',
                        title: 'Show all relationships'
                    }));
                }


            }

            // Create Link

            if (data.shortLink && config.hideCreateLinkButton !== true && $vf.referenceBin) {
                createLinkButton = new CopyLinkButton({
                    containerE: contentE,
                    refId: config.refId
                });
            }


            // Remove Loading spin

            if (data.loading) {

                $('<div/>', {
                    "class": "references-loading",
                    "text": "Loading..."
                }).appendTo(contentE);
            } else {
                contentE.find('.references-loading').remove();
            }

            if ( config.embedded ) {
                config.containerE.prepend($('<h4>Related</h4>'));
            }

            // preview image

            if ( data.preview ) {

                var previewE = $('<div/>', {
                    'class': 'preview'
                });

                previewE.append($( '<h4/>', {
                    'text': 'Preview'
                }));

                var imgE = $('<img/>', {
                    "class": 'preview-image'
                });

                imgE.load(function() {
                    trace( 'img loaded - redrawing');
                    if (config.infoTriggerE) {
                        config.infoTriggerE.qtip('reposition');
                    }
                });

                imgE.attr('src', data.preview);

                if (config.infoTriggerE){
                    imgE.css('display', 'none');
                        postRedraw = function(){
                        //imgE.attr('width', contentE.width()); Does not work well with small images
                        imgE.css('display', 'inline');
                    };
                } else{
                    //imgE.attr('width', contentE.width()); //seems to be causing preview images grow giant on XCNG  pages
                }

                previewE.append( imgE );

                if (that.clickURL) {

                    previewE.addClass( 'clickable' );

                    previewE.attr( 'title', 'Click to open' );

                    previewE.click( function() {
                        top.location.href = data.preview;
                    });
                }

                contentE.append( previewE );

            }

        };


    };

    CopyLinkButton = function (config) {

        var buttonE;

        if (config.containerE) {

            buttonE = $('<div/>', {

                'class': 'copyLinkButton',
                'title': 'Add to Link Bin',
                click: function () {

                    if ($vf.referenceBin) {
                        $vf.referenceBin.addReference(config.refId);
                    }

                }

            });

            config.containerE.append(buttonE);

        }

    };


    /**
     * List of ArtifactLinks
     *
     * @class
     * @param config
     */
    var ArtifactLinkList = function (config) {

        trace('ArtifactLinkList created...');

        var that = this;
        var liE, artifactLink, artifactLinkList, removeE;

        var listE = this.listE = $('<div/>', {
            'class': 'artifactLinkList'
        });

        this.referenceDescriptors = config.referenceDescriptors;

        this.length = 0;

        this.render = function (silent) {

            if (config.containerE) {

                artifactLinkList = artifactLinkList || {};

                this.empty();

                config.containerE.append(listE);

                if ($.isArray(this.referenceDescriptors) || this.referenceDescriptors.length) {

                    $.each(this.referenceDescriptors, function (i, e) {

                        that.addLinkByDescriptor(e, silent);

                    });

                }

            }

        };

        this.addLinkByDescriptor = function (descriptor, silent) {

            var messagesEl;

            artifactLinkList = artifactLinkList || {};

            if (config.maxLength !== undefined && this.length >= config.maxLength) {

                // Here we drop error message

                messagesEl = $("#messages");
                messagesEl.notify('Link Bin is full. [' + descriptor.label + '] can not be added.', {
                        status: 'error',
                        timer: 4000
                    }
                );

                return false;

            }

            if (artifactLinkList[ descriptor.refId ] === undefined) {

                liE = $('<div/>', {
                    'class': 'artifactLinkListElement'
                });

                listE.append(liE);

                if (config.editable) {

                    liE.draggable({

                        cursor: 'move',
                        revert: true,
                        containment: 'document',
                        appendTo: 'body',
                        helper: 'clone',
                        zIndex: 15000,
                        revertDuration: 250,
                        opacity: 0.7,
                        scroll: true,

                        start: function (event, ui) {
                            // FIXING Chrome specific offset bug
                            if(! $.browser.chrome) ui.position.top -= $(window).scrollTop();

                            // making textareas link-droppable

                            var textareaAction = function (artifactLink) {

                                $(this).insertAtCaret(artifactLink.shortLink);

                            };

                            $('.markdown-edit textarea').each(function () {

                                $(this).artifactLinkDroppable(textareaAction);

                            });

                        },
                        // FIXING Chrome specific offset bug
                        drag: function(event, ui) {
                            if(! $.browser.chrome) ui.position.top -= $(window).scrollTop();
                        }

                    });

                }

                artifactLink = new ArtifactLink(descriptor, config.labelMaxWidth);

                // passing some settings over to ArtifactLink instance
                artifactLink.containerE = liE;
                artifactLink.hideCreateLinkButton = config.hideCreateLinkButton;
                artifactLink.hideInfoIcon = config.hideInfoIcon;

                if ( config.showIcon === false ) {
                    artifactLink.showIcon = false;
                }

                if ( config.leftTrimmed ) {
                    artifactLink.leftTrimmed = true;
                }

                artifactLink.render();

                artifactLinkList[ descriptor.refId ] = artifactLink;

                var handlerFactory = function (id) {
                    return function () {
                        that.removeLinkByRefId(id);
                    };
                };

                liE.data('host', artifactLink);

                if (config.editable) {

                    removeE = $('<span/>', {
                        'class': 'linkRemoveButton',
                        'text': 'X',
                        'title': 'Remove Link',
                        click: handlerFactory(descriptor.refId)
                    });

                    liE.append(removeE);
                }

                this.length += 1;

                if ($.isFunction(config.on_linkAdd) && silent !== true) {
                    config.on_linkAdd.call(that, descriptor.refId);
                }

            } else {

                // Already in bin. Display error message.

                messagesEl = $("#messages");
                messagesEl.notify('[' + descriptor.label + '] is already in Link Bin.', {
                        status: 'error',
                        timer: 4000
                    }
                );

                return false;

            }

        };

        this.empty = function() {

            $.each(artifactLinkList, function (i, e) {
                artifactLink = artifactLinkList[ i ];

                if (artifactLink) {

                    liE = artifactLink.containerE;

                    artifactLink.remove();

                    liE.remove();

                    delete artifactLinkList[ i ];

                }

            });

            this.length = 0;
            artifactLinkList = {};

        };

        this.removeLinkByRefId = function (refId, silent) {

            artifactLink = artifactLinkList[ refId ];

            if (artifactLink) {

                liE = artifactLink.containerE;

                artifactLink.remove();

                liE.remove();

                delete artifactLinkList[ refId ];

                this.length -= 1;

                if ($.isFunction(config.on_linkRemove) && silent !== true) {
                    config.on_linkRemove.call(that, refId);
                }

            }

        };

    };


    // Public interface

    /**
     * Use this jQuery plugin to make a DOM element accept artifactLinks.
     *
     *
     * @param action Called when the drop action is done. It gets the dropped link as first parameter.
     * @param types List of artifact types which target accepts or undefined for all types.
     */
    $.fn.artifactLinkDroppable = function (action, types) {

        var that = this, artifactLink;

        this.droppable({

            accept: function (draggable) {

                artifactLink = draggable.data('host');

                return ( types === undefined || ( artifactLink && types.indexOf(artifactLink.artifactType) !== -1 ) );

            },

            drop: function (event, ui) {

                artifactLink = ui.draggable.data('host');

                ui.helper.css( 'cursor', ui.helper.data( 'cursorBefore'));

                action.call(that, artifactLink);

            },

            over: function (event, ui) {

                ui.helper.data( 'cursorBefore', ui.helper.css( 'cursor') );
                ui.helper.css( 'cursor', 'copy');

            },

            out: function (event, ui) {

                ui.helper.css( 'cursor', ui.helper.data( 'cursorBefore') );

            },

            activeClass: 'will-eat-artifactlink',
            hoverClass: 'ready-for-artifactlink'

        });

    };

    /**
     * Use this jQuery plugin to make a DOM element NOT to accept artifactLinks.
     *
     */
    $.fn.unregisterLinkDroppable = function () {
        this.droppable("destroy");
    };


    $vf.ArtifactLink = ArtifactLink;
    $vf.ArtifactInfoPanel = ArtifactInfoPanel;
    $vf.ArtifactLinkList = ArtifactLinkList;

}(window));
