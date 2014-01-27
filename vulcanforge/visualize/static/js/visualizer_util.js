(function (global) {
    "use strict";
    // Import Globals
    var $ = global.jQuery,
        defaults = {
            targetAlign: "right bottom",
            linksAlign: "right top"
        };

    var VisualizerOptions = function( element, options ){

        var t = this;
        var init, renderLinks, trigger, untrigger;

        // properties
        t.visualizerLinks = options.visualizerLinks;

        // internals
        var targetAlign = options.targetAlign;
        var linksAlign = options.linksAlign;
        var offset = options.offset;
        var onClick = options.onClick;
        var ul, panel;
        var triggered = false;
        var isHoveringPanel = false;

        var $topArrowShape, $topArrowShapeHolder;

        init = function (){
            element.mouseenter(trigger);
            element.mouseleave(function(){
                setTimeout(untrigger, 100);
            });
        };

        renderLinks = function (){
            if (panel){
                panel.remove();
            }

            panel = $('<div/>', {
                "class": "visualizer_options"
            });

            ul = $('<ul/>');

            $topArrowShape = $('<svg xmlns="http://www.w3.org/2000/svg" version="1.1"><polygon points="0,10, 10,0, 20,10"/></svg>');
            $topArrowShapeHolder = $('<div/>', {
                'class': 'callout-wrapper'
            });

            $topArrowShapeHolder.append($topArrowShape);

            panel.append($topArrowShapeHolder);
            panel.append(ul);

            $.each(t.visualizerLinks, function(i, link){
                var a = $('<a/>', {
                    "href": link.url,
                    "text": link.name,
                    "click": function(){
                        untrigger();
                        if (onClick !== undefined){
                            return onClick(link);
                        }
                    }
                });
                if (link.title){
                    a.attr('title', link.title);
                }
                ul.append($('<li/>').append(a));
            });
            $('body').append(panel);

            panel.mouseenter(function(){
                isHoveringPanel = true;
            }).mouseleave(function(){
                isHoveringPanel = false;
                untrigger();
            });

        };

        trigger = function(){
            if (triggered === false){
                triggered = true;
                if (panel === undefined){
                    renderLinks();
                }
                element.parent().addClass('vo-engaged');
                element.addClass('vo-engaged');
                panel.show().position({
                    my: linksAlign,
                    at: targetAlign,
                    of: element,
                    offset: offset
                });
            }
            return false;
        };

        untrigger = function(){
            if (triggered === true && isHoveringPanel === false){
                panel.hide().css('left', 0).css("top", 0);
                element.removeClass('vo-engaged');
                element.parent().removeClass('vo-engaged');
                triggered = false;
            }
        };

        // methods
        t.init = init;
        t.trigger = trigger;
        t.renderLinks = renderLinks;

    };

    $.fn.visualizerOptions = function(options){
        options = $.extend(true, {},
            defaults,
            {},
            options
        );

        this.each(function(i,e){
            var element = $(e);
            var visualizer_options = new VisualizerOptions(element, options);
            element.data('visualizerOptions', visualizer_options);
            visualizer_options.init();
        });

        return this;
    };

}(window));
