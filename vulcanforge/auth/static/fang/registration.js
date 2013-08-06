/*globals window, $, trace, $vf, DEBUG, detectIfBrowserSUpported, Detector, getCSS, CFInstall, document, initAnimation */

var fragmentShader,
    vertexShader,
    ACTIVE = true,
    DEBUG = true;

(function ($) {

    "use strict";

    var NO_WEBGL_MSG = 'WebGL is not enabled. For full 3D experience, please use a <a href="http://www.khronos.org/webgl/wiki/Getting_a_WebGL_Implementation" target="_blank">WebGL-enabled browser</a>.';
    var ONLY_BASIC_MSG = '<p>You are using %%YourBrowser%%, which is not the most up-to-date version of %%Browser%%.</p> Basic functionality will work in %%YourBrowser%%';
    var NOT_SUPPORTED_MSG = '<p><b>Sorry. You are using %%YourBrowser%%</b></p>';
    var NOT_SUPPORTED_AT_ALL_MSG = '<p><b>Sorry. You are using %%Browser%% which is not supported!</b></p>';
    var ANCIENT_VERSION = ', which is an old version of %%Browser%% and not supported.<br/>Please upgrade your browser.';
    var UNKNOWN_BROWSER = 'an unsupported browser. Please check back again with a supported browser! ';
    var NO_COOKIES_MSG = 'Cookies are disabled in your browser. Please enable them in order to log in!';
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


    var displayBrowserSupportError = function ( msg, css_class ) {
        var e = $( '#browserSupportErrorHolder' );
        if ( css_class ) {
            e.addClass( css_class );
        }
        e.html( msg );
        e.fadeIn();
    };

    $( document ).ready( function () {
        var browserInf = detectIfBrowserSUpported( browserRequirements ),
            block = false,
            registrationForm = $('#main-content'),
            yourBrowserStr,
            msg;


        if ( browserInf.supported ) {

            // Browser is supported

            if ( browserInf.cookiesSupported ) {
                trace('browser is supported');
                registrationForm.fadeIn( 500 );

                var supportWarnings = '';

                if ( browserInf.browser == 'Internet Explorer' && browserInf.version < 9 ) {
                    yourBrowserStr = browserInf.browser + ' ' + browserInf.version;

                    msg = ONLY_BASIC_MSG.replace( /%%YourBrowser%%/g, yourBrowserStr );
                    msg = msg.replace( /%%Browser%%/g, ( browserInf.browser || '' ) );

                    supportWarnings += msg;
                }

                if ( !(Detector.webgl) ){
                    // No WebGL
                    if ( browserInf.browser == 'Internet Explorer' ) {
                        supportWarnings += NO_WEBGL_MSG + CHROME_FRAME_MSG;
                    } else {
                        supportWarnings += NO_WEBGL_MSG;
                    }
                }

                if ( supportWarnings != '' ) {
                    displayBrowserSupportError( supportWarnings, 'warning' );
                }
            } else {
                displayBrowserSupportError( NO_COOKIES_MSG, 'error' );
                block = true;
            }

        } else {

            block = true;
            trace('browser not supported');
            // Browser is not supported
            if ( browserInf.browser == 'Internet Explorer' && browserInf.version < 7 ) {

                // Old IE, taking care of log get displayed
                $( "#logoImage" ).attr( "src", $vf.resourcePath + "images/fang_vf_logo_for_login.png" );
            }

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

        if ( block ) {
            registrationForm.remove();
        } else {
            registrationForm.fadeIn();
        }

    } );


}(jQuery));