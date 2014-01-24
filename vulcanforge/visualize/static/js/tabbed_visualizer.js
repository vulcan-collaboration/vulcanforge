var $vf = $vf || {};

/* New Window Button */
$vf.NewWindowButton = function(default_url, config){
    this.setUrl(default_url);
    if (config) {
        $.extend(this, config);
    }
    this.init();
};

$vf.NewWindowButton.prototype = {
    activeUrl: null,
    generateUrl: null,
    buttonE: null,
    onClick: null,
    standAlone: false,

    init: function(){
        var t = this;
        this.buttonE = $('<div/>', {
            "class": 'new-window-container'
        }).append($('<a/>', {
            'class': 'new-window-button has-icon ico-new_window',
            'text': 'View in new window',
            'href': '#',
            'click': function(e) {
                if (t.onClick) {
                    t.onClick(e);
                }
                t.newWindow();
            }
        }));

        if (this.standAlone) {
            this.buttonE.addClass('stand-alone');
        }
    },

    setUrl: function(url){
        this.activeUrl = url;
    },

    newWindow: function(){
        var newwin,
            url = this.generateUrl ? this.generateUrl(this.activeUrl) : this.activeUrl,
            params  = [
                'width=' + screen.width,
                'height=' + screen.height,
                'top=0, left=0',
                'fullscreen=yes',
                'directories=no',
                'location=no',
                'menubar=no',
                'resizable=no',
                'scrollbars=yes',
                'status=no',
                'toolbar=no',
                'location=no'
            ];
        newwin = window.open(url, '_blank', params.join(', '));
        if (window.focus) {
            newwin.focus();
        }
    }
};

function renderTabbedVisualizer(config) {

    /* generate iframe */
    var visualizerSpecs = config.visualizerSpecs,
        $element = config.element,
        downloadUrl = config.downloadUrl,
        filename = config.filename,
        $iframeE = $('<iframe/>', {"class": 'visualizerContainer'}),
        visualizerToolbarE,
        newWindowB,
        toolbarTabsUL,
        toolbarTabs,
        visualizerFooterE,
        visualizerWrapper,
        visualizerWrapperE,
        selectVisualizerTab = function (name) {
            $('a[data-visualizer="'+name+'"]', toolbarTabsUL).click();
        };

    $iframeE.on('load', function () {
        var iframeWindow = this.window || this.contentWindow;
        iframeWindow.TAB_API = {
            'visualizerSpecs': visualizerSpecs,
            'selectVisualizerTab': selectVisualizerTab
        };
    });

    if (typeof config.height !== "undefined") {
        $iframeE.css("height", config.height);
    }

    /* generate toolbar */
    visualizerToolbarE = $('<div/>', {
        'class': 'visualizerToolbar'
    });

    /* --new window button */
    newWindowB = new $vf.NewWindowButton(visualizerSpecs[0].fullscreen_url, {
        "generateUrl": function (url) {
            var splitQuery = $iframeE.attr("src").split("?", 1),
                iframeSearchStr = null;
            if (splitQuery.length > 1) {
                iframeSearchStr = splitQuery[1];
                url += '&iframe_query=' + encodeURIComponent(iframeSearchStr);
            }
            return url;
        }
    });

    /* --tabs */
    toolbarTabsUL = $('<ul/>', {
        "class": "ui-tabs-nav ui-helper-reset ui-helper-clearfix ui-corner-all"
    });
    $.each(visualizerSpecs, function(i, spec){
        var thisTab;
        if (!spec.hasOwnProperty("fullscreen_url")){
            spec.fullscreen_url = '#';
        }
        thisTab = $('<li/>', {
            "class": "ui-state-default ui-corner-top" +
                (spec.active === true ? " ui-state-active ui-tabs-selected" : " ui-tabs-unselected")
        }).append($('<a/>', {
            "href": spec.fullscreen_url,
            "text": spec.name,
            "title": "View with " + spec.name,
            "click": function(){
                toolbarTabsUL
                    .find('li.ui-tabs-selected')
                    .removeClass('ui-tabs-selected ui-state-active')
                    .addClass('ui-tabs-unselected');
                $(this).parent().addClass('ui-tabs-selected ui-state-active')
                                .removeClass('ui-tabs-unselected');
                $iframeE.attr("src", spec.iframe_url);
                newWindowB.setUrl(spec.fullscreen_url);
                return false;
            }
        }).attr('data-visualizer', spec.name));
        toolbarTabsUL.append(thisTab);
        if (i === 0){
            thisTab.find("a").click();
        }
    });

    /* --download button */
    if (downloadUrl){
        toolbarTabsUL.append(
            $('<li/>', {
                "class": "ui-state-default ui-corner-top ui-tabs-unselected dl-link-container"
            }).append($('<a/>', {
                "class": "dl-link",
                "href": downloadUrl,
                "title": "Download " + filename + "..."
            }))
        );
    }

    toolbarTabs = $('<div/>', {
        "class": "visualizerTabs"
    }).append(toolbarTabsUL);
    visualizerToolbarE
            .append(toolbarTabs)
            .append(newWindowB.buttonE)
            .append($('<div/>').css('clear', 'both'));


    /* generate footer */
    visualizerFooterE = $('<div/>', {
        'class': 'visualizerFooter'
    });
    visualizerFooterE.append($('<span class="visualizerFilename">Source: ['+filename+']</span>'));

    /* render EVERYTHING */
    visualizerWrapperE = $('<div/>', {
        'class': 'visualizerWrapper'
    });
    visualizerWrapperE
        .append(visualizerToolbarE)
        .append($iframeE)
        .append(visualizerFooterE);
    $element.html(visualizerWrapperE);
}

$.fn.tabbedVisualizer = function(config){
    config.element = $(this);
    renderTabbedVisualizer(config);
    return config.element;
};
