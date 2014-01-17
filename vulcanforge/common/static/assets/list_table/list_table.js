/*globals jQuery, window, trace, $vf */
(function ( $ ) {
    "use strict";

    $.fn.listTable = function ( config ) {

        return this.each( function () {

            var $container = $(this),
                topPager, bottomPager,
                $topPagerContainer, $bottomPagerContainer,
                $table = $( '<table/>', {
                    'class': 'vf-table list-table' + ( config.className && ( ' ' + config.className ) )
                } ),
                $tableContainer,
                $emptyMessage = $( '<div/>', {
                    'class': 'empty-message',
                    'html': config.emptyMessage || 'No entries'
                }),
                dataParams = {},
                pleaseWait,
                init,
                loadData,
                render,
                updateParams,
                classNameParser;

            $.extend(
                dataParams,
                {
                    limit: config.limit || 25,
                    page: config.page || 0
                },
                config.dataParams || {}
            );


            loadData = function () {

                pleaseWait.skin.height( $tableContainer.height() );
                pleaseWait.update();
                pleaseWait.show();
                $.ajax({
                    url: config.dataSource,
                    type: 'GET',
                    data: dataParams,
                    dataType: 'json',
                    success: function ( data ) {
                        pleaseWait.hide();
                        config.data = data;
                        render();
                    }
                });


            };

            init = function() {
                if ( !$topPagerContainer || !$bottomPagerContainer || !$tableContainer) {
                    $container.empty();
                    topPager = new $vf.Pager();
                    $topPagerContainer = $('<div></div>', {
                        'class': 'pager-container top'
                    });
                    bottomPager = new $vf.Pager();
                    $bottomPagerContainer = $('<div></div>', {
                        'class': 'pager-container top'
                    });
                    $tableContainer = $( '<div/>', {
                        'class': 'table-container'
                    }).
                        css('position', 'relative');

                    $container.append( $topPagerContainer );
                    $container.append( $tableContainer );
                    $container.append( $bottomPagerContainer );

                    pleaseWait = new $vf.PleaseWait('Loading...', $tableContainer );

                    topPager.containerE = $topPagerContainer;

                    bottomPager.containerE = $bottomPagerContainer;

                }

            };

            classNameParser = function ( e ) {

                return ( ( e.className !== undefined ) &&  ( e.className + ' '  + $vf.slugify( e.label ) ) ) ||
                    $vf.slugify( e.label );

            };

            updateParams = function(params) {
                var changelog = {}, old;
                $.each(params, function(key, value){
                    old = dataParams[key];
                    if (old !== value){
                        changelog[key] = {
                            "old": old,
                            "new": value
                        };
                        dataParams[key] = value;
                    }
                });
                return changelog;
            };

            render = function() {

                var $tableHeadRow = $( '<tr/> '),
                    $tableHeadGroupRow = $( '<tr/> '),
                    $colGroup = $('<colgroup/>'),
                    $tableHead = $('<thead/>'),
                    $tableBody = $('<tbody/>'),
                    $tableRow,
                    columnClasses = [],
                    columnRenderAs = [],
                    className, childClassName,
                    lastGroupedPosition = -1,
                    $spacerCell,
                    numberOfColumns = 0, d;

                if ( !$container || !config.data ) {
                    return null;
                }


                if ( $table ) {
                    $table.empty();
                }

                if ( config.data.count && $.isArray( config.data.rows ) && config.data.rows.length) {

                    topPager.configure({
                        maxLength: 13,
                        itemCount: config.data.count,
                        itemPerPage: dataParams['limit'],
                        currentPage: dataParams['page'],
                        onGotoPage: function(n) {
                            dataParams['page'] = n;
                            topPager.currentPage = n;
                            bottomPager.currentPage = n;
                            topPager.render();
                            bottomPager.render();
                            loadData( config );
                        }
                    });

                    bottomPager.configure({
                        maxLength: 13,
                        itemCount: config.data.count,
                        itemPerPage: dataParams['limit'],
                        currentPage: dataParams['page'],
                        onGotoPage: function(n) {
                            dataParams['page'] = n;
                            topPager.currentPage = n;
                            bottomPager.currentPage = n;
                            topPager.render();
                            bottomPager.render();
                            loadData( config );
                        }
                    });

                    topPager.render();
                    bottomPager.render();

                    topPager.containerE.show();
                    $table.appendTo( $tableContainer );
                    $emptyMessage.remove();
                    bottomPager.containerE.show();

                    $table.append( $colGroup );
                    $table.append( $tableHead );
                    $table.append( $tableBody );

                    $tableHead.append( $tableHeadRow );

                    $.each( config.data.columns , function( i, e ) {

                        if ( $.isArray( e.childColumns) ) {

                            if ( lastGroupedPosition + 1 < numberOfColumns ) {
                                $spacerCell = $('<td/>', {
                                    'class': 'spacer'
                                });

                                d = numberOfColumns - lastGroupedPosition;

                                if ( d > 2 ) {
                                    $spacerCell.attr( 'colspan', d-1 );
                                }

                                $tableHeadGroupRow.append( $spacerCell );
                            }

                            className = classNameParser( e );
                            $tableHeadGroupRow.append( $('<th/>', {
                                'html': e.label,
                                'class': className,
                                'title': e.title || e.label,
                                'colspan': e.childColumns.length
                            }));

                            $.each( e.childColumns , function ( i2, e2 ) {
                                childClassName = classNameParser( e2 );
                                columnClasses.push( childClassName );
                                columnRenderAs.push( e2.renderAs );

                                $colGroup.append( $('<col/>', {
                                    'class': 'grouped'
                                } ));

                                $tableHeadRow.append( $('<th/>', {
                                    'html': e2.label,
                                    'title': e2.title || e2.label,
                                    'class': childClassName
                                }));

                                numberOfColumns++;
                            } );

                            lastGroupedPosition = numberOfColumns;

                        } else {
                            className = classNameParser( e );
                            columnClasses.push( className );
                            columnRenderAs.push( e.renderAs );

                            $colGroup.append( $('<col/>'), {} );

                            $tableHeadRow.append( $('<th/>', {
                                'html': e.label,
                                'title': e.title || e.label,
                                'class': className
                            }) );

                            numberOfColumns++;
                        }

                    });

                    if ( lastGroupedPosition > -1 ) {

                        if ( lastGroupedPosition !== numberOfColumns ) {
                            $spacerCell = $('<td/>', {
                                'class': 'spacer'
                            });

                            d = numberOfColumns - lastGroupedPosition;

                            $spacerCell.attr( 'colspan', d-1 );

                            $tableHeadGroupRow.append( $spacerCell );
                        }

                        $tableHead.prepend( $tableHeadGroupRow );
                    }

                    $.each( config.data.rows , function( i, rowData ) {

                        $tableRow = $( '<tr/>' );

                        $tableBody.append( $tableRow );

                        $.each( rowData , function( i2, cellData ) {
                            var $tableCell = $( '<td/>', {
                                'class': columnClasses[ i2 ]
                            } );

                            $tableRow.append( $tableCell );

                            if ( columnRenderAs[ i2 ] &&
                                 config.renderers &&
                                 $.isFunction ( config.renderers [ columnRenderAs[ i2 ] ] )) {

                                 config.renderers [ columnRenderAs[ i2 ] ].call( this, $tableCell, cellData);

                            } else {
                                if ( cellData === null ) {
                                    $tableCell.text( '---' );
                                    $tableCell.attr( 'title', 'Data not available' );
                                } else {
                                    $tableCell.text( cellData );
                                    $tableCell.attr( 'title', cellData );
                                }
                            }

                        });
                    });

                } else {
                    topPager.containerE.hide();
                    $table.remove();
                    $emptyMessage.appendTo( $tableContainer );
                    bottomPager.containerE.hide();
                }

            };

            init();

            if ( config.data && $.isArray( config.data )) {

                render();

            } else if ( config.dataSource ) {

                loadData();

            }

            /* exports */
            this.loadData = loadData;
            this.updateParams = updateParams;

            $container.data('listTable', this);

            return $container;

        } );
    };

} ( jQuery ));
