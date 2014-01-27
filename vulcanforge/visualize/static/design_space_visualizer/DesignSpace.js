/*globals window, $, jQuery, $vf, getParameterByName, trace*/
$(parent).ready(function() {
    "use strict";

    $(function($, $vf) {
        if ($vf === undefined) {
            $vf = parent.window.$vf;
        }

        trace('designSpace in the house');

        var DesignVisualizer = function(config) {
            $.extend(this, config);

            this.init();
        }, containerIframe;

        if ( parent !== window ) {
            containerIframe = $(parent.document).find('iframe[name='+window.name+']');
            containerIframe.css('overflow', 'hidden');
        }

        DesignVisualizer.prototype = {

            topologyHolderE: null,
            $designSelector: null,
            contentHolderE: null,
            titleE: null,

            topologyData: null,
            currentId: null,
            serviceUrl: null,
            isLoading: false,

            dataPump: null,

            init: function() {

                this.currentId = getParameterByName('DesignSpace.currentElement', window.top) || getParameterByName('DesignSpace.currentElement');
                this.resourceUrl = getParameterByName('resource_url');

                trace( 'Current id: [' + this.currentId + ']' );
                trace( 'Resource URL: [' + this.resourceUrl + ']' );

                this.renderTopology();

            },

            renderTitle: function() {
                if (this.currentElement){
                    this.titleE = $('<h2/>', {
                        'html': this.currentElement.name,
                        'class': 'title'
                    });
                }

                /*        this.titleE.append($('<span/>', {
                 'class': 'topologyLocation',
                 'text': 'Source: ['+this.topologyLocation+']'
                 }))*/

                this.contentHolderE.append(this.titleE);
            },

            renderTopology: function() {
                var dataPump,
                    designId,
                    that = this,
                    _docType,
                    $designSelector;

                this.topologyHolderE = $('<div/>', {
                    id: 'topologyHolder'
                });

                this.contentHolderE.append(this.topologyHolderE);

                function projectMapper( data, request, cache ) {

                    var mappedDatas = [],
                        newElement;

                    if ( data ) {

                        newElement = {
                            id: data.id,
                            dataType: 'project',
                            properties: {
                                name: data.display_name,
                                state: data.state,
                                designDescriptors: data.designs
                            }

                        };

                        if ( cache ) {
                            cache.addEntity( 'project', newElement );
                        }
                        mappedDatas.push( newElement );

                    }

                    return mappedDatas;

                }

                function projectsMapper( data, request, cache ) {


                    var mappedDatas = [],
                        newElement;

                    if ( data ) {
                        $.each( data.design_projects, function(i) {
                            mappedDatas = mappedDatas.concat( projectMapper( data.design_projects[ i ], request, cache ) );
                        });
                    }

                    newElement = {
                        id: request.id,
                        dataType: 'projects',
                        properties: {
                            projects: mappedDatas.filter( function(el) {
                                return el.dataType === 'project';
                            })
                        }
                    };

                    if ( cache ) {
                        cache.addEntity( 'projects', newElement );
                    }

                    mappedDatas.push( newElement );

                    return mappedDatas;
                }

                function designMapper( data, request, cache ) {
                    var mappedDatas = [],
                        newDesignByUrl,
                        newDesignById,
                        properties;

                    if ( data && data.top_element ) {

                        properties = {
                            topElementId: data.top_element.id,
                            designId: data.design.id,
                            url: data.design.file_url
                        };

                        newDesignByUrl = {
                            id: data.design.file_url,
                            dataType: 'designByUrl',
                            properties: properties
                        };

                        newDesignById = {
                            id: data.design.id,
                            dataType: 'design',
                            properties: properties
                        };

                        mappedDatas = elementMapper( data.top_element, request, cache );

                    }

                    if ( cache ) {
                        cache.addEntity( 'design', newDesignById );
                        cache.addEntity( 'designByUrl', newDesignByUrl);
                    }

                    mappedDatas.push( newDesignById );

                    return mappedDatas;
                }

                /*                function designMapper( data, request, cache ) {
                 var mappedDatas = [], newElement = {};

                 if ( data ) {

                 newElement = {
                 id: data.id,
                 dataType: 'design',
                 properties: {
                 name: data.name
                 }
                 };

                 mappedDatas.push( newElement );

                 if ( cache ) {
                 cache.addEntity( 'element', newElement );
                 }

                 }

                 return mappedDatas;
                 }*/

                function _separateElementsByKind( mixed ) {
                    var results = {};

                    $.each( mixed, function (j,k) {
                        results [ k.dataType ] = results [ k.dataType ] || [];
                        results [ k.dataType ] = k;
                    });

                    return results;
                }

                function elementMapper( data, request, cache ) {

                    var mappedDatas = [],
                        validTypes = [
                            'Compound',
                            'Component',
                            'LocalComponent',
                            'Alternative',
                            'Optional',
                            'ComponentCategory'
                        ],
                        newElement,
                        parentCategory,
                        dataType;

                    trace("ElementMapper with data id " + data.id);
                    if ( data && data.id ) {

                        /* get data type */
                        dataType = data.$type || '';
                        if (dataType.substr(0, 16) === 'AVM.META.Design.') {
                            dataType = dataType.substr(16);
                        }
                        if (dataType === 'ComponentInstance') {
                            dataType = data.component_id ? 'Component': 'LocalComponent';
                        }
                        if (validTypes.indexOf(dataType) === -1){
                            dataType = 'DesignContainer';
                        }

                        newElement = {
                            id: data.id,
                            dataType: 'element',
                            properties: {
                                componentId: data.component_id,
                                /* componentVersion: data.ComponentVersion,*/
                                designId: data.design_id,
                                name: data.name,
                                type: dataType,
                                metadata: {},
                                indexId: data.index_id
                            }
                        };
                        mappedDatas.push( newElement );
                        if ( cache ) {
                            cache.addEntity( 'element', newElement );
                        }

                        if ( request && request.id === undefined ) {
                            request.id = data.id;
                        }

                        if ( data.children && data.children.length ) {

                            var childrenByComponentCategory = {},
                                nocategory = [],
                                newChildren = [];

                            parentCategory = data.id.split('::::')[1];
                            $.each( data.children, function (i, child)  {
                                if ( child.component_category && child.component_category !== parentCategory ) {
                                    if ( !childrenByComponentCategory[ child.component_category ] ) {
                                        childrenByComponentCategory[ child.component_category ] = {
                                            id: data.id + '::::' + child.component_category,
                                            $type: 'ComponentCategory',
                                            name: child.component_category,
                                            children: []
                                        };

                                        newChildren.push( childrenByComponentCategory[ child.component_category ] );
                                    }

                                    childrenByComponentCategory[ child.component_category ].children.push( child );

                                    mappedDatas.push( {
                                        dataType: 'RemoveRelation',
                                        type: 'embeds',
                                        nodes: [
                                            data.id,
                                            child.id
                                        ]
                                    } );

                                } else {
                                    nocategory.push( child );
                                }

                                data.children = nocategory;
                                data.children = data.children.concat( newChildren );

                            });

                            $.each( data.children, function (i)  {

                                mappedDatas = mappedDatas.concat( elementMapper( data.children[ i ], request, cache ) );

                                mappedDatas.push( {
                                    dataType: 'Relation',
                                    type: 'embeds',
                                    nodes: [
                                        data.id,
                                        data.children[ i ].id
                                    ]
                                } );
                            });
                        } else {

                            if ( data.children_ids ) {
                                $.each( data.children_ids, function (i)  {
                                    mappedDatas.push( {
                                        dataType: 'Relation',
                                        type: 'embeds',
                                        nodes: [
                                            data.id,
                                            data.children_ids[ i ]
                                        ]
                                    } );
                                });
                            }
                        }

                        if ( data.parent_id ) {
                            mappedDatas.push( {
                                dataType: 'Relation',
                                type: 'embeds',
                                nodes: [
                                    data.parent_id,
                                    data.id
                                ]
                            } );
                        }


                    }

                    return mappedDatas;
                }

                function RelationsIndex() {
                    var _indexes = {};

                    this.updateWith = function ( objectList ) {
                        $.each( objectList, function ( i, o ) {
                            var normalDirectionCollector,
                                reverseDirectionCollector,
                                e0_id, e1_id, type;

                            if ( o.dataType === 'Relation' ) {

                                type = o.type || 'embeds';

                                _indexes[ type ] = _indexes[ type ] || {};
                                _indexes[type].normal = _indexes[type].normal || {};     // normal direction: for finding b's for a (a->b)
                                _indexes[type].reverse = _indexes[type].reverse || {};     // reverse direction: for finding a's for b (a->b)

                                e0_id = o.nodes[0];
                                e1_id = o.nodes[1];

                                normalDirectionCollector = _indexes[type].normal[e0_id] = _indexes[type].normal[e0_id] || [];
                                reverseDirectionCollector = _indexes[type].reverse[e1_id] = _indexes[type].reverse[e1_id] || [];

                                if (  normalDirectionCollector.indexOf( e1_id ) === -1 ) {
                                    normalDirectionCollector.push( e1_id );
                                }

                                if ( reverseDirectionCollector.indexOf( e0_id ) === -1 ) {
                                    reverseDirectionCollector.push( e0_id );
                                }
                            }

                            if ( o.dataType === 'RemoveRelation' ) {

                                type = o.type || 'embeds';

                                _indexes[ type ] = _indexes[ type ] || {};
                                _indexes[type].normal = _indexes[type].normal || {};     // normal direction: for finding b's for a (a->b)
                                _indexes[type].reverse = _indexes[type].reverse || {};     // reverse direction: for finding a's for b (a->b)

                                e0_id = o.nodes[0];
                                e1_id = o.nodes[1];

                                normalDirectionCollector = _indexes[type].normal[e0_id] = _indexes[type].normal[e0_id] || [];
                                reverseDirectionCollector = _indexes[type].reverse[e1_id] = _indexes[type].reverse[e1_id] || [];

                                if (  normalDirectionCollector.indexOf( e1_id ) !== -1 ) {
                                    normalDirectionCollector.splice( normalDirectionCollector.indexOf( e1_id ), 1 );
                                }

                                if ( reverseDirectionCollector.indexOf( e0_id ) !== -1 ) {
                                    reverseDirectionCollector.splice( reverseDirectionCollector.indexOf( e0_id ), 1 );
                                }
                            }
                            /*if ( o.dataType === 'ProjectDesignRelation' ) {

                             _indexes[ 'ProjectDesignRelation' ] = _indexes[ 'ProjectDesignRelation' ] || {};

                             e0_id = o.nodes[0];
                             e1_id = o.nodes[1];

                             normalDirectionCollector = _indexes['ProjectDesignRelation'][e0_id] = _indexes['ProjectDesignRelation'][e0_id] || [];

                             if ( normalDirectionCollector.indexOf( e1_id ) == -1 ) {
                             normalDirectionCollector.push( e1_id );
                             }
                             }*/
                        } );
                    };

                    this.getRelationsFor = function ( element, type, dir ) {
                        if ( _indexes && _indexes[type] ) {
                            return _indexes[type][dir][element];
                        } else {
                            return null;
                        }
                    };

                    this.getDesignsForProject = function ( projectId ) {
                        if ( _indexes && _indexes.ProjectDesignRelation ) {
                            return _indexes.ProjectDesignRelation.projectId;
                        } else {
                            return null;
                        }
                    };

                }

                var  loadingSpinner = new $vf.PleaseWait('Loading details', this.topologyHolderE, 0.9);

                dataPump = this.dataPump = $vf.designSpaceDataPump = new $vf.DataPump({

                    indexes: {
                        relationsIndex: new RelationsIndex()
                    },
                    resourceUrl: this.resourceUrl,
                    serviceUrl: this.serviceUrl,
                    events: {
                        beforeLoad: function() {
                            this.isLoading = true;
                            trace('We will be pulling click condom up here.' );
                            loadingSpinner.update();
                            loadingSpinner.show();
                        },
                        afterLoad: function() {
                            this.isLoading = false;
                            trace('We will be taking click condom down.' );
                            loadingSpinner.hide();
                        }
                    },
                    loadParameterRenderer: function (serviceUrl, request) {
                        var results;

                        switch ( request.requestType ) {

                        case 'projects':

                            results =  {
                                url: serviceUrl + '/project/',
                                data: null
                            };

                            break;

                        case 'projectByUrl':

                            results =  {
                                url: serviceUrl + '/project/by_url?descend=2',
                                data: {
                                    url: request.id
                                }
                            };

                            break;

                        case 'designByUrl':

                            results =  {
                                url: serviceUrl + '/design/by_url?descend=1',
                                data: {
                                    url: request.id
                                }
                            };

                            break;

                        case 'design':

                            results =  {
                                url: serviceUrl + '/design/' + request.id,
                                data: {
                                    descend: 2
                                }
                            };

                            break;

                        case 'element':

                            if ( designId ) {
                                results =  {
                                    url: serviceUrl + '/design/' + designId + '/element/' + request.id,
                                    data: {
                                        descend: request.descend || 1
                                    }
                                };
                            } else {
                                throw 'Unknown design id.  Unable to process request for getting element.';
                            }

                            break;

                        }

                        return results;
                    },
                    resultsMappers: {
                        'projects': projectsMapper,
                        'designByUrl': designMapper,
                        'design': designMapper,
                        'element': elementMapper
                    }

                });


                this.topologyGraph = new $vf.TopologyVisualizer.Graph({
                    enableZoom: false,
                    dataPump: this.dataPump,
                    topologyHolderE: this.topologyHolderE,
                    autoResize: false,
                    scrollDirection: 'horizontal',
                    initialScale: getParameterByName('scaleValue') || 1,
                    clickHandlerAdder: function( node ) {

                        var handler = null;

                        if ( node.id !==  that.currentId ) {

                            if ( node.type === 'Component' ) {

                                handler = function( ) {
                                    top.location.href = '/exchange/components/' + this.componentId;
                                };

                            } else {

                                handler = function( ) {
                                    var newUrl = location.pathname + '?resource_url=' + encodeURIComponent(that.resourceUrl) + '&DesignSpace.currentElement=' + this.id + '&scaleValue=' + that.topologyGraph.scaleValue;
                                    if ( window !== window.top ) {
                                        if ( $(window.top.document).find('body.fullscreen-vis').length ) {
                                            window.top.history.pushState(null, null, window.top.location.pathname + '?resource_url=' + encodeURIComponent(that.resourceUrl) + '&DesignSpace.currentElement=' + this.id + '&scaleValue=' + that.topologyGraph.scaleValue);
                                        } else {
                                            window.top.history.pushState(null, null, window.top.location.pathname + '?DesignSpace.currentElement=' + this.id + '&scaleValue=' + that.topologyGraph.scaleValue);
                                        }
                                    }

                                    location.replace( newUrl );
                                    //trace(newUrl);
                                };

                            }

                        }

                        return handler;
                    },
                    nodeCustomizer: function( ) {
                        var that = this,
                            nodeE = this.nodeE,
                            refId = this.indexId;

                        if ( $vf.ArtifactInfoPanel ) {

                            if ( refId ) {
                                //extraURI = "&refId=" + refId;
                                var infoButtonE = $( '<div/>', {
                                    'class': 'infoButton'
                                } );

                                that.infoPanel = new $vf.ArtifactInfoPanel( {
                                    parentClickURL: null,
                                    refId: refId,
                                    infoTriggerE: infoButtonE
                                } );

                                nodeE.append( infoButtonE );
                            }
                        }
                    }
                });

                function _determineDocTypeFromUrl( url ) {
                    var result = null,
                        projectIndex = -1 ,
                        designIndex = -1,
                        queryIndex,
                        pathUrl;

                    function extMatches (ext) {
                        return pathUrl.substr(-ext.length) === ext;
                    }

                    if (url !== undefined && url !== '') {
                        queryIndex = url.lastIndexOf('?');
                        pathUrl = queryIndex === -1 ? url : url.substr(0, queryIndex);

                        if (extMatches('.project.json')) {
                            result = 'project';
                        } else if (extMatches('.metadesign.json') || extMatches('.adm')) {
                            result = 'design';
                        }
                    }
                    return result;
                }

                var projectsCollection = $vf.designProjectCollection && $vf.designProjectCollection[ this.serviceUrl ]|| null,
                    renderProjectsCollection = function( projectsCollection ) {
                        if ( projectsCollection.properties &&
                            projectsCollection.properties.projects &&
                            projectsCollection.properties.projects.length ) {
                            $designSelector = $( '<select name="selection" id="design-selection" tabindex="2"/>' );
                            var $titleE = $( '<div/>', {
                                    text: 'Topology of',
                                    'class': 'topologyTitle'
                                } ),
                                $optionGroup, $option;

                            that.topologyHolderE.prepend( $titleE.append( $designSelector ) );

                            $.each( projectsCollection.properties.projects, function( i,e ) {

                                if ( e.dataType === 'project') {

                                    $optionGroup = new $( '<optgroup/>', {
                                        label: e.properties.name
                                    } );

                                    if ( e.properties.designDescriptors ) {
                                        $.each( e.properties.designDescriptors, function( j, k ) {
                                            $option = new $( '<option/>', {
                                                'value': k.id,
                                                'text': k.display_name
                                            });

                                            if ( designId && designId === k.id ) {
                                                $option.attr( 'selected' , 'selected' );
                                            }

                                            $optionGroup.append( $option );
                                        } );
                                    }

                                    $designSelector.append( $optionGroup );

                                }

                            });

                            $designSelector.change( function() {
                                var newId = $(this).val();
                                if ( newId !== designId ) {
                                    that.dataPump.query( new that.dataPump.Transaction( [
                                        {
                                            id: newId,
                                            requestType: 'design',
                                            dataType: 'design'
                                        }], function (results, status ) {
                                            trace( 'Loading newly selected design status is [' + status + ']' );
                                            var design = results && results[0];
                                            top.location.href = design.properties.url;
                                        }
                                    ));
                                }
                            });

                        }
                    };

                if ( !projectsCollection ) {
                    this.dataPump.query( new this.dataPump.Transaction( [
                        {
                            id: this.serviceUrl,
                            requestType: 'projects',
                            dataType: 'projects'
                        }], function (results, status ) {
                            trace( 'Loading projects status is [' + status + ']' );

                            $vf.designProjectCollection = $vf.designProjectCollection || [];
                            $vf.designProjectCollection[ that.serviceUrl ] = projectsCollection = results[0];

                            renderProjectsCollection( projectsCollection );
                        }
                    ));
                } else {
                    renderProjectsCollection( projectsCollection );
                }
                // Figuring out if we should load project or design
                if ( this.resourceUrl ) {
                    _docType = _determineDocTypeFromUrl( this.resourceUrl );
                } else {
                    throw 'Missing or bad resource_url.';
                }

                if ( _docType === 'design') {

                    // loading design by url
                    this.dataPump.query( new this.dataPump.Transaction( [
                        {
                            id: this.resourceUrl,
                            requestType: 'designByUrl',
                            dataType: 'design'
                        } ], function ( results, status ) {

                        trace( 'First load status is [' + status + ']' );

                        var design = results[ 0 ];

                        designId = design.properties.designId;
                        if ( !that.currentId ) {
                            that.currentId = design.properties.topElementId;
                        }

                        trace( 'Design id is: [' + designId + '], Current Id is: [' + that.currentId + ']');

                        if ( $designSelector ) {
                            $designSelector.find('option[value="' + designId + '"]').attr('selected', 'selected');
                        }

                        function reloader( ) {
                            window.top.removeEventListener('popstate', reloader);
                            if ( location ) {
                                location.reload();
                            }
                        }
                        window.top.addEventListener('popstate', reloader);


                        that.topologyGraph.currentComponentId = that.currentId;

                        var nodeId = that.currentId.split('::::')[0];

                        that.dataPump.query( new dataPump.Transaction([{
                            id: nodeId,
                            requestType: 'element',
                            forceLoad: true
                        }], function( elements, status) {
                                trace( 'Second load status is [' + status + ']' );

                                if ( elements ) {
                                    $.each( elements, function( i,e ) {
                                        if ( e.id === that.currentId ) {
                                            that.topologyGraph.addCenterElement( e );
                                            return;
                                        }
                                    });
                                } else {
                                    throw 'Could not load current element.';
                                }
                            }
                        ) );

                    }));

                }

            },

            renderProperties: function() {
                var count = 0,
                    metaDataListE,
                    liE;

                if (this.currentElement && this.currentElement.metadata) {
                    metaDataListE = this.metaDataListE = $('<ul/>', {
                        'class': 'metadataList'
                    });

                    $.each(this.currentElement.metadata, function(k, v) {
                        liE = $('<li/>');

                        metaDataListE.append(liE);

                        liE.append($('<div/>', {
                            'class': 'labelContainer',
                            'text': k
                        }));

                        liE.append($('<div/>', {
                            'class': 'valueContainer',
                            'text': v.value + ' ' + v.unit
                        }));

                        count++;

                    });

                    if (count) {
                        this.contentHolderE.append($('<h3>Properties</h3>'));
                        this.contentHolderE.append(this.metaDataListE);
                    }
                }
            },

            renderArtifacts: function() {
                var count = 0,
                    liE,
                    afListE;

                if (this.currentElement && this.currentElement.artifacts) {
                    afListE = this.afListE = $('<ul/>', {
                        'class': 'artifactList'
                    });

                    $.each(this.currentElement.artifacts, function(k, v) {
                        liE = $('<li/>');

                        afListE.append(liE);

                        liE.append($('<a/>', {
                            'href': v,
                            'title': k,
                            'text': k,
                            'target': '_top'
                        }));

                        count++;

                    });

                    if (count) {
                        this.contentHolderE.append($('<h3>Artifacts</h3>'));
                        this.contentHolderE.append(this.afListE);
                    }
                }
            },

            render: function() {
                this.renderTitle();
                this.renderTopology();
                this.renderProperties();
                this.renderArtifacts();

                if ( parent !== window ) {
                    containerIframe.height($(document).height());
                }
            }
        };

        $vf.DesignVisualizer = DesignVisualizer;

    }(
        jQuery,
        parent.window.$vf
    ));
});