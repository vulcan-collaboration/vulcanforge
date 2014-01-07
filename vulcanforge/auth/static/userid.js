/*globals window, $, jQuery, $vf, Raphael, trace */
(function ( $ ) {
    "use strict";

    function mixColors ( color1, color2, fade ) {
        return [
            color1[0] + ( color2[0] - color1[0] ) * fade,
            color1[1] + ( color2[1] - color1[1] ) * fade,
            color1[2] + ( color2[2] - color1[2] ) * fade
        ].map( Math.round );
    }

    function getColor ( score ) {

        var color = [ 255, 255, 255 ],
            bottom = [ 255, 0, 100 ],
            mid = [ 233, 249, 50 ],
            top = [ 0, 252, 147];

        if ( score <= 0.5 ) {

            color = mixColors( bottom, mid, score * 2 );

        } else {

            color = mixColors( mid, top, (score - 0.5) * 2 );

        }

        return color;

    }
    if ($vf.trustforge_enabled)
        $.fn.reputationMe = function ( trustInfo, withHistory, reputationHistoryURL ) {
            return this.each( function () {
    
                var $reputationElementContainer = $( this ),
                    $reputationContainer = $( '<div/>', {
                        "class": "reputation-container",
                        "text": Math.round( trustInfo.score * 100 )
                    } ),
                    color = getColor( trustInfo.percentile ),
                    $historyGraphContainer,
                    historyPaper,
                    that = this,
                    history;
    
    
    
                $reputationContainer.css( 'background-color', 'rgb(' + color.join( ',' ) + ')' );
    
                $reputationContainer.addClass( 'bright' );
    
                $reputationElementContainer.attr(
                    'title',
                    'Reputation: ' + Math.round( trustInfo.score * 100 ) +
                        ' (Percentile: ' + Math.round( trustInfo.percentile * 100 ) + '%)' );
    
    
                $reputationElementContainer.append( $reputationContainer );
    
                if ( withHistory ) {
                    $historyGraphContainer = $( '<div/>', {
                        "class": "history-graph-container loading"
                    } );
    
                    $reputationElementContainer.append( $historyGraphContainer );
    
                    $historyGraphContainer.fadeIn();
    
                    if ( !history ) {
    
                        $.ajax( {
                            url: reputationHistoryURL,
                            context: that,
                            type: 'GET',
                            data: {
    
                            },
                            dataType: 'json'
                        } ).done( function ( data ) {
    
                                var duration,
                                    width = $historyGraphContainer.width() + 1,
                                    height = $historyGraphContainer.height(),
                                    minimumTime,
                                    curvePath,
                                    curve,
                                    i,
                                    newX;
    
                                $historyGraphContainer.removeClass( 'loading' );
    
                                historyPaper = new Raphael(
                                    $historyGraphContainer[0],
                                    width,
                                    height );
    
                                history = data.history;
    
                                if ( history.length ) {
    
                                    minimumTime = history[ 0 ][ 0 ];
    
                                    trace( history );
    
                                    if ( history.length < 2 ) {
                                        duration = minimumTime;
                                    } else {
                                        duration = history[ history.length - 1 ][ 0 ] - minimumTime;
                                    }
    
                                    curvePath = 'M1 ' + height + ' ';
    
                                    for ( i = 0; i < history.length; i++ ) {
                                        newX = Math.round( width / duration * ( history[ i ][ 0 ] - minimumTime ) );
    
                                        curvePath += 'L' + newX
                                            + ' ' + ( 1 - history[ i ][ 1 ] ) * height + ' ';
                                    }
    
                                    curvePath += 'L' + width + ' ' + ( 1 - history[ history.length - 1 ][ 1 ] ) * height + ' ';
                                    curvePath += 'L' + width + ' ' + height + ' ';
                                    curvePath += 'L0 ' + height + ' ';
                                    curvePath += 'Z';
    
                                    trace( curvePath );
    
    
                                    curve = historyPaper.path( curvePath );
    
                                    curve.attr( {
                                        stroke: '#fff',
                                        'stroke-width': 1,
                                        fill: '#fff'
                                    } );
    
    
                                }
    
                            } );
                    }
    
                }
    
            } );
        };

    $.fn.userIdMe = function( _options ) {

        var createUserIdPanel = function( $container, data, withReputationHistory ) {

            var $profileImage = $('<img/>', {
                src:  data.profileImage,
                'class': 'ico-user id-photo'
            }),
                $extraInfo = $('<div/>', {
                    'class': 'id-extra-info'
                }),
                $fullName = $('<div/>', {
                    html: '<a href="' + data.userURL + '">' + data.fullName + '</a>',
                    'class': 'id-full-name'
                }),
                $innerContents = $('<div/>', {
                    'class': 'id-inner-contents'
                }),
                $userSince = $('<div/>', {
                    text: 'Registered '+data.userSince,
                    'class': 'id-user-since'
                }),
                $mission = $('<div/>', {
                    text: data.mission,
                    'class': 'id-mission'
                }),
                $expertise = $('<div/>', {
                    html: data.expertise !== '' && ('<h4>Expertise</h4>' + data.expertise),
                    'class': 'id-expertise'
                }),
                $interests = $('<div/>', {
                    html: data.interests !== '' && ('<h4>Interests</h4>' + data.interests),
                    'class': 'id-interests'
                }),
                $reputationElementContainer = ($vf.trustforge_enabled) ? $('<div/>', {
                    'class': 'id-reputation'
                }) : null,
                $actions = $('<div/>', {
                    'class': 'id-actions'
                }),
                $seal = $('<div/>', {
                    'class': 'id-seal'
                });

            /* actions */
            if ($vf.logged_in_as !== data.username) {
                $('<a/>').
                    addClass('action-icon ico-inbox').
                    attr('href', '/dashboard/messages/start_conversation?recipients=' + data.username).
                    attr('title', 'Message ' + data.username).
                    html('<span class="hidden">Message ' + data.username + '</span>').
                    appendTo($actions);
            }

            if ($vf.trustforge_enabled)
                $reputationElementContainer.reputationMe(
                    data.trustInfo,
                    withReputationHistory,
                    data.userURL+'/profile/get_user_trust_history'
                );

            /* dom structure */
            $extraInfo.
                //append($reputationElementContainer).
                append($actions);
            $innerContents.
                append($fullName).
                append($mission).
                append($expertise).
                append($interests);
            return $container.
                prepend($seal).
                removeClass('waiting-on-something').
                append($profileImage).
                append($innerContents).
                append($extraInfo).
                append($userSince);
        };


        return this.each( function() {

            var that = this,
                options = _options || {},
                $avatar = $(this),
                $content = $('<div/>', {
                    'class': 'user-id-content waiting-on-something'
                }),
                tipPosition = "middle center",
                tipAnchor = "top center";

            if ( !options.userName ) {
                options.userName = $avatar.data( 'user-name' );
            }

            if ( !options.userURL ) {
                if ( $avatar.data( 'user-url' ) ) {
                    options.userURL = $avatar.data( 'user-url' );
                } else {
                    $avatar.find('a').css('cursor', 'default');
                }
            }

            if ( !options.replaceWithUserId ) {
                options.replaceWithUserId = $avatar.data( 'replace-with-userid' );
            }

            if ( options.userName && options.userURL ) {

                if ( options.replaceWithUserId ) {
                    // Direct display

                    $content.addClass( 'standalone' );
                    $avatar.replaceWith( $content );

                    $.ajax({
                        url: options.userURL+'/profile/get_user_profile',
                        context: that,
                        type: 'GET',
                        data: {
                            username: options.userName
                        },
                        dataType: 'json'
                    }).done(function( data ) {
                        data.userURL = options.userURL;
                        createUserIdPanel( $content, data, true );
                    });

                } else {

                    if (!$avatar.is(".avatar-list *, .user-list-container *")) {
                        tipPosition = "top right";
                        tipAnchor = "left top";
                    }

                    // attaching qtip to trigger
                    $avatar.qtip({

                        content: {

                            text: function (event, api) {
                                var $myContent = $content.clone();
                                $.ajax({
                                    url: options.userURL+'/profile/get_user_profile',
                                    type: 'GET',
                                    data: {
                                        username: options.userName
                                    },
                                    dataType: 'json',
                                    success: function ( data ) {
                                        data.userURL = options.userURL;

                                        createUserIdPanel( $myContent, data );

                                        api.reposition();
                                    },
                                    error: function ( e ) {
                                        api.destroy();
                                    }
                                });
                                return $myContent;
                            }

                        },
                        position: {
                            at: tipPosition, // Position the tooltip above the link
                            my: tipAnchor,
                            viewport: $(window) // Keep the tooltip on-screen at all times
                        },
                        show: {
                            event: 'mouseover',
                            solo: true // Only show one tooltip at a time
                        },
                        hide: 'unfocus',
                        style: {
                            classes: 'user-id',
                            tip: {
                                border: false
                            }
                        }

                    });
                }
            }

        });

    };

    if ($('body').data('user') === 'authenticated') {
        $vf.afterInit( function() {
            $('.avatar.with-user-id').userIdMe();
        });
    }

}(jQuery));
