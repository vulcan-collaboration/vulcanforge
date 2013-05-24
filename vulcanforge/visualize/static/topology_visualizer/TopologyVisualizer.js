/*globals window, $, jQuery, $vf, getParameterByName, Raphael, trace*/

$(parent).ready(function() {
    "use strict";

    $(function ( $, $vf ) {

        if ($vf === undefined) {
            $vf = parent.window.$vf;
        }

        /**
         *
         * @author Naba Bana
         *
         * TopologyVisualizer
         *
         * Defining namespace. It is the only global object.
         *
         */

        var TopologyVisualizer = {}, containerIframe;

        trace( 'TopologyVisualizer is in the house' );

        if ( parent !== window ) {
            containerIframe = $(parent.document).find('iframe[name='+window.name+']');
        }

        function resizeIframe() {
            if ( parent !== window ) {
                containerIframe.height($(document).height());
            }
        }

        TopologyVisualizer.Graph = function ( config ) {

            $.extend( this, config );
            this.init();
        };

        TopologyVisualizer.Graph.prototype = {

            MAX_DEPTH: 1,
            MAX_HEIGHT: Infinity,

            topologyHolderE: null,
            containerElement: null,
            dataProvider: null,
            currentComponentId: null,

            autoResize: true,
            enableZoom: true,

            relationsIndex: null,

            exchangeURIPrefix: null,
            localComponentURIPrefix: null,

            nodeCollector: null,

            titleE: null,
            zoomSliderE: null,

            scaleValue: 1,

            scrollDirection: 'auto',

            hasContent: false,

            clickHandlerAdder: function() {},
            nodeCustomizer: function() {},

            init: function () {
                if ( this.topologyHolderE && this.dataPump ) {

                    var that = this;

                    this.containerElement = $( '<div/>', {
                        'class': 'graphContainer'
                    } );

                    this.topologyHolderE.addClass( 'topologyHolder' );
                    this.topologyHolderE.append( this.containerElement );

                    this.relationsIndex = this.dataPump.indexes.relationsIndex;

                    this.nodeCollector = $( '<div/>', {
                        'class': 'nodeCollector'
                    } );


                    this.containerElement.append( this.nodeCollector );

                    if ( that.autoResize ) {
                        this.refreshSizeAndScroller();
                        $( window ).resize( function () {
                            that.refreshSizeAndScroller();
                        } );
                    } else {
                        this.refreshSizeAndScroller( true );
                        $( window ).resize( function () {
                            that.refreshSizeAndScroller( true );
                        } );
                    }

                }
            },

            addCenterElement: function( elementDescriptor ) {

                var that = this;
                var relationsIndex = this.relationsIndex;

                if ( elementDescriptor ) {

                        var e = elementDescriptor.properties;
                        trace('AddElement [' + elementDescriptor.id + ']');

                        if ( e.type === 'ExchangeComponent' ) {
                            if ( e.AVMID ) {
                                if ( that.exchangeURIPrefix ) {
                                    e.uri = that.exchangeURIPrefix + e.AVMID + '/reveal';
                                } else {
                                    e.uri = e.AVMID + '/reveal';
                                }
                            }
                        } else {
                            e.uri = that.localComponentURIPrefix + '&DesignSpace.currentElement=' + elementDescriptor.id;
                        }

    
                        var centerNode = new TopologyVisualizer.Node($.extend({
                            id: elementDescriptor.id,
                            graph: that
                        }, e), true );
                        centerNode.addToGraph( that );
                        centerNode.renderTo( that.nodeCollector );
    
                        if ( relationsIndex.getRelationsFor( that.currentComponentId, 'embeds', 'reverse' ) ) {
                            centerNode.nodeE.before( $( '<div/>', {
                                'class': 'divider heaven',
                                text: 'Others embedding that component'
                            } ) );
    
                            var upperSubTree = centerNode.addSubTree( 'UPPER', {
                                type: 'embeds',
                                dir: 'reverse'
                            } );
    
                            upperSubTree.expandToLevel( that.MAX_HEIGHT );
    
                        }
    
                        if ( relationsIndex.getRelationsFor( that.currentComponentId, 'embeds', 'normal' ) ) {
    
                            centerNode.nodeE.after( $( '<div/>', {
                                'class': 'divider base',
                                text: 'Components embedded'
                            } ) );
    
                            var lowerSubTree = centerNode.addSubTree( 'LOWER', {
                                type: 'embeds',
                                dir: 'normal'
                            } );
    
                            if ( lowerSubTree) {
                                lowerSubTree.expandToLevel( that.MAX_DEPTH );
                            }
    
                        }
    
                        centerNode.nodeContainerE.disableSelection();

                        if ( !that.hasContent ) {

                            if ( that.enableZoom ) {
                                that.zoomSliderE = $( '<div/>', {
                                    'class': 'zoomSlider'
                                } ).slider( {
                                        orientation: "vertical",
                                        min: 6,
                                        max: 15,
                                        value: 10,
                                        slide: function ( event, ui ) {
                                            that.scale( ui.value / 10 );
                                        }
                                    } );
                                that.zoomSliderContainerE = $( '<div/>', {
                                    'class': 'zoomSliderContainer'
                                } );

                                that.zoomSliderContainerE.append( that.zoomSliderE );
                                that.topologyHolderE.prepend( that.zoomSliderContainerE );

                                // Setting initial zoom level

                                that.scale( that.initialScale );
                                that.zoomSliderE.slider( 'value', that.initialScale*10 );

                            }

                            // Setting up scrolling by grabbing

                            that.containerElement.dragscrollable({
                                dragSelector: '.nodeCollector',
                                preventDefault: false,
                                acceptPropagatedEvent: true
                            });

                            that.nodeCollector.mousedown( function() {
                                that.nodeCollector.addClass('being-grabbed');
                            });

                            that.nodeCollector.mouseup( function() {
                                that.nodeCollector.removeClass('being-grabbed');
                            });


                            that.hasContent = true;

                        }
    
                    }

            },

            scale: function ( s ) {
                if ( this.nodeCollector && this.scaleValue !== s) {
                    this.nodeCollector.css( {
                        '-webkit-transform': 'scale(' + s + ')',
                        '-moz-transform': 'scale(' + s + ')',
                        'transform': 'scale(' + s + ')'
                    } );

                    this.scaleValue = s;

                    //trace(this.nodeCollector.position().top+' '+this.containerElement.scrollTop()+' '+this.nodeCollector.height());
                    var nodeCollectorOffset = (s > 1) ? this.nodeCollector.height() * (s - 1) : 0;
                    this.nodeCollector.css( 'top', nodeCollectorOffset );
                    this.refreshSizeAndScroller( true );
                }
            },

            refreshSizeAndScroller: function ( /*doNotResize*/ ) {
                if ( this.containerElement && this.titleE ) {
    //                this.containerElement.removeOverscroll();
    /*                if ( false && !doNotResize ) {
                        var d = $( 'body' );
                        var w = d.innerWidth();
                        var h = d.innerHeight();
                        //while (w != this.containerElement.outerWidth() || h != this.containerElement.outerHeight()) {
                        this.containerElement.outerWidth( w );
                        this.containerElement.outerHeight( h );
                        //trace('Recalculating size: '+w+' '+h)
                        // }
                    }*/
                    this.containerElement.height(this.nodeCollector.height() * this.scaleValue + 30);
    /*                this.containerElement.overscroll( {
                        hoverThumbs: true,
                        persistThumbs: false,
                        cancelOn: '.noDrag',
                        direction: this.scrollDirection
                    } );*/

                    resizeIframe();

                }
            },

            remove: function () {
            }
        };

        TopologyVisualizer.CurvePort = function ( config ) {
            $.extend( this, config );
            this.create();
        };

        TopologyVisualizer.CurvePort.prototype = {
            hostNode: null,
            type: null,
            state: null,
            acceptedCurves: null,
            portE: null,

            isOn: false,
            isExpandable: true,
            subTree: null,

            expandButtonE: null,
            collapseButtonE: null,

            padding: 40,

            create: function () {

                var that = this;

                this.portE = $( '<div/>', {
                    'class': 'port'
                } );

                this.expandButtonE = $( '<div/>', {
                    'class': 'expandButton',
                    title: 'Expand',
                    click: function () {
                        if ( that.subTree ) {
                            that.subTree.expand();
                        }
                    }
                } );

                this.collapseButtonE = $( '<div/>', {
                    'class': 'collapseButton noDrag',
                    title: 'Collapse',
                    click: function () {
                        if ( that.subTree ) {
                            that.subTree.collapse();
                        }
                    }
                } );

                this.expandButtonE.hide();
                this.collapseButtonE.hide();

                this.portE.append( this.expandButtonE );
                this.portE.append( this.collapseButtonE );

                if ( this.type ) {
                    this.portE.addClass( this.type );
                }
            },

            on: function () {
                if ( !this.isOn ) {
                    this.isOn = true;
                    this.draw();
                }
            },

            off: function () {
                if ( this.isOn ) {
                    this.isOn = false;
                    this.draw();
                }
            },

            expandable: function () {
                if ( !this.isExpandable ) {
                    this.isExpandable = true;
                    this.draw();
                }
            },

            collapsible: function () {
                if ( this.isExpandable ) {
                    this.isExpandable = false;
                    this.draw();
                }
            },

            draw: function () {
                if ( this.isOn ) {
                    this.portE.addClass( 'on' );

                    if ( this.subTree ) {
                        if ( this.isExpandable ) {

                            this.portE.addClass( 'expandable' );
                            this.portE.removeClass( 'collapsible' );

                            this.collapseButtonE.hide();
                            this.expandButtonE.show();
                        } else {

                            this.portE.removeClass( 'expandable' );
                            this.portE.addClass( 'collapsible' );

                            this.collapseButtonE.show();
                            this.expandButtonE.hide();
                        }
                    } else {
                        this.portE.removeClass( 'expandable' );
                        this.portE.removeClass( 'collapsible' );

                        this.expandButtonE.hide();
                        this.collapseButtonE.hide();
                    }

                } else {
                    this.portE.removeClass( 'on' );

                    this.expandButtonE.hide();
                    this.collapseButtonE.hide();
                }
            }
        };

        TopologyVisualizer.Curve = function ( config ) {
            $.extend( this, config );
        };

        TopologyVisualizer.Curve.prototype = {
            fromPort: null,
            toPort: null,
            data: null,
            style: null,
            paper: null,
            paperHolder: null,
            draw: function () {

                var s;

                //        trace('Drawing curve');
                if ( this.fromPort && this.toPort ) {

                    if (this.toPort.subTree) {
                        s = this.toPort.subTree.parentNode.graph.scaleValue;
                    } else if (this.fromPort.subTree) {
                        s = this.fromPort.subTree.parentNode.graph.scaleValue;
                    } else {
                        s = 1;
                    }

                    var bottomPort = this.toPort;
                    var topPort = this.fromPort;
                    if ( bottomPort && topPort ) {
                        var pos1 = topPort.portE.offset();
                        var pos0 = bottomPort.portE.offset();

                        var paperOffset = this.paperHolder.offset();

                        pos0.top /= s;
                        pos0.left /= s;
                        pos1.top /= s;
                        pos1.left /= s;
                        paperOffset.top /= s;
                        paperOffset.left /= s;

                        pos0.top = pos0.top - paperOffset.top + bottomPort.portE.height();
                        pos0.left = pos0.left - paperOffset.left;
                        pos1.top = pos1.top - paperOffset.top;
                        pos1.left = pos1.left - paperOffset.left;

                        var w1 = topPort.portE.width();
                        var w0 = bottomPort.portE.width();

                        var p0x = pos0.left + w0 / 2 + 0.5;
                        var p0y = pos0.top;

                        var p1x = pos1.left + w1 / 2 + 0.5;
                        var p1y = pos1.top;

                        /*if (jQuery.browser.mozilla) {         // won't solve curve-antialiasing problem in FF
                         p0x += .5;
                         p1x += .5;
                         }*/

                        var curvePath = 'M' + (p0x) + ' ' + p0y +
                            ' C' + (p0x) + ' ' + (p0y + bottomPort.padding) + ' ' + (p1x) + ' ' + (p1y - topPort.padding) + ' ' + (p1x) + ' ' + (p1y) +
                            ' L' + (p1x) + ' ' + (p1y);

                        var curve = this.curve = this.paper.path( curvePath );

                        curve.attr( {
                            stroke: '#333',
                            'stroke-width': 1
                        } );

                    }
                }
            }
        };


        TopologyVisualizer.Node = function ( config, isCurrent ) {
            $.extend( this, config );
            this.isCurrent = isCurrent;
            this.create();
            this.draw();
        };

        TopologyVisualizer.Node.prototype = {

            id: null,
            name: null,
            category: null,
            uri: null,

            nodeE: null,

            paperHolder: null,
            nodeContainerE: null,
            abovePaper: null,
            topPort: null,
            bottomPort: null,

            graph: null,

            subTrees: null,

            curves: null,

            isCurrent: null,

            onclick: null,

            create: function () {
                var that = this;

                var nodeContainerE = this.nodeContainerE = $( '<div/>', {
                    'class': 'nodeContainer' + (this.isCurrent ? ' current' : '')
                } );

                var paperHolder = this.paperHolder = $( '<div/>', {
                    'class': 'paperHolder'
                } );

                nodeContainerE.prepend( paperHolder );

                this.paper = new Raphael( paperHolder[0], 1, 1 );


                var nodeE = this.nodeE = $( '<div/>', {
                    'class': 'node' + (this.isCurrent ? ' current' : '')
                } );

                var abovePaper = this.abovePaper = $( '<div/>', {
                    'class': 'abovePaper'
                } );

                nodeContainerE.append( abovePaper );
                abovePaper.append( nodeE );

                if ( this.metaKind ) {
                    nodeE.addClass( this.metaKind );
                }

                if ( this.type ) {
                    nodeE.addClass( this.type );
                }

                var core = $( '<div/>', {
                    'class': 'core noDrag',
                    'title': that.isCurrent ? '' : 'Navigate to [' + that.name + ']'
                } );

                this.graph.nodeCustomizer.call( this );

                this.onclick = this.graph.clickHandlerAdder( this );

                if ($.isFunction( that.onclick )) {
                    core.click( function (  ) {
                        that.onclick.call( that );
                    } );

                    core.addClass( 'clickable' );
                }

                core.append( $( '<div class="marker"/>') );
                core.append( $( '<span class="name">' + ( this.name || '' ) + '</span>' ) );

                nodeE.append( core );

                if ( this.category && this.category.id !== '' ) {
                    nodeE.append( $( '<div/>', {
                        'class': 'category noDrag',
                        'title': 'Discover category',
                        text: this.category.label,
                        click: function (  ) {
                            top.location.href = '/component_search/?term_id=' + that.category.id;
                        }
                    } ) );
                }

                this.topPort = new TopologyVisualizer.CurvePort( {
                    type: 'top'
                } );

                this.bottomPort = new TopologyVisualizer.CurvePort( {
                    type: 'bottom'
                } );

                if ( this.isCurrent ) {
                    this.topPort.padding = 70;
                    this.bottomPort.padding = 80;
                }

                this.nodeE.prepend( this.topPort.portE );
                this.nodeE.append( this.bottomPort.portE );

            },

            drawCurves: function () {

                if ( this.subTrees ) {
                    this.paper.setSize( this.nodeContainerE.width(), this.nodeContainerE.height() );
                    this.paper.clear();
                    //            trace('NodeContainer dimensions: '+this.nodeContainerE.width()+' '+this.nodeContainerE.height());
                    var that = this;
                    this.curves = this.curves || {};
                    $.each( this.subTrees, function ( i, sT ) {
                        that.curves[sT.direction] = {};

                        if ( sT.expanded ) {
                            $.each( sT.nodesById, function ( n_id, node ) {
                                if ( node ) {
                                    var curve = new TopologyVisualizer.Curve( {
                                        paper: that.paper,
                                        paperHolder: that.paperHolder,
                                        toPort: (sT.direction === 'LOWER') ? that.bottomPort : node.bottomPort,
                                        fromPort: (sT.direction === 'LOWER') ? node.topPort : that.topPort
                                    } );
                                    that.curves[n_id] = curve;
                                    curve.draw();
                                }
                            } );
                        }

                    } );

                } else {
                    this.paper.setSize( 0, 0 );
                    this.paper.clear();
                    this.curves = null;
                }

                this.updateUpstreamCurves();
            },

            updateUpstreamCurves: function () {
                if ( this.parentSubTrees ) {
                    $.each( this.parentSubTrees, function ( i, st ) {
                        st.parentNode.drawCurves();
                    } );
                }
            },

            draw: function () {
                //        trace('Drawing node ['+this.id+']');
                if ( this.subTrees ) {
                    $.each( this.subTrees, function ( i, st ) {
                        st.draw();
                    } );
                }
                this.drawCurves();
                //if (this.paper) this.paper.renderfix();
            },

            addToGraph: function ( graph ) {
                this.graph = graph;
                //graph.nodesById[this.id] = this;

                if ( this.parentSubTrees ) {
                    var that = this;
                    $.each( this.parentSubTrees, function ( i, st ) {
                        that.addSubTree( st.direction, st.relationShip, st.level + 1 );
                    } );
                }
            },

            addToSubtree: function( subtree ) {

                subtree.nodesById[this.id] = this;

                if ( this.parentSubTrees ) {
                    var that = this;
                    $.each( this.parentSubTrees, function ( i, st ) {
                        that.addSubTree( st.direction, st.relationShip, st.level + 1 );
                    } );
                }
            },

            addSubTree: function ( direction, relationShip, level ) {

                var result = null;

                if ( this.subTrees && this.subTrees[direction] ) {
                    return this.subTrees[direction];
                }

                if ( direction && relationShip && this.graph && this.graph.relationsIndex && this.graph.relationsIndex.getRelationsFor( this.id, relationShip.type, relationShip.dir ) ) {

                    this.subTrees = this.subTrees || {};

                    switch ( direction ) {

                    case 'UPPER':
                        result = this.subTrees.UPPER = new TopologyVisualizer.SubTree( {
                            parentNode: this,
                            relationShip: relationShip,
                            parentPort: this.topPort,
                            direction: direction,
                            level: (level || 0),
                            graph: this.graph
                        } );
                        this.abovePaper.prepend( this.subTrees.UPPER.subTreeE );
                        break;

                    case 'LOWER':
                        result = this.subTrees.LOWER = new TopologyVisualizer.SubTree( {
                            parentNode: this,
                            relationShip: relationShip,
                            parentPort: this.bottomPort,
                            direction: direction,
                            level: (level || 0),
                            graph: this.graph
                        } );
                        this.abovePaper.append( this.subTrees.LOWER.subTreeE );
                        break;

                    }
                }
                return result;
            },

            renderTo: function ( container ) {
                if ( this.nodeContainerE && container ) {
                    container.append( this.nodeContainerE );
                }
                this.drawCurves();
            },

            remove: function () {
                if ( this.subTrees ) {
                    $.each( this.subTrees, function ( i, st ) {
                        st.remove();
                    } );
                }
                this.nodeContainerE.remove();
            },

            hide: function () {
                this.nodeContainerE.hide();
            },

            show: function () {
                this.nodeContainerE.show();
            }

        };

        TopologyVisualizer.SubTree = function ( config ) {
            $.extend( this, config );
            this.create();
        };

        TopologyVisualizer.SubTree.prototype = {
            parentNode: null,
            nodeIds: null,
            expanded: false,
            subTreeE: null,
            direction: null,
            parentPort: null,
            relationShip: null,
            level: 0,
            nodesById: null,

            create: function () {
                this.subTreeE = $( '<div/>', {
                    'class': 'subTreeHolder ' + this.direction
                } );

                this.nodesById = {};
                if ( this.parentPort ) {
                    this.parentPort.subTree = this;
                    this.parentPort.on();
                }

                if ( this.parentNode && this.parentNode.graph && this.parentNode.graph.relationsIndex && this.relationShip ) {
                    this.nodeIds = this.parentNode.graph.relationsIndex.getRelationsFor( this.parentNode.id, this.relationShip.type, this.relationShip.dir );
                }

            },

            expand: function () {
                if ( !this.expanded ) {
                    this.expanded = true;
                    this.draw();
                }
                if ( this.parentPort ) {
                    this.parentPort.collapsible();
                }
                this.parentNode.graph.refreshSizeAndScroller( true );
            },

            expandToLevel: function ( levelLimit ) {
                if ( this.level < levelLimit ) {
                    this.expand();
                    var that = this;
                    $.each( this.nodeIds, function ( i, nodeId ) {
                        var node = that.nodesById[nodeId];
                        if ( node && node.subTrees && node.subTrees[that.direction] ) {
                            node.subTrees[that.direction].expandToLevel( levelLimit );
                        }
                    } );
                }
            },

            collapse: function () {
                if ( this.expanded ) {
                    this.expanded = false;
                    this.draw();
                }

                if ( this.parentPort ) {
                    this.parentPort.expandable();
                }
                this.parentNode.graph.refreshSizeAndScroller();
            },

            draw: function () {
                if ( this.nodeIds && this.parentNode && this.parentNode.graph ) {

                    var that = this,
                        transaction;
                    if ( this.expanded ) {

                        //expanding
                        trace("Expanding [" + that.nodeIds.join(', ') + "]");
                        var dataPump = this.parentNode.graph.dataPump,
                            requests,
                            loadData = false;

                        $.each( this.nodeIds, function ( i, n_id ) {
                            var existingNode = that.nodesById[n_id];
                            if ( !existingNode ) {
                                loadData = true;
                            } else {
                                existingNode.show();
                                existingNode.draw();
                            }
                        });

                        if ( loadData ) {
                            /* query children from parent */
                            requests = [{
                                id: that.parentNode.id.split('::::')[0],
                                requestType: 'element',
                                descend: 1,
                                forceLoad: true
                            }];


                            transaction = new dataPump.Transaction( requests,
                                function( elements, status ) {
                                    var subRequests, subTransaction;
                                    if ( transaction.withErrors ) {
                                        that.collapse();
                                        throw 'Could not load elements.';
                                    } else {
                                        subRequests = $.map(that.nodeIds, function(nodeId, i){
                                            return {
                                                id: nodeId,
                                                requestType: 'element',
                                                descend: 0
                                            };
                                        });
                                        subTransaction = new dataPump.Transaction(
                                            subRequests,
                                            function(elements, status) {
                                                $.each( elements, function( i, element) {
                                                    trace("Element [" + element.id + "]");
                                                    var nodeDescriptor = element.properties;
                                                    if ( nodeDescriptor ) {
                                                        nodeDescriptor.id = element.id;
                                                        nodeDescriptor.graph = that.graph;
                                                        nodeDescriptor.parentSubTrees = nodeDescriptor.parentSubTrees || {};
                                                        nodeDescriptor.parentSubTrees[that.direction] = that;
                                                        var node = new TopologyVisualizer.Node( nodeDescriptor );
                                                        node.addToSubtree( that );
                                                        switch ( that.direction ) {
                                                            case 'UPPER':
                                                                node.bottomPort.on();
                                                                break;

                                                            case 'LOWER':
                                                                node.topPort.on();
                                                                break;
                                                        }
                                                        node.renderTo( that.subTreeE );
                                                    }
                                                });
                                                that.draw();
                                                that.parentNode.drawCurves();
                                            }
                                        );
                                        dataPump.query( subTransaction );
                                    }
                                }
                            );

                            dataPump.query( transaction );
                        }

                    } else {

                        // collapsing

                        if ( this.nodeIds ) {
                            $.each( this.nodeIds, function ( i, n_id ) {
                                var node = that.nodesById[n_id];
                                if ( node ) {
                                    node.hide();
                                    that.parentNode.drawCurves();
                                }
                            } );
                        }
                    }
                }
            },

            remove: function () {
                this.collapse();
                this.subTreeE.remove();
            }

        };

        $vf.TopologyVisualizer = TopologyVisualizer;

    }(
        jQuery,
        parent.window.$vf
    ));
});