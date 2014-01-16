/*
 *  @author Naba Bana
 *
 *  Workspace infrastructure for VF.
 *
 */

(function ($vf, $) {
    "use strict";

    if (!$vf) {
        throw {
            name: "MissingRequirement",
            message: "Tutorial.js requires vf.js to be loaded first"
        };
    }

    /**
     *
     * Tutorial
     *
     */
    $vf.Tutorial = function (options) {
        var that = this;

        $.extend(this, options);

        that.pageId = that.pageId || document.location.pathname;

        if ( this.statePersistenceApiUrl ) {

            // adding key to make up the good URI
            this.statePersistenceApiUrl += 'hidden_tutorials';
            if ( that.enabled === undefined ) {
                // Try to get state from service if it is undefined (not preset)

                $.ajax({
                    url: that.statePersistenceApiUrl,
                    headers: { "VF_SESSION_ID": $.cookie( '_session_id' ) },
                    success: function ( data ) {
                        that.enabled =
                            !(data && data[ that.pageId ] === 'hidden');
                    },
                    error: function (data) {
                        that.enabled = true;

                    },
                    complete: function () {
                        that.render();
                    }
                });
            }
        }

    };

    $vf.Tutorial.prototype = {

        containerElement: null,

        title: null,
        description: null,

        pageId: null,

        elements: null,

        toolTipped: null,

        enabled: undefined,

        statePersistenceApiUrl: null,

        toggle: function () {
            return this.enabled ? this.disable() : this.enable();
        },

        enable: function () {
            var that = this;
            this.enabled = true;
            $.each(this.toolTipped, function (i, e) {
                e.qtip('enable');
            });
            this.containerElement.
                clearQueue().
                animate({
                    opacity: 'show',
                    height: 'show'
                });
            this.buttonContainerElement.
                removeClass('tutorial-off').
                addClass('tutorial-on');
            this.buttonElement.
                qtip('set', 'content.text', 'Hide interface tips');
        },

        disable: function () {
            var that = this;
            this.enabled = false;
            $.each(this.toolTipped, function (i, e) {
                e.removeClass('tutorialHilite');
                e.qtip('disable');
            });
            this.containerElement.
                clearQueue().
                animate({
                    opacity: 'hide',
                    height: 'hide'
                });
            this.buttonContainerElement.
                addClass('tutorial-off').
                removeClass('tutorial-on');
            this.buttonElement.
                qtip('set', 'content.text', 'Show interface tips');
        },

        highlightAll: function (e) {
            if (this.enabled) {
                $.each(this.toolTipped, function (i, e) {
                    e.addClass('tutorialHilite');
                });
            }
        },

        highlightNone: function (e) {
            if (this.enabled) {
                $.each(this.toolTipped, function (i, e) {
                    e.removeClass('tutorialHilite');
                });
            }
        },

        persistState: function() {

            var that = this,
                preference;

            if ( that.statePersistenceApiUrl && that.pageId ) {

                $.ajax({
                    url: that.statePersistenceApiUrl,
                    headers: { "VF_SESSION_ID": $.cookie( '_session_id' ) },
                    success: function ( data ) {
                        preference = data;
                    },

                    error: function () {
                        preference = {};
                    },
                    complete: function () {

                        if (that.enabled) {
                            delete preference[ that.pageId ];
                        } else {
                            preference[ that.pageId ] = 'hidden';
                        }

                        $.ajax({
                            type: "POST",
                            url: that.statePersistenceApiUrl,
                            headers: { "VF_SESSION_ID": $.cookie( '_session_id' ) },
                            data: preference
                        });
                    }

                });

            }
        },

        render: function () {
            var that = this, containerElement, linerElement,
                elements, toolTipped;

            containerElement = this.containerElement;
            elements = this.elements;

            if (containerElement) {

                toolTipped = this.toolTipped = [];

                if (elements) {
                    $.each(elements, function (i, element) {
                        var hE, pos;

                        hE = $(i);

                        if (hE) {
                            switch (element.position) {
                            case 'top':
                                pos = {
                                    my: 'bottom center',
                                    at: 'top center'
                                };
                                break;
                            case 'right':
                                pos = {
                                    my: 'left center',
                                    at: 'right center'
                                };
                                break;
                            case 'left':
                                pos = {
                                    my: 'right center',
                                    at: 'left center'
                                };
                                break;
                            case 'center':
                                pos = {
                                    my: 'bottom center',
                                    at: 'center center'
                                };
                                break;
                            default:
                                /** includes case 'bottom' */
                                pos = {
                                    my: 'top center',
                                    at: 'bottom center'
                                };
                                break;
                            }

                            hE.qtip({
                                content: {
                                    title: element.title,
                                    text: element.content.replace(/%%UC%%/g,
                                        '<div class="uC">' +
                                            '<span class="inner">' +
                                            'Under development' +
                                            '</span>' +
                                            '</div>')

                                },
                                position: pos,
                                style: {
                                    classes: 'vf-tutorial-tip'
                                }
                            }).hover(
                                function () {
                                    if (that.enabled) {
                                        hE.addClass('tutorialHilite');
                                    }
                                },
                                function () {
                                    hE.removeClass('tutorialHilite');
                                }
                            );

                            toolTipped.push(hE);
                        }
                    });
                }

                containerElement.
                    addClass('tutorial').
                    hide();

                this.highlightTrigger = this.highlightTrigger || containerElement;

                this.highlightTrigger.
                    bind('mouseenter', $.proxy(this.highlightAll, this)).
                    bind('mouseleave', $.proxy(this.highlightNone, this));

                linerElement = $('<div/>').appendTo(containerElement);

                if (this.title) {

                    this.titleElement = $('<div/>', {
                        text: this.title || ''
                    }).
                        addClass('title').
                        appendTo(linerElement);
                }

                this.descriptionElement = $('<div/>', {
                    html:  ''
                }).
                    addClass('tutorial-description').
                    appendTo(linerElement);

                if ( this.description instanceof jQuery ) {
                    this.description.appendTo(this.descriptionElement);
                    this.description.show();
                } else if (typeof this.description == 'string') {
                    this.descriptionElement.html( this.description );
                    this.descriptionElement.addClass('pure');
                }

                this.disableElement = $('<a/>', {
                    text: "hide tips",
                    'class': "has-icon ico-play_up"
                }).
                    addClass('close').
                    bind('click', function() {
                        that.disable();
                        that.persistState();
                    } ).
                    appendTo(linerElement);


                this.buttonContainerElement = $('<div/>').
                    addClass('tutorial-button-container').
                    appendTo($('#header-wrapper'));

                this.buttonElement = $('<div/>').
                    addClass('tutorial-button').
                    bind('click', function() {
                        that.toggle();
                        that.persistState();
                    }).
                    appendTo(this.buttonContainerElement).
                    qtip({
                        content: {
                            text: "Show interface tips"
                        },
                        position: {
                            my: 'top center',
                            at: 'bottom center'
                        },
                        style: {
                            classes: 'vf-tutorial-tip'
                        }
                    });
/*
                this.buttonIconElement = $('<div/>').
                    addClass('tutorial-button-icon').
                    addClass('inline-icon').
                    addClass('ico-info').
                    appendTo(this.buttonElement);*/

                this.buttonLabelElement = $('<span/>', {text: 'User Tips'}).
                    addClass('tutorial-button-label').
                    appendTo(this.buttonElement);

                if (this.enabled === true) {
                    this.enable();
                } else {
                    this.disable();
                }
            }
        }

    };

}(window.$vf, window.jQuery));
