(function ($) {
    'use strict';

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

        options: {},

        _create: function () {
            var that = this;

            // structure
            this.$image = this.element;

            this.$container = $('<div/>').
                addClass('container').
                insertBefore(this.element).
                dragScroll();

            this.$image.
                appendTo(this.$container).
                css('opacity', 0);

            this.$panel = $('<div/>').
                appendTo(this.$container).
                addClass('panel').
                fadeOut(0);

            this.$zoomOut = $('<button/>').
                appendTo(this.$panel).
                text('-');

            this.$zoomIn = $('<button/>').
                appendTo(this.$panel).
                text('+');

            this.$zoomFit = $('<button/>').
                appendTo(this.$panel).
                text('fit');

            this.$zoomFull = $('<button/>').
                appendTo(this.$panel).
                text('full');

            // events
            this.$zoomOut.bind('click', function () {
                that.setScale(that._scale * 0.9);
            });
            this.$zoomIn.bind('click', function () {
                that.setScale(that._scale * 1.1);
            });
            this.$zoomFit.bind('click', function () {
                that.setScale('fit');
            });
            this.$zoomFull.bind('click', function () {
                that.setScale(1);
            });

            // bind events
            this.$image.bind({
                'load': function () {
                    // initialize
                    that._nativeWidth = that.$image.width();
                    that._nativeHeight = that.$image.height();
                    that._nativeRatio = that._nativeWidth / that._nativeHeight;
                    that.setScale('fit');
                    that.$panel.fadeIn('slow');
                    that.$image.animate({'opacity': 1}, 'slow');
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

        },

        setScale: function (scale) {
            var that = this, width, height;
            // scale is either a decimal number or the word 'fit'
            if (scale === 'fit') {
                if (this._nativeWidth >= this._nativeHeight) {
                    width = this.$container.width();
                    if (width > this._nativeWidth) {
                        width = this._nativeWidth;
                    }
                    height = (width / this._nativeWidth) * this._nativeHeight;
                } else {
                    height = this.$container.height();
                    if (height > this._nativeHeight) {
                        height = this._nativeHeight;
                    }
                    width = (height / this._nativeHeight) * this._nativeWidth;
                }
                this._scale = width / this._nativeWidth;
                this.$image.clearQueue().
                    animate({
                        'height': height,
                        'width': width
                    }, function () {
                        that.$image.css({
                            'height': 'auto',
                            'width': 'auto',
                            'max-width': '100%',
                            'max-height': '100%'
                        });
                    });
            } else {
                this._scale = scale;
                this.$image.css({
                    'width': this.$image.width(),
                    'height': this.$image.height(),
                    'max-width': 'none',
                    'max-height': 'none'
                }).
                    clearQueue().
                    animate({
                        'width': scale * this._nativeWidth,
                        'height': scale * this._nativeHeight
                    });
            }
        }

    });

    $(function () {
        $('#image').image();
    });

}(window.jQuery));
