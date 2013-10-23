/*globals window, $, trace, $vf, DEBUG, detectIfBrowserSUpported, Detector, getCSS, CFInstall, document, initAnimation */

var fragmentShader,
    vertexShader,
    ACTIVE = true,
    DEBUG = true;

(function () {

    "use strict";

    var NO_WEBGL_MSG = 'WebGL is not enabled. For full 3D experience, please use a <a href="http://www.khronos.org/webgl/wiki/Getting_a_WebGL_Implementation" target="_blank">WebGL-enabled browser</a>.';
    var ONLY_BASIC_MSG = '<p>You are using %%YourBrowser%%, which is not the most up-to-date version of %%Browser%%.</p> Basic functionality will work in %%YourBrowser%%';
    var NOT_SUPPORTED_MSG = '<p><b>Sorry. You are using %%YourBrowser%%</b></p>';
    var NOT_SUPPORTED_AT_ALL_MSG = '<p><b>Sorry. You are using %%Browser%% which is not supported!</b></p>';
    var ANCIENT_VERSION = ', which is an old version of %%Browser%% and not supported.<br/>Please upgrade your browser.';
    var UNKNOWN_BROWSER = 'an unsupported browser. Please check back again with a supported browser! ';
    var NO_COOKIES_MSG = 'Cookies are disabled in your browser. To log in to VehicleFORGE please enable them!';
    var CHROME_FRAME_MSG = '<p>If you do not have sufficient privileges to install another browser on your computer,</br> we recommend you use <a href="" onclick="$(\'#browserSupportErrorHolder\').hide(); CFInstall.check({ mode: \'overlay\', destination: document.location }); return false">Google Chrome Frame</a>, a convenient way to browse safely.';
    
    var browserRequirements = {
        'Chrome': {
            minVersion: 20,
            downloadURL: 'http://www.google.com/chrome',
            cssClass: 'chrome'
        },

        'Safari': {
            minVersion: 5,
            downloadURL: 'http://www.apple.com/safari/',
            cssClass: 'safari'
        },

        'Firefox': {
            minVersion: 13,
            downloadURL: 'http://www.mozilla.org/en-US/firefox/new/',
            cssClass: 'firefox'
        },

        'Opera': {
            minVersion: 12,
            downloadURL: 'http://www.opera.com/download/',
            cssClass: 'opera'
        }

        /*,

        'Internet Explorer': {
            minVersion: 9
        }*/
    };

    var idle = $.cookie('idleLogout.loggedOut');

    if ( idle ) {
        $.cookie('idleLogout.loggedOut', null);
    }

    var loadGLLibs = function () {

        var ThreeWebGL_loaded = false,
            ThreeExtras_loaded = false,
            RequestAnimationFrame_loaded = false,
            AnimationCode_loaded = true,
            VertexShaderLoaded = false,
            FragmentShaderLoaded = false;


        var checkIfGLLibsAreLoaded = function () {

            if ( ThreeExtras_loaded && ThreeWebGL_loaded && RequestAnimationFrame_loaded && FragmentShaderLoaded && VertexShaderLoaded && AnimationCode_loaded ) {
                trace( "GLLibs are loaded. Initializing animation." );
                initAnimation();
            }
        };

        $.getScript( $vf.resourcePath + "ThreeWebGL.js", function () {
            ThreeWebGL_loaded = true;
            checkIfGLLibsAreLoaded();
            trace( "ThreeWebGL_loaded." );

            $.getScript( $vf.resourcePath + "ThreeExtras.js", function () {
                ThreeExtras_loaded = true;
                checkIfGLLibsAreLoaded();
                trace( "ThreeExtras_loaded." );

                $.getScript( $vf.resourcePath + "RequestAnimationFrame.js", function () {
                    RequestAnimationFrame_loaded = true;
                    checkIfGLLibsAreLoaded();
                    trace( "RequestAnimationFrame_loaded." );

                    $.get( $vf.resourcePath + "clouds.vert", function ( data ) {
                        VertexShaderLoaded = true;
                        vertexShader = data;
                        checkIfGLLibsAreLoaded();
                        trace( "VertexShaderLoaded" );

                        $.get( $vf.resourcePath + "clouds.frag", function ( data ) {
                            FragmentShaderLoaded = true;
                            fragmentShader = data;
                            checkIfGLLibsAreLoaded();
                            trace( "FragmentShaderLoaded" );
                        }, "text" );

                    }, "text" );

                } );

            } );

        } );

    };

    var displayBrowserSupportError = function ( msg, css_class ) {
        var e = $( '#browserSupportErrorHolder' );
        if ( css_class ) {
            e.addClass( css_class );
        }
        e.html( msg );
        e.fadeIn();
    };

    var loadStaticBG = function() {
        trace( 'No WebGL. Using static background.' );
        getCSS( $vf.resourcePath + 'vf_landing_nowebgl.css', function () {
        } );

    };

    $( document ).ready( function () {
        var loginShouldBeBlocked = false;

        trace( "Intializing VF Landing page..." );

        var browserInf = detectIfBrowserSUpported( browserRequirements ),
            yourBrowserStr,
            msg;


        if ( browserInf.supported ) {

            // Browser is supported

            $( "#messageHolder" ).show();

            if ( browserInf.cookiesSupported ) {

                $( '#loginForm' ).fadeIn( 500 );

                var supportWarnings = '';

                if ( browserInf.browser == 'Internet Explorer' && browserInf.version < 9 ) {
                    yourBrowserStr = browserInf.browser + ' ' + browserInf.version;

                    msg = ONLY_BASIC_MSG.replace( /%%YourBrowser%%/g, yourBrowserStr );
                    msg = msg.replace( /%%Browser%%/g, ( browserInf.browser || '' ) );

                    supportWarnings += msg;
                }

                if ( !(Detector.webgl) ) {

                    // No WebGL

                    loadStaticBG();

                    if ( browserInf.browser == 'Internet Explorer' ) {

                        supportWarnings += NO_WEBGL_MSG + CHROME_FRAME_MSG;

                    } else {
                        supportWarnings += NO_WEBGL_MSG;
                    }

                } else {

                    // WebGL

                    trace( "WebGL is supported." );

                    if ( !idle ) {
                        loadGLLibs();
                    } else {
                        loadStaticBG();
                    }
                }

                if ( supportWarnings != '' ) {
                    displayBrowserSupportError( supportWarnings, 'warning' );
                }
            } else {
                displayBrowserSupportError( NO_COOKIES_MSG, 'error' );
                loginShouldBeBlocked = true;
            }

        } else {

            loginShouldBeBlocked = true;

            // Browser is not supported

            $( '#messageHolder' ).hide();

            loadStaticBG();

            if ( browserInf.browser ) {
                yourBrowserStr =  browserInf.browser + ' ' + browserInf.version + ANCIENT_VERSION;
            } else {
                yourBrowserStr = UNKNOWN_BROWSER;
            }

            if ( browserRequirements[browserInf.browser] ) {

                // Old version

                msg = NOT_SUPPORTED_MSG.replace( /%%YourBrowser%%/g, yourBrowserStr );
                msg = msg.replace( /%%Browser%%/g, browserInf.browser );

            } else {

                // Browser is not supported at all

                trace('Not supported at all');

                msg = NOT_SUPPORTED_AT_ALL_MSG;
                msg = msg.replace( /%%Browser%%/g, browserInf.browser );
            }


            msg += '<p>We currently support and recommend the following browsers: </p><ul class="supported-browsers">';

            $.each ( browserRequirements , function (i, e) {

                var bs;

                msg += '<li ' + ( e.cssClass ? ( 'class="' + e.cssClass + '"' ) : '') + '>';
                bs = i + ' ' + e.minVersion;

                if ( e.downloadURL ) {
                    bs = '<a href="' + e.downloadURL + '" title="Go to download page" target="_blank">' + bs + '</a>';
                }

                msg += bs;

                msg += '</li>';
            });
                
            msg += '</ul>';

            if ( browserInf.browser == 'Internet Explorer' && browserInf.version < 10 ) {
                msg += CHROME_FRAME_MSG;
            }

            displayBrowserSupportError( msg, 'error' );
        }

        if ( loginShouldBeBlocked ) {

            $( '#main-content' ).remove();

        } else {

            $( '#main-content' ).fadeIn();

        }

        if ( idle ) {
            $( '#idleMessageHolder' ).show();
        }

        // handling user being inactive

        $.idleTimer(180000);

        $(document).bind("idle.idleTimer", function(){
            ACTIVE = false;
        });


        $(document).bind("active.idleTimer", function(){
            ACTIVE = true;
        });

    } );


}());