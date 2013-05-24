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
                'width='+screen.width,
                'height='+screen.height,
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

$vf.EmbedVisualizer = function(config) {

    /* generate iframe */
    var src = config.src,
        afterThisElement = config.after,
        resource = config.resource,
        filename = config.filename,
        tabUrls = config.tabUrls,
        iframeAttrs = config.iframeAttrs,
        hideTabBar = config.hideTabBar || false,
        iframeNameStr = 'visualizerContainer_' + Math.round(Math.random()*10000),
        iframeE,
        visualizerToolbarE,
        newWindowB,
        toolbarTabsUL,
        toolbarTabs,
        visualizerFooterE,
        visualizerWrapper,
        visualizerWrapperE;

    $.extend(iframeAttrs, {
        "name": iframeNameStr,
        "src": src,
        "class": 'visualizerContainer'
    });

    iframeE = $('<iframe/>', iframeAttrs);

    /* generate toolbar */
    if (hideTabBar === false){
        visualizerToolbarE = $('<div/>', {
            'class': 'visualizerToolbar'
        });
        /* --new window button */
        newWindowB = new $vf.NewWindowButton(tabUrls[0].fs_url, {
            "generateUrl": function(url){
                var iframeSearchStr = null;
                try {
                    iframeSearchStr = parent.frames[iframeNameStr].location.search;
                    if (iframeSearchStr.charAt(0) === '?'){
                        iframeSearchStr = iframeSearchStr.slice(1);
                    }
                } catch (err) {

                }
                return iframeSearchStr ? url+'&iframe_query='+encodeURIComponent(iframeSearchStr) : url;
            }
        });
        /* --tabs */
        toolbarTabsUL = $('<ul/>', {
            "class": "ui-tabs-nav ui-helper-reset ui-helper-clearfix ui-corner-all"
        });
        $.each(tabUrls, function(i, url){
            if (url.fs_url === undefined){
                url.fs_url = '#';
            }
            toolbarTabsUL.append($('<li/>', {
                "class": "ui-state-default ui-corner-top" + (url.url === src ? " ui-state-active ui-tabs-selected" : " ui-tabs-unselected")
            }).append($('<a/>', {
                "href": url.fs_url,
                "text": url.name,
                "title": "View with " + url.name,
                "click": function(){
                    toolbarTabsUL.find('li.ui-tabs-selected').removeClass('ui-tabs-selected ui-state-active').addClass('ui-tabs-unselected');
                    $(this).parent().addClass('ui-tabs-selected ui-state-active').removeClass('ui-tabs-unselected');
                    iframeE.attr('src', url.url);
                    newWindowB.setUrl(url.fs_url);
                    return false;
                }
            }))
            );
        });
        toolbarTabsUL.append(
                $('<li/>', {
                    "class": "ui-state-default ui-corner-top ui-tabs-unselected dl-link-container"
                }).append($('<a/>', {
                    "class": "dl-link",
                    "href": resource,
                    "title": "Download File..."
                }))
        );
        toolbarTabs = $('<div/>', {
            "class": "visualizerTabs"
        }).append(toolbarTabsUL);
        visualizerToolbarE
                .append(toolbarTabs)
                .append(newWindowB.buttonE)
                .append($('<div/>').css('clear', 'both'));
    }


    /* generate footer */
    visualizerFooterE = $('<div/>', {
        'class': 'visualizerFooter'
    });
    visualizerFooterE.append($('<span class="bomLocation">Source: ['+filename+']</span>'));

    /* render EVERYTHING */
    visualizerWrapperE = $('<div/>', {
        'class': 'visualizerWrapper'
    });
    visualizerWrapperE
        .append(visualizerToolbarE)
        .append(iframeE)
        .append(visualizerFooterE);
    afterThisElement.after(visualizerWrapperE);
};

$vf.afterInit(function() {

    $('.visualizerWrapper[data-add-new-window-button-to]' ).each(function() {
        var $this = $(this ),
            fs_url = $this.data('add-new-window-button-to'),
            newWindowB = new $vf.NewWindowButton(fs_url, {
            "generateUrl": function(url){
                var iframeSearchStr = null;
                try {
                    iframeSearchStr = parent.frames[iframeNameStr].location.search;
                    if (iframeSearchStr.charAt(0) === '?'){
                        iframeSearchStr = iframeSearchStr.slice(1);
                    }
                } catch (err) {

                }
                return iframeSearchStr ? url+'&iframe_query='+encodeURIComponent(iframeSearchStr) : url;
            },
            'standAlone': true
        });
        $this.prepend(newWindowB.buttonE);
    });

});