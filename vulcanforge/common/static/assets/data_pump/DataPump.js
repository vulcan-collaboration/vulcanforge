/*globals window, $, jQuery, $vf, getParameterByName, Raphael, trace*/

$(parent).ready(function() {
    $(function ( $, $vf ) {
        "use strict";

        if ($vf === undefined) {
            $vf = parent.window.$vf;
        }

        trace('DataPump in the house');

        var _countOfBeingLoadedTransactions=0;

        function DataPump(config) {

            var that = this,
                cache;

            cache = new function() {
                this.collections = {};
                this.addEntity = function( type, entity ) {
                    this.collections[ type ] = cache.collections[ type ] || {};
                    this.collections[ type ][ entity.id ] = entity
                };
            };

            $.extend( that, new window.EventDispatcher() );

            if ( config.events ) {
                $.each( config.events, function(i, e) {
                    if ( $.isFunction( e ) ) {
                        that.addEventListener( i, e );
                    }
                });

                delete config.events;
            }

            this.indexes = config.indexes;

            function _loadingOneTransaction() {
                if ( _countOfBeingLoadedTransactions === 0) {
                    that.dispatchEvent( 'beforeLoad' );
                    trace( 'Loading some data.');
                }

                _countOfBeingLoadedTransactions += 1;

                if ( status === false ) {
                    that.dispatchEvent( 'afterLoad' );
                }

            }

            function _loadingOfOneTransactionComplete() {
                _countOfBeingLoadedTransactions -= 1;
                if ( _countOfBeingLoadedTransactions === 0) {
                    that.dispatchEvent( 'afterLoad' );
                    trace( 'Not loading data anymore');
                }
            }

            function query( _transaction ) {
                var transaction = _transaction || new Transaction([{}]), // blank transaction
                    accumulatedResponse = [];

                $.each( transaction.requests, function( i, request ) {

                    trace("Data pump query for request with id [" + request.id + ']');
                    if ( request &&
                         ( request.forceLoad !== true &&
                         request.requestType &&
                         cache.collections[ request.requestType ] &&
                         cache.collections[ request.requestType ][ request.id ]) ) {

                        // From cache
                        request.results = [cache.collections[ request.requestType ][ request.id ]];
                        transaction.processedRequests.push( request );
                        accumulatedResponse = accumulatedResponse.concat( request.results );
                        if ( transaction.requests.length === transaction.processedRequests.length ) {
                            if ( $.isFunction( transaction.completed ) ) {
                                transaction.completed.call( transaction, accumulatedResponse, 'success' );
                            }
                        }

                    } else {
                        // Now we have to load
                        if (config.serviceUrl) {

                            if ( $.isFunction(config.loadParameterRenderer) ) {
                                try {
                                    request.loadParams = config.loadParameterRenderer(
                                        config.serviceUrl,
                                        request,
                                        config.resourceUrl
                                    );

                                    if ( !request.requestType ) {
                                        request.erroneous = true;
                                        transaction.dispatchEvent( 'loadError', request );
                                        transaction.withErrors = true;
                                    } else {
                                        $.ajax({
                                        url: request.loadParams.url,
                                        data: request.loadParams.data,
                                        requestType: 'json',
                                        beforeSend: function() {
                                            if ( transaction.countOfPendingRequests === 0 ) {
                                                _loadingOneTransaction();
                                            }
                                            transaction.countOfPendingRequests += 1;
                                        },
                                        success: function(data) {

                                            if ( $.isFunction( config.resultsMappers[ request.requestType ] )) {
                                                data = config.resultsMappers[ request.requestType ]( data, request, cache )
                                            } else {
                                                data = [ data ];
                                            }

                                            request.results = data;

                                            if ( that.indexes ) {
                                                $.each( that.indexes, function( i, e ) {
                                                    e.updateWith( request.results );
                                                });
                                            }

                                            accumulatedResponse = accumulatedResponse.concat(
                                                request.results.filter( function( el ) {
                                                    return request.dataType === undefined ||
                                                        el.dataType === request.dataType;
                                                } )
                                            );

                                        },
                                        error: function() {
                                            request.erroneous = true;
                                            transaction.dispatchEvent( 'loadError', request );
                                            transaction.withErrors = true;
                                            //throw 'Could not load design information for request.';
                                        },

                                        complete: function() {
                                            transaction.countOfPendingRequests -= 1;
                                            if ( transaction.countOfPendingRequests === 0 ) {
                                                _loadingOfOneTransactionComplete();
                                            }

                                            transaction.processedRequests.push( request );
                                            if ( transaction.requests.length === transaction.processedRequests.length ) {
                                                if ( transaction.withErrors !== true ) {
                                                    if ( $.isFunction( transaction.completed ) ) {
                                                        transaction.completed.call(
                                                            transaction,
                                                            accumulatedResponse,
                                                            'success' );
                                                    }
                                                } else {
                                                    if ( $.isFunction( transaction.completed ) ) {
                                                        transaction.completed.call( transaction, null, 'error' );
                                                    }
                                                }
                                            }
                                        }

                                    });
                                    }
                                } catch (e) {
                                    throw e;
                                }
                            } else {
                                transaction.withErrors = true;
                                throw 'No urlRenderer specified.';
                            }

                        }  else {
                            transaction.withErrors = true;
                            throw 'No serviceUrl specified.';
                        }

                    }
                });

                return transaction;
            }

            function Transaction( requests, completed, error ) {

                if ( $.isArray( requests) ) {
                    var t = {
                        requests: requests,
                        countOfPendingRequests: 0,
                        withErrors: false,
                        processedRequests: [],
                        completed: completed,
                        error: error
                    };

                    $.extend( t, new window.EventDispatcher() );

                    return t;
                } else {
                    throw 'Empty transaction.';
                }
            }

            // Making things public

            $.extend( that, {
                countOfBeingLoadedTransactions: _countOfBeingLoadedTransactions,
                query: query,
                Transaction: Transaction
            });

            return that;

        }

        $vf.DataPump = DataPump;
    }(
        jQuery,
        parent.window.$vf
    ));
});