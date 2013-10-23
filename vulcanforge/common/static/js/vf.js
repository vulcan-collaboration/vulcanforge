/**
 * Base VulcanForge application architecture.
 *
 * @module $vf
 *
 * @author Naba Bana
 */

/**
 * Namespace for general VF-related stuff.
 * Use this for random application-specific properties instead of the window object or global ns.
 *
 * @class $vf
 * @static
 */

var $vf = $vf || {
    page_state: null,
    currentPage: null,
    refreshId: null,
    tb: null,
    toolBar: null,
    linkBin: null
};

(function (global) {
    "use strict";

    // Import Globals
    var $ = global.$,
        trace,
        guid,
        isSet,
        $ws;

    // privates
    var initialized = false,        // stores state
        tasksAfterInit = [];        // function/attribute pairs which should be called after/when VF is initialized


    // this function will go through the functions which should be called after/when VF is initialized. Event handlers
    // are called on $vf as context
    var do_afterInits = function() {
        if (initialized && tasksAfterInit.length > 0) {
            var e = tasksAfterInit.shift();

            while (e !== null) {
                if ($.isFunction(e[0])) {
                    e[0].apply($vf, e[1]);
                }

                if (tasksAfterInit.length > 0) {
                    e = tasksAfterInit.shift();
                } else {
                    e = null;
                }
            }
        }
    };

    /**
     * Method to add a task which will bw invoked when $vf is intialized
     *
     * @param task
     * @param args
     */
    $vf.afterInit = function(task, args) {
        if (global.jQuery.isFunction(task)) {
            tasksAfterInit.push([task, args]);
            do_afterInits();
        }
    };

    /**
     *
     * Global and general page init should come here.
     *
     */
    $vf.init = function (userURL, tabs, referenceBin) {

        $ = global.jQuery;
        trace = global.trace;
        guid = global.guid;
        isSet = global.isSet;
        $ws = global.$ws;

        trace('Initializing VF App...');

        if (!initialized) {

            var headerUnreadCountE, $body=$('body');

            initialized = true;

            $vf.currentPage = {
                userURL: null,
                pageType: $body.attr('data-pagetype') || null,
                pageTitle: $body.attr('data-pagetitle') ||
                           window.document.title.replace( $('body').data('title-postfix') || '', '')
            };

            var a = '&hellip;';
            var h = 47;
            $('ul.sidebarmenu a span').not('allow_big').each(function () {
                var t = $(this).html();
                $(this).attr('title', $(this).text());
                while ($(this).height() > h && t.length > 0) {
                    t = t.slice(0, -1);
                    $(this).html(t + a);
                }
            });


            /** vertical text canvas switch */
            $('.verticalText').each(function () {
                var text = $(this).text();
                var $canvas = $('<canvas/>');
                var canvas = $canvas[0];
                var ctx = canvas.getContext('2d');
                var font = $(this).css('font-size') + ' sans-serif';

                ctx.font = font;
                var wm = ctx.measureText('M').width;

                //noinspection JSSuspiciousNameCombination
                canvas.height = ctx.measureText(text).width;
                canvas.width = wm * 2;

                ctx.translate(wm * 0.35, 0);
                ctx.rotate(Math.PI / 2);
                ctx.font = font;
                ctx.fillStyle = '#fff';
                ctx.fillText(text, 0, 0);

                $(this).replaceWith($canvas);
                $(this).show();
            });

            if ( userURL !== null ) {

                $vf.currentPage.userURL = userURL;

                // Update service
                var defaultFrequency = 5000,
                    idleFrequency = 60000,
                    windowIdleTimeOut = 30000;

                $vf.updateService = (function ( serviceUrl, frequency ) {

                    var _currentValues = {},
                        _subscribers = {},
                        subscribe = function( key, callBack, nullValue ) {
                            if (nullValue !== undefined) {
                                _currentValues[key] = nullValue;
                            }

                            if (!_subscribers[key]) {
                                _subscribers[key] = [];
                                _subscribers[key].push(callBack);
                            }

                            stop();
                            _poll();
                            reset();
                        },
                        unSubscribe = function( key, callBack ) {
                            var callBacks = _subscribers[key],
                                index = -1;

                            if (callBacks) {
                                index = callBacks.indexOf(callBack);
                                if (index > -1){
                                    callBacks.splice(index, 1);
                                }
                            }
                        },
                        reset = function() {
                            stop();
                            if ( frequency ) {
                                _intervalID = setInterval(_poll, frequency);
                            }
                        },
                        stop = function() {
                            clearInterval(_intervalID);
                        },
                        _poll = function() {
                            $.ajax({
                                url:serviceUrl,
                                dataType:'json',
                                data:{},
                                success:function(data) {
                                    $.each(data, function(key,newValue) {
                                        var wasChange = newValue !== _currentValues[key];
                                        _currentValues[key] = newValue;

                                        if (_subscribers[key]) {
                                            $.each(_subscribers[key], function(index, callBack) {
                                                if (wasChange) {
                                                    try {
                                                        callBack.call(callBack, newValue);
                                                    } catch (e) {
                                                        trace(e);
                                                    }
                                                }
                                            });
                                        }
                                    });
                                }
                            });

                        },
                        changeFrequency = function(newFrequency) {
                            frequency = newFrequency;
                            reset();
                        },
                        _intervalID;

                    return {
                        subscribe: subscribe,
                        unSubscribe: unSubscribe,
                        changeFrequency: changeFrequency,
                        stop: stop,
                        reset: reset
                    }
                })(userURL+'/profile/updates_dispatcher', defaultFrequency);

                // making polls less frequent when user is idle
                $( document ).idleTimer( windowIdleTimeOut );
                $( document ).on( "idle.idleTimer", function(){
                    $vf.updateService.changeFrequency(idleFrequency);
                    trace('User is not very active.');
                });
                $( document ).on( "active.idleTimer", function(){
                    $vf.updateService.changeFrequency(defaultFrequency);
                    trace('User is active again.');
                });

                switch ( $vf.currentPage.pageType ) {

                    case 'visualizerFullScreen':
                        $vf.referenceBin = new $ws.ReferenceBin({
                            addSL: new $vf.ServiceLocation(userURL + "profile/reference_bin", "POST"),
                            removeSL: new $vf.ServiceLocation(userURL + "profile/reference_bin/delete_reference", "POST"),
                            getSL: new $vf.ServiceLocation(userURL + "profile/reference_bin", "GET"),
                            containerE: $('#right-toolbar .toolbar-lower'),
                            referenceDescriptors: referenceBin.contents,
                            lastMod: referenceBin.last_mod
                        });

                        break;

                    default:

                        $vf.workspaceTabBar = new $ws.WorkspaceTabBar({
                            addSL: new $vf.ServiceLocation(userURL + "profile/workspace_tabs", "POST"),
                            updateSL: new $vf.ServiceLocation(userURL + "profile/workspace_tabs", "PUT"),
                            removeSL: new $vf.ServiceLocation(userURL + "profile/workspace_tabs/", "DELETE"),
                            getSL: new $vf.ServiceLocation(userURL + "profile/workspace_tabs", "GET"),
                            barContainer: $('#workspace-tab-bar-container'),
                            tabDescriptors: tabs
                        });

                        $vf.referenceBin = new $ws.ReferenceBin({
                            addSL: new $vf.ServiceLocation(userURL + "profile/reference_bin", "POST"),
                            removeSL: new $vf.ServiceLocation(userURL + "profile/reference_bin/delete_reference", "POST"),
                            getSL: new $vf.ServiceLocation(userURL + "profile/reference_bin", "GET"),
                            containerE: $('#right-toolbar .toolbar-lower'),
                            referenceDescriptors: referenceBin.contents,
                            lastMod: referenceBin.last_mod
                        });

                        break;
                }

            }

            headerUnreadCountE = $('#header-unread-count');

            if ( headerUnreadCountE.length ) {

                $vf.updateService.subscribe('dashboard_unread_count',
                    function(unreadCount) {

                        headerUnreadCountE.text(unreadCount);
                        if (unreadCount > 0) {
                            headerUnreadCountE.addClass('unread');
                        } else {
                            headerUnreadCountE.removeClass('unread');
                        }
                    }, 0);
            }

            // Search related stuff

            trace ('Initing global search');

            // setting up global-search-field
            var globalSearchFieldE = $('#global-search-field' ),
                $sidebar = $("#sidebar");

            var updateKeywordSearchField = function () {
                var field = $(this);
                if (field.val() == '') {
                    if ( !field.hasClass('empty') ) {
                        field.addClass('empty');
                    }
                } else {
                    if ( field.hasClass('empty') ) {
                        field.removeClass('empty');
                    }
                }
            };


            globalSearchFieldE.change(updateKeywordSearchField);
            globalSearchFieldE.focusout(updateKeywordSearchField);

            globalSearchFieldE.focusin(function () {
                var field = $(this);
                if ( field.hasClass('empty') ) {
                    field.removeClass('empty');
                }
            });

            updateKeywordSearchField.call(globalSearchFieldE);

            // Setting up sidebar-scroll
            trace('Setting up sidebar-scroll');
            if ($sidebar.length){
                $sidebar.niceScroll({
                    cursorcolor:"#999",
                    cursoropacitymax:0.8,
                    boxzoom:false,
                    touchbehavior:false,
                    zindex:85,
                    railoffset:{
                        top:0,
                        left:0
                    },
                    cursorwidth:4
                });

                $vf.sidebarScroll = $sidebar.getNiceScroll();

                // block scrollbar from blocking other elements

                $('#sidebar').mouseout(function () {
                    $vf.sidebarScroll.hide();
                }).mouseover(function () {
                    $vf.sidebarScroll.show();
                });
            }

            // Taking care of post-links
            $( '.post-link' )
                .click( function ( evt ) {
                    var cval = $.cookie( '_session_id' );
                    evt.preventDefault();
                    $.post(
                        this.href,
                        {
                            _session_id: cval
                        },
                        function ( val ) {
                            if (val.error) {
                                alert(val.error);
                            } else {
                                window.location = val.location;
                            }
                        },
                        'json' );
                } );


            // going through afterInit hooks

            do_afterInits();

            // visual fizes, taking care of trimming

            $vf.handleTrimLeft();

            $(window ).resize(function() {
                $vf.handleTrimLeft();
            });

        } else {
            throw 'Someone wanted to initialize the page twice, which is quite wrong!';
        }
    };

    /**
     *
     * Left trimmer
     *
     */

    $vf.handleTrimLeft = function( $el ) {

        var trimLeft = function(row){

            var trimContents = function(row, node){

                    while (row.scrollWidth > row.offsetWidth) {

                        var childNode = node.firstChild;

                        if (!childNode)
                            return true;

                        if (childNode.nodeType == document.TEXT_NODE){
                            trimText(row, node, childNode);
                        }else {
                            var empty = trimContents(row, childNode);
                            if (empty){
                                node.removeChild(childNode);
                            }
                        }
                    }

                    return true;
                },
                trimText = function(row, node, textNode){
                    var value = '...' + textNode.nodeValue;
                    do {
                        value = '...' + value.substr(4);
                        textNode.nodeValue = value;

                        if (value == '...'){
                            node.removeChild(textNode);
                            return;
                        }
                    }
                    while (row.scrollWidth > row.offsetWidth);
                };

            trimContents(row, row);
        };

        var count = 0;

        if (!$el) {
            $('.left-trimmed' ).each(function(i,e) {
                var $e = $(e),
                    savedText = $e.data('initialText')
                if (!savedText) {
                    !$e.data('initialText', $e.html())
                } else {
                    $e.html(savedText);
                }
                trimLeft(e);
                count = i;
            });
        } else {
            var $e = $el,
                e = $el[0],
                savedText = $e.data('initialText')
            if (!savedText) {
                !$e.data('initialText', $e.html())
            } else {
                $e.html(savedText);
            }
            trimLeft(e);
            count = 1;
        }

    }

    /**
     *
     * Main Search services
     *
     */
    $vf.Search = function ( config ) {

        if (config) {
            $.extend(this, config);
        }

        if (this.data) {
            this.render_all(this.data);
        }

        if (this.sidebar_form) {
            var t = this;
            this.sidebar_form.find('input').change(function () {
                t.page = 0;
                t.load_results('advanced');
            });
        }

    };

    $vf.Search.prototype = {

        discoveryAccessE: null,

        // protocol
        searchSL: '',
        query_param: 'q',

        // filters
        filters: [],

        // pagination
        pagination: true,
        page: 0,
        pageSize: 10,
        MAX_COLUMNS: 12,
        PAGE_LENGTHS: [10, 20, 30, 50, 100],
        pagerContainerEls: null,

        // other options
        displayProject: true,

        // jQuery DOM Elements
        results_container: null,
        sidebar_form: null,
        results_header: null, //optional


        render_results: function (results, count) {
            var t = this,
                ul,
                pagerContainerEls;

            // results
            ul = $('<ul/>', {"class": "search-result"});
            $.each(results, function (i, result) {
                ul.append(t.render_result(result));
            });

            // pagination
            if (this.pagerContainerE) {
                this.pagerContainerE.remove();
            }
            pagerContainerEls = this.pagerContainerEls = [
                $('<div/>', {'class': 'pagerContainer'}),
                $('<div/>', {'class': 'pagerContainer'})
            ];
            this.results_container.html(
                $('<p/>').
                    append($('<strong/>').text(this.q)).
                    append(' was found in ' + count + ' items:'))
                .append(pagerContainerEls[0])
                .append(ul)
                .append(pagerContainerEls[1]);

            if (this.results_header) {
                var header_text = '';
                switch (results.length) {
                case 0:
                    header_text = 'No Search Results';
                    break;
                case 1:
                    header_text = '1 Search Result';
                    break;
                case 2:
                    header_text = results.length + ' Search Results';
                    break;
                }
                this.results_header.text(header_text);
            }
        },

        render_result: function (doc) {
            var result, title, artifactLinkE;

            result = $('<li/>', {
                "class": doc.type_s.toLowerCase().
                    replace('exchange term', 'component')
            });

            title = $('<h4/>', {"class": 'title'}).
                appendTo(result);

            artifactLinkE = $('<span/>').
                addClass('artifact-link-container').
                appendTo(title);

            var linkData = {
                artifactType: $vf.slugify(doc.type_s),
                label: doc.title_s || doc.name_s,
                refId: doc.id,
                clickURL: doc.url_s,
                containerE: artifactLinkE
            };
            if (!doc.can_reference_b){
                linkData.infoURL = null;
            }
            new $vf.ArtifactLink(linkData).render();

            $('<p/>', {
                "class": 'summary',
                text: doc.summary_t || doc.snippet_t || doc.description_t
            }).
                appendTo(result);

            if (this.displayProject && doc.project_shortname_t) {
                title.append(
                    $('<span/>').text(' in ')
                ).append(
                    $('<a/>', {href: doc.url_s})
                        .text(doc.project_name_t)
                );
                result.addClass('project');
            }

            if (!isNaN(parseFloat(doc.rel_score)) && isFinite(doc.rel_score)) {
                title.append(
                    $('<div/>', {
                        "class": "score_container",
                        "title": Math.round(100 * doc.rel_score) / 100
                    }).append(
                        $('<div/>', {"class": "search_score"})
                            .css("width",
                            4 * Math.round(10 * doc.rel_score) / 10 - 1)
                    )
                );
            }

            $('<div/>', {
                "class": "flag"
            }).appendTo(result);
            return result;
        },

        renderPager: function () {
            if (this.pagination && this.pagerContainerEls) {
                var t = this;
                $.each(t.pagerContainerEls, function (i, containerE) {
                    t.pager = new $vf.Pager();
                    t.pager.containerE = containerE;
                    t.pager.onGotoPage = t.onGotoPage;
                    t.pager.onGotoPage_ctx = t;
                    t.pager.configure(t.pagination);
                    t.pager.render();
                });
            }
        },

        onGotoPage: function (n) {
            this.page = n;
            this.load_results('advanced');
        },

        load_results: function (mode) {
            if (this.q) {
                if (!mode) {
                    mode = 'simple';
                }
                var data = [
                    {
                        name: this.query_param,
                        value: this.q
                    },
                    {
                        name: 'limit',
                        value: this.pageSize
                    },
                    {
                        name: 'startPos',
                        value: this.page * this.pageSize
                    },
                    {
                        name: 'mode',
                        value: mode
                    }
                ];
                if (mode != 'simple' && this.sidebar_form) {
                    data = data.concat(this.sidebar_form.serializeArray());
                }
                $.ajax({
                    url: this.searchSL.url + '.json',
                    type: this.searchSL.type,
                    data: data,
                    dataType: "json",
                    context: this,
                    success: function (response) {
                        this.results_loaded(response);
                    },
                    error: function () {
                        trace("Search Results Load Error");
                    }
                });
            }
        },

        results_loaded: function (response) {
            this.render_all(response);
        },

        render_all: function (data) {
            this.render_results(data.results, data.count);
            this.pagination = {
                itemCount: data.count,
                currentPage: this.page,
                itemPerPage: this.pageSize,
                onGotoPage: this.onGotoPage,
                onGotoPage_ctx: this
            };
            this.renderPager();
        }


    };


    /**
     * Pagination infrastructure
     *
     * @class Pager
     */
    $vf.Pager = function (config) {
        /*this.id = guid();*/
        this.onGotoPage_ctx = this;
        if (config) {
            $.extend(this, config);
        }
    };

    $vf.Pager.prototype = {
        id: null,

        containerE: null,

        pagerE: null,

        maxLength: 16,
        currentPage: null,
        totalPages: null,
        itemCount: null,
        itemPerPage: null,

        onGotoPage_ctx: null,

        onGotoPage: function (n) {
            trace('GotoPage [' + n + ']');
        },

        configure: function (config) {
            $.extend(this, config);
        },

        render: function () {

            var that = this;
            var nofb = 0, i, closeRange, DU, DL, L, pagerE, firstPageE, prevPageE, nextPageE, lastPageE, compress;

            if (this.pagerE) {
                this.pagerE.remove();
            }

            this.totalPages = Math.ceil(this.itemCount / this.itemPerPage);

            if (this.totalPages > 1) {
                pagerE = this.pagerE = $('<ul/>', {
                    'class': 'pager',
                    id: this.id
                });

                firstPageE = $('<li/>', {
                    'class': 'stepper firstPage',
                    title: 'First page'
                });

                prevPageE = $('<li/>', {
                    'class': 'stepper prevPage',
                    title: 'Previous page'
                });

                if (this.currentPage > 0) {
                    firstPageE.append($('<a/>', {
                        html: '&laquo;',
                        click: function () {
                            that.onGotoPage.call(that.onGotoPage_ctx, 0);
                        }
                    }));

                    prevPageE.append($('<a/>', {
                        html: '&lsaquo;',
                        click: function () {
                            that.onGotoPage.call(that.onGotoPage_ctx, (that.currentPage > 0) ? that.currentPage - 1 : 0);
                        }
                    }));
                }

                lastPageE = $('<li/>', {
                    'class': 'stepper lastPage',
                    title: 'Last page'
                });

                nextPageE = $('<li/>', {
                    'class': 'stepper nextPage',
                    title: 'Next page'
                });

                if (this.currentPage < this.totalPages - 1) {

                    lastPageE.append($('<a/>', {
                        html: '&raquo;',
                        click: function () {
                            that.onGotoPage.call(that.onGotoPage_ctx, that.totalPages - 1);
                        }
                    }));

                    nextPageE.append($('<a/>', {
                        html: '&rsaquo;',
                        click: function () {
                            that.onGotoPage.call(that.onGotoPage_ctx, (that.currentPage < that.totalPages - 1) ? that.currentPage + 1 : that.totalPages - 1);
                        }
                    }));
                }

                pagerE.append(firstPageE);
                pagerE.append(prevPageE);

                compress = (this.totalPages > this.maxLength);

                if (compress) {

                    L = Math.floor(this.maxLength / 4);

                    closeRange = {
                        bottom: Math.max(0, this.currentPage - L),
                        top: Math.min(this.totalPages - 1, this.currentPage + L)
                    };

                    DL = Math.round(closeRange.bottom / L);
                    DU = Math.round((this.totalPages - 1 - closeRange.top) / L);
                }

                var on_click = function () {
                    that.onGotoPage.call(that.onGotoPage_ctx, $(this).data('pageN'));
                };

                for (i = 0; i < this.totalPages; i++) {

                    if (!compress || (

                        // each page gets its individual button within the close range of currentPage
                        compress &&
                            ( i >= closeRange.bottom &&
                                i <= closeRange.top )

                        ) || (

                        compress && (
                            ( i < closeRange.bottom && ( (i + 1) % DL) === 0) ||
                                ( i > closeRange.top && ( (i + 1) % DU) === 0 )
                            )
                        )) {

                        var liE = $('<li/>', {});

                        if (this.currentPage != i) {
                            liE.append($('<a/>', {
                                click: on_click,
                                title: 'Go to page ' + (i + 1),
                                text: i + 1,
                                'class': 'pagerLink',
                                data: {
                                    pageN: i
                                }
                            }));

                        } else {

                            liE.text(i + 1);
                            liE.addClass('currentPage');

                        }

                        if (compress && i != 0 && i == closeRange.bottom) {
                            pagerE.append($('<li/>', {
                                html: '&hellip;'
                            }));
                        }

                        pagerE.append(liE);

                        if (compress && i != this.totalPages - 1 &&
                            i == closeRange.top) {
                            pagerE.append($('<li/>', {
                                html: '&hellip;'
                            }));
                        }

                        nofb++;

                    }
                }

                trace('Number of pager buttons: ' + nofb);

                pagerE.append(nextPageE);
                pagerE.append(lastPageE);

                if (this.containerE) {
                    this.containerE.append(this.pagerE);
                }
            }

        }

    };

    /**
     *
     * Class ServiceLocation
     *
     * For specifying (ajax) service locations.
     *
     */
    $vf.ServiceLocation = function (url, type) {
        if (isSet(url)) {
            this.url = url;
        }
        if (isSet(type)) {
            this.type = type;
        } else {
            this.type = "GET";      // default value (in harmony with jQuery)
        }
    };

    $vf.ServiceLocation.prototype = {
        url: null,
        type: null
    };

    /**
     *
     * Class PleaseWait
     *
     * A spinning pleasewait panel with a message layered over a target area
     *
     */

    $vf.PleaseWait = function (message, target, _opacity) {
        var opacity = _opacity || 1;
        this.id = guid && guid() || Math.random();
        this.target = target;

        this.skin = $('<div/>', {
            id: "PleaseWait_" + this.id,
            "class": "please-wait"
        });

        this.skin.css( 'opacity', opacity );
        this.skin.hide();
        this.skin.appendTo(target);

        this.messageHolder = $('<div/>', {
            id: "MessageHolder_" + this.id,
            "class": "please-wait-message"
        });

        this.messageHolder.appendTo(this.skin);

        this.spinner = $('<div/>', {
            id: "PleaseWaitSpinner _" + this.id,
            "class": "please-wait-spinner "
        });

        this.spinner.appendTo(this.skin);

        this.skin.disableSelection();

        this.update(message);
    };

    $vf.PleaseWait.prototype = {
        id: null,
        message: null,
        target: null,
        skin: null,
        messageHolder: null,
        spinner: null,

        update: function (message) {

            if ( message ) {
                this.message = message;
            }

            var h, w;

            h = this.target.height();
            w = this.target.width();

            this.skin.width(w);
            this.skin.height(h);

            var position = this.skin.position();

            this.skin.css("margin-top", -position.top);
            this.skin.css("margin-left", -position.left);

            h = this.skin.height();
            w = this.skin.width();

            this.messageHolder.css("margin-top", h / 2 + 32);

            this.messageHolder.text(this.message);

            this.spinner.css("top", h / 2 - 46);
            this.spinner.css("left", w / 2 - 33);
        },

        show: function () {
            if (!this.skin.is(":visible")) {
                this.skin.show();
            }
        },

        hide: function () {
            if (this.skin.is(":visible")) {
                this.skin.fadeOut();
            }
        }
    };


    /**
     *
     * Class ClickCondom
     *
     * This will disable what's beneath
     *
     */

    $vf.ClickCondom = function (target) {
        this.id = guid();
        this.target = target;

        this.skin = $('<div/>', {
            id: "ClickCondom_" + this.id,
            "class": "click-condom"
        });
        this.skin.hide();
        this.skin.appendTo(target);

        this.skin.data('host', this);

        this.update();
    };

    $vf.ClickCondom.prototype = {
        id: null,
        target: null,
        skin: null,

        update: function () {

            var h = this.target.outerHeight();
            var w = this.target.outerWidth();

            this.skin.width(w);
            this.skin.height(h);

            //var offset = this.target.offset();

            this.skin.css("top", 0);
            this.skin.css("left", 0);

        },

        on_positionChange: function () {
            var host = $(this).data('host');
            host.update.call(host);
        },

        show: function () {
            if (!this.skin.is(":visible")) {
                this.update();
                this.skin.show();
            }
        },

        hide: function () {
            if (this.skin.is(":visible")) {
                this.skin.fadeOut();
            }
        }
    };

    /**
     * clickConfirm
     *
     * confirms click with javascript popup before proceeding
     *
     * @param target
     * @param msg
     */
    $vf.clickConfirm = function (target, msg) {
        if (msg === undefined) {
            msg = 'Are you sure you want to do that?';
        }
        target.click(function () {
            return confirm(msg);
        });
    };


    /**
     * ISO format date parser
     */
    $vf.parseISO8601 = function (str) {
        // we assume str is a UTC date ending in 'Z'

        var parts = str.split('T'),
            dateParts = parts[0].split('-'),
            timeParts = parts[1].split('Z'),
            timeSubParts = timeParts[0].split(':'),
            timeSecParts = timeSubParts[2].split('.'),
            timeHours = Number(timeSubParts[0]), _date = new Date();

        _date.setUTCFullYear(Number(dateParts[0]));
        _date.setUTCMonth(Number(dateParts[1]) - 1);
        _date.setUTCDate(Number(dateParts[2]));
        _date.setUTCHours(Number(timeHours));
        _date.setUTCMinutes(Number(timeSubParts[1]));
        _date.setUTCSeconds(Number(timeSecParts[0]));
        if (timeSecParts[1]) {
            _date.setUTCMilliseconds(Number(timeSecParts[1]));
        }

        // by using setUTC methods the date has already been converted to local time(?)
        return _date;
    };

    /**
     * Simple relative date.
     *
     * Returns a string like "4 days ago". Prefers to return values >= 2. For example, it would
     * return "26 hours ago" instead of "1 day ago", but would return "2 days ago" instead of
     * "49 hours ago".
     *
     * Copyright (c) 2008 Erik Hanson http://www.eahanson.com/
     * Licensed under the MIT License http://www.opensource.org/licenses/mit-license.php
     */
    $vf.relativeDate = function (olderDate, newerDate) {
        var i;

        if (typeof olderDate == "string") {
            olderDate = new Date(olderDate);
        }
        if (typeof newerDate == "string") {
            newerDate = new Date(newerDate);
        } else if (typeof newerDate == "undefined") {
            newerDate = new Date();
        }

        var milliseconds = newerDate - olderDate;
        var conversions = [
            ["years", 31518720000],
            ["months", 2626560000 /* assumes there are 30.4 days in a month */],
            ["days", 86400000],
            ["hours", 3600000],
            ["minutes", 60000],
            ["seconds", 1000]
        ];

        for (i = 0; i < conversions.length; i++
            ) {
            var result = Math.floor(milliseconds / conversions[i][1]);
            if (result >= 2) {
                return result + " " + conversions[i][0] + " ago";
            }
        }

        return "1 second ago";
    };

    /**
     * slugify an input string using the same process as the server side slugify
     *
     * @param str
     */
    $vf.slugify = function (str) {
        return str.toString().
            toLowerCase().
            replace(/[^A-Za-z0-9]+/g, '-').
            replace(/(^-|-$)/g, '');
    };

    /**
     * automatic logout
     */
    /** defaults */
    $vf.idle_logout_enabled = true;
    $vf.idle_logout_minutes = 30;
    $vf.idle_logout_countdown_seconds = 30;
    /** /defaults */
    $vf.afterInit(function () {
        if ($vf.logged_in_as && $vf.idle_logout_enabled) {
            $.idleLogout({
                logoutSeconds: $vf.idle_logout_minutes * 60,
                countdownSeconds: $vf.idle_logout_countdown_seconds,
                logoutUrl: '/auth/logout'
            });
        }
    });

    /**
     * forgemarkdown extras
     */
    $vf.afterInit(function () {
        // Read More
        $('.md-read-more').each(function () {
            var $theMore = $(this).
                    hide(),
                $more = $('<a>Read more...</a>').
                    addClass('md-read-more-show').
                    addClass('inline-icon ico-info').
                    insertBefore($theMore).
                    bind('click', function () {
                        $(this).hide();
                        $less.show();
                        $theMore.
                            show();
                    }),
                $less = $('<a></a>').
                    addClass('md-read-more-hide').
                    addClass('inline-icon ico-close').
                    prependTo($theMore).
                    bind('click', function () {
                        $(this).hide();
                        $more.show();
                        $theMore.hide();
                    }).
                    hide();
        });
    });

    /**
     * Initializes the webflash functionality to display status messages as
     * user feedback in the top right corner of screen
     *
     * @method webflash
     * @namespace $vf
     */
    $vf.webflash = function (options) {
        var opts = $.extend({}, $vf.webflash.defaults, options);
        if ($.cookie('webflash')) {
            var flash_message = JSON.parse($.cookie('webflash'));
            var messagesEl = $("#" + opts.messagesId);

            messagesEl.notify(flash_message.message, {
                    status: flash_message.status,
                    timer: opts.timer
                }
            );

            $.cookie('webflash', null, {
                path: '/'
            });
        }
    };

    $vf.webflash.defaults = {
        messagesId: "messages",
        timer: 4000
    };

    $vf.ajaxErrorHandler = function (jqXHR, textStatus, errorThrown) {
        var alertParams = {
            title: 'Action could not be performed.',
            message: null
        };
        if (jqXHR.responseText) {
            try{
                var responseData = JSON.parse(jqXHR.responseText);
                if (responseData.detail) {
                    alertParams.message = responseData.detail;
                }
            } catch(err){
                alertParams.message = jqXHR.responseText;
            }
        }
        if (alertParams.message == null) {
            alertParams.message = errorThrown;
        }
        $vf.alert(alertParams);
    };

    $vf.alert = function (opt) {
        var message = typeof(opt) == 'string' ? opt : '';
        if (opt.title != undefined) {
            message += opt.title + '\n\n';
        }
        if (opt.message != undefined) {
            message += opt.message;
        }
        if (message.length > 0) {
            return alert(message);
        }
    };


    $vf.countDownUp = function ($timerTextElement, epoch, opt_callback) {
        var epochSeconds = epoch.getTime() / 1000,
            isFuture = new Date().getTime() / 1000 < epochSeconds,
            minuteSeconds = 60,
            hourSeconds = 60 * minuteSeconds,
            daySeconds = 24 * hourSeconds,
            updateMethod = function () {
                var nowSeconds, updateDelay, messageParts,
                    days, hours, minutes, seconds, isFinished;
                nowSeconds = new Date().getTime() / 1000;
                seconds = Math.round(Math.abs(epochSeconds - nowSeconds));
                days = Math.floor(seconds / daySeconds);
                seconds -= days * daySeconds;
                hours = Math.floor(seconds / hourSeconds);
                seconds -= hours * hourSeconds;
                minutes = Math.floor(seconds / minuteSeconds);
                seconds -= minutes * minuteSeconds;

                messageParts = [seconds + ' seconds'];
                updateDelay = 1000;
                if (minutes) {
                    messageParts.unshift(minutes + ' minutes');
                }
                if (hours) {
                    messageParts.unshift(hours + ' hours');
                    updateDelay = minuteSeconds * 1000;
                }
                if (days) {
                    messageParts.unshift(days + ' days');
                    updateDelay = hourSeconds * 1000;
                }
                messageParts.splice(2);

                $timerTextElement.text(messageParts.join(' '));

                isFinished = (isFuture && nowSeconds > epochSeconds) || (!isFuture && nowSeconds < epochSeconds);
                if (isFinished) {
                    if (opt_callback) {
                        opt_callback();
                    }
                } else {
                    setTimeout(updateMethod, updateDelay);
                }
            };
        updateMethod();
    };

    $vf.xmlEscape = function (content) {
        return content.replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    };

    /**
     * icon title tooltips
     */
    $vf.afterInit(function () {
        $('body').on('mouseenter', '.toolbar-icon[title], .icon[title]', function (e) {
            $(this).qtip({
                overwrite: false,
                show: {
                    event: e.type,
                    ready: true
                },
                content: {
                    text: false
                },
                style: {
                    classes: 'vf-title-tip'
                },
                position: {
                    /*target: 'mouse',
                    adjust: { x: 10, y: 0 },*/
                    viewport: $(window),
                    at: 'bottom middle',
                    my: 'top right'
                }
            });
        })
    }, null);

    /**
     * to relative url
     *
     * get the most relative url from the given absolute url
     */
    $vf.toRelativeURL = function (absoluteURL, opt_referenceURL) {
        var referenceURL = (typeof opt_referenceURL !== 'undefined') ? opt_referenceURL : window.location.pathname,
            linkParts = absoluteURL.split('/'),
            referenceParts = referenceURL.split('/'),
            relativeParts = [],
            sharedParts = [],
            iterations, i, linkPart, referencePart;

        iterations = Math.max(linkParts.length, referenceParts.length);
        for (i=0; i < iterations; ++i) {
            linkPart = linkParts[i];
            referencePart = referenceParts[i];

            if (linkPart === referencePart) {
                sharedParts.push(linkPart);
            }

            else if (typeof linkPart !== 'undefined') {
                relativeParts.push(linkPart);
            }
        }

        iterations = referenceParts.length - sharedParts.length;
        for (i=0; i < iterations; ++i) {
            relativeParts.unshift('..');
        }

        if (relativeParts.length === 0) {
            return '.';
        }
        else {
            return relativeParts.join('/');
        }
    };
    /* test it
    $vf.test_toRelativeURL = function (absolute, reference, expected) {
        var result = $vf.toRelativeURL(absolute, reference);
        if (expected !== result) {
            console.error('toRelativeURL failed test:', {
                absolute: absolute,
                reference: reference,
                expected: expected,
                result: result
            });
        }
        else {
            console.log('toRelativeURL passed test:', {
                absolute: absolute,
                reference: reference,
                expected: expected,
                result: result
            });
        }
    };

    $vf.test_toRelativeURL('/a/b/c/d', '/a/b', 'c/d');
    $vf.test_toRelativeURL('/a/b/c', '/a/b', 'c');
    $vf.test_toRelativeURL('/a/b', '/a/b/c/d', '../..');
    $vf.test_toRelativeURL('/a/b/c/d', '/a/b/e', '../c/d');
    $vf.test_toRelativeURL('/a/b', '/a/b', '.');
    */

}(window));
