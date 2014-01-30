(function ($) {
    'use strict';

    var ENABLE_DEBUG_GIZMOS = false;

    $.fn.dragScroll = function () {
        return this.each(function () {
            var that = $(this),
                scrolling = false,
                scrollX = null,
                scrollY = null,
                clickX = null,
                clickY = null,
                startScrolling,
                stopScrolling,
                updateScrolling;

            startScrolling = function (e) {
                scrolling = true;
                scrollX = that.scrollLeft();
                scrollY = that.scrollTop();
                clickX = e.pageX;
                clickY = e.pageY;
            };

            stopScrolling = function () {
                scrolling = false;
                scrollX = null;
                scrollY = null;
                clickX = null;
                clickY = null;
            };

            updateScrolling = function (e) {
                if (scrolling) {
                    that.scrollLeft(scrollX + (clickX - e.pageX));
                    that.scrollTop(scrollY + (clickY - e.pageY));
                }
            };

            $(this).bind({
                'mousedown': startScrolling,
                'mouseup': stopScrolling,
                'mousemove': updateScrolling,
                'mouseleave': stopScrolling
            });
        });
    };

    $.widget('vf_vis.image', {

        options: {
            minImageDimension: 32,
            maxScale: 8
        },

        _create: function () {
            var that = this;

            this._offsetX = 0;
            this._offsetY = 0;
            this._centerX = 0;
            this._centerY = 0;
            this._minScale = 0.1;

            // structure
            this.$image = this.element;

            this.$container = $('<div/>').
                addClass('container').
                insertBefore(this.element);

            this.$imageWrapper = $('<div/>').
                addClass('image-wrapper').
                appendTo(this.$container);

            this.$image.
                addClass('image').
                appendTo(this.$imageWrapper);

            if (ENABLE_DEBUG_GIZMOS) {
                this.$unscaledImageMarker = $('<div/>').
                    addClass('unscaledImageMarker').
                    appendTo(this.$imageWrapper);
                this.$transformOriginMarker = $('<div/>').
                    addClass('transformOriginMarker').
                    appendTo(this.$imageWrapper);
            }

            this.$overlay = $('<div/>').
                addClass('overlay').
                appendTo(this.$container);

            this.$panel = $('<div/>').
                appendTo(this.$container).
                addClass('panel').
                css('opacity', 0);

            this.$zoomOut = $('<button/>').
                appendTo(this.$panel).
                text('-');

            this.$zoomIn = $('<button/>').
                appendTo(this.$panel).
                text('+');

            this.$zoomFit = $('<button/>').
                appendTo(this.$panel).
                text('fit');

            this.$zoomActual = $('<button/>').
                appendTo(this.$panel).
                text('100%');

            // events
            this.$panel.on('mousedown', function (e) {
                e.stopPropagation();
            });
            this.$zoomOut.bind('click', function (e) {
                that.zoomOut.call(that);
                e.stopPropagation();
                e.preventDefault();
            });
            this.$zoomIn.bind('click', function (e) {
                that.zoomIn.call(that);
                e.stopPropagation();
                e.preventDefault();
            });
            this.$zoomFit.bind('click', function (e) {
                that.setScale.call(that, 'fit');
                that.center.call(that);
                e.stopPropagation();
                e.preventDefault();
            });
            this.$zoomActual.bind('click', function (e) {
                that.setScale.call(that, 1);
                that.center.call(that);
                e.stopPropagation();
                e.preventDefault();
            });

            // bind events
            this.$image.on({
                'load': function () {
                    // initialize
                    that._nativeWidth = that.$image.width();
                    that._nativeHeight = that.$image.height();
                    that._nativeRatio = that._nativeWidth / that._nativeHeight;
                    if (that._nativeRatio >= 1) {  // landscape
                        that._minScale = that.options.minImageDimension / that._nativeHeight;
                    } else {  // portrait
                        that._minScale = that.options.minImageDimension / that._nativeWidth;
                    }
                    if (that._nativeWidth > that.$container.width() || that._nativeHeight > that.$container.height()) {
                        that.setScale.call(that, 'fit');
                    } else {
                        that.setScale.call(that, 1);
                    }
                    that.$panel.css('opacity', 1);
                    that.$image.css('opacity', 1);
                    that.center.call(that);
                    if (ENABLE_DEBUG_GIZMOS) {
                        that.$unscaledImageMarker.css({
                            width: that._nativeWidth,
                            height: that._nativeHeight
                        });
                    }
                },
                'click': function (e) {
                    e.preventDefault();
                },
                'mousedown': function (e) {
                    e.preventDefault();
                }
            });
            if (this.$image.prop("complete")){
                this.$image.trigger('load');
            }
            $(document).
                on('mousedown', function (e) {
                    var startingPageX, startingPageY,
                        startingOffsetX, startingOffsetY,
                        originalTransitions, placeholderTransition;
                    if (e.which !== 1) {
                        return;
                    }
                    startingPageX = e.pageX;
                    startingPageY = e.pageY;
                    startingOffsetX = that._offsetX;
                    startingOffsetY = that._offsetY;
                    // unbind transition
                    originalTransitions = {
                        "WebkitTransition": that.$image.css("WebkitTransition"),
                        "MozTransition": that.$image.css("MozTransition"),
                        "msTransition": that.$image.css("msTransition"),
                        "OTransition": that.$image.css("OTransition"),
                        "transition": that.$image.css("transition")
                    };
                    placeholderTransition = 'initial';
                    that.$image.css({
                        "WebkitTransition": placeholderTransition,
                        "MozTransition": placeholderTransition,
                        "msTransition": placeholderTransition,
                        "OTransition": placeholderTransition,
                        "transition": placeholderTransition
                    });
                    $(document).on('mouseup mousemove mouseleave unfocus', function handler(e) {
                        var x, y;
                        if (e.type === 'mousemove') {
                            // scale move
                            x = startingOffsetX - (startingPageX - e.pageX) / that._scale;
                            y = startingOffsetY - (startingPageY - e.pageY) / that._scale;
                            that.moveTo.call(that, x, y);
                        } else {
                            $(document).off('mouseup mousemove', handler);
                            // rebind stylesheet transitions
                            that.$image.css(originalTransitions);
                        }
                    });
                });
            $(window).
                bind('mousewheel wheel ', function (e) {
                    //var delta = e.originalEvent.deltaY/400.0;
                    var delta, f, o = e.originalEvent,
                    d = o.deltaY, w = o.wheelDelta,
                    n = 225, n1 = n- 1;

                    // Normalize delta
                    d = d ? w && (f = w/d) ? d/f : -d/1.35 : w/120;
                    // Quadratic scale if |d| > 1
                    d = d < 1 ? d < -1 ? (-Math.pow(d, 2) - n1) / n : d : (Math.pow(d, 2) + n1) / n;
                    // Delta *should* not be greater than 2...
                    delta = Math.min(Math.max(d / 2, -1), 1);
                    that.setScale(that._scale * (1 + delta));
                });

        },


        zoomIn: function () {
            this.setScale(this._scale * 1.1);
        },
        zoomOut: function () {
            this.setScale(this._scale * 0.9);
        },
        center: function () {
            var x, y;
            x = (this.$container.width() - this._nativeWidth) / 2;
            y = (this.$container.height() - this._nativeHeight) / 2;
            this.moveTo(x, y);
        },


        setScale: function (scale) {
            var newTransform;
            // scale is either a decimal number or the word 'fit'
            if (scale === 'fit') {
                if (this.$container.width() / this.$container.height() >= this._nativeRatio) {
                    this._scale = this.$container.height() / this._nativeHeight;
                } else {
                    this._scale = this.$container.width() / this._nativeWidth;
                }
            } else {
                this._scale = Math.min(this.options.maxScale, Math.max(this._minScale, scale));
            }
            newTransform = 'scale(' + this._scale + ')';
            this.$image.css({
                "WebkitTransform": newTransform,
                "MozTransform": newTransform,
                "msTransform": newTransform,
                "OTransform": newTransform,
                "transform": newTransform
            });
        },
        moveTo: function (x, y) {
            var newWrapperTransform, newImageTransformOrigin, originX, originY;
            this._offsetX = x;
            this._offsetY = y;
            newWrapperTransform = 'translate(' + x + 'px, ' + y + 'px)';
            this.$imageWrapper.css({
                "WebkitTransform": newWrapperTransform,
                "MozTransform": newWrapperTransform,
                "msTransform": newWrapperTransform,
                "OTransform": newWrapperTransform,
                "transform": newWrapperTransform
            });
            originX = this.$container.width() / 2 - x;
            originY = this.$container.height() / 2 - y;
            if (ENABLE_DEBUG_GIZMOS) {
                this.$transformOriginMarker.css({
                    top: originY + 'px',
                    left: originX + 'px'
                });
            }
            newImageTransformOrigin = originX + 'px ' + originY + 'px';
            this.$image.css({
                "WebkitTransformOrigin": newImageTransformOrigin,
                "MozTransformOrigin": newImageTransformOrigin,
                "msTransformOrigin": newImageTransformOrigin,
                "OTransformOrigin": newImageTransformOrigin,
                "transform-origin": newImageTransformOrigin
            });
        }
    });

    $(function () {
        $('#image').image();
    });

}(window.jQuery));
