var NO_WEBGL_MSG = ', but for full functionality and to enjoy the 3D experience, please use a <a href="http://www.khronos.org/webgl/wiki/Getting_a_WebGL_Implementation" target="_blank">WebGL-enabled browser</a>';
var ONLY_BASIC_MSG = '<p>You are using %%YourBrowser%%, which is not the most up-to-date version of %%Browser%%.</p> Basic functionality will work in %%YourBrowser%%';
var NOT_SUPPORTED_MSG = '<p><b>Sorry. You are using %%YourBrowser%%</b></p>';
var ANCIENT_VERSION = ', which is an old version of %%Browser%% and not supported.<br/>Please upgrade your browser and check back again!';
var UNKNOWN_BROWSER = 'a not supported browser. Please check back again with a supported browser! ';
var NO_COOKIES_MSG = 'Cookies are disabled in your browser. To log in to VehcileForge.mil please enable them!';

var browserRequirements = {
    'Chrome': {
        minVersion: 12
    },

    'Safari': {
        minVersion: 5
    },

    'Internet Explorer': {
        minVersion: 8
    },

    'Firefox': {
        minVersion: 4
    }, 

    'Opera': {
        minVersion: 11
    }
}


$(document).ready(function(){
    DEBUG = true;
    trace("Intializing VF Landing page...");

    var browserInf = detectIfBrowserSUpported(browserRequirements);

    if (browserInf.supported) {
        $("#messageHolder").show()

        if (browserInf.cookiesSupported) {

            $('#loginForm').fadeIn(500);
            
            var supportWarnings = '';

            if (browserInf.browser == 'Internet Explorer' && browserInf.version < 9) {
                var yourBrowserStr = browserInf.browser+' '+browserInf.version;

                var msg = ONLY_BASIC_MSG.replace(/%%YourBrowser%%/g, yourBrowserStr );
                msg = msg.replace(/%%Browser%%/g, (browserInf.browser) ? browserInf.browser : '' );            

                supportWarnings += msg;
            }

            if (!(Detector.webgl)) { // we disable it for other browsers than Chrome

                trace("No WebGL. Using static background.");

                getCSS($vf.resourcePath + 'css/vf_landing_nowebgl.css', function () {});
                
                if (browserInf.browser == 'Internet Explorer') {
                    
                    var preamble = (browserInf.version == 9) ? NO_WEBGL_MSG.replace(", but f", "F") : NO_WEBGL_MSG;
                    supportWarnings += preamble + ' or the <a href="" onclick="$(\'#browserSupportErrorHolder\').hide(); CFInstall.check({ mode: \'overlay\', destination: document.location }); return false">Google Chrome Frame</a> plugin.'

                } else {
                    supportWarnings += NO_WEBGL_MSG.replace(", but f", "F") + ".";
                }

            } else {
                trace("WebGL is supported. Loading animation...");
            
                loadGLLibs();
            }

            if (supportWarnings != '') {
                displayBrowserSupportError(supportWarnings, 'light');
            }
        } else {
            displayBrowserSupportError(NO_COOKIES_MSG, 'notSupported');
        }

    } else {
        if (browserInf.browser == 'Internet Explorer' && browserInf.version < 7) {
            $("#logoImage").attr("src", $vf.resourcePath + "images/vf_logo.gif");
        }

        $('#messageHolder').hide();

        getCSS($vf.resourcePath + 'css/vf_landing_nowebgl.css', function () {});

        var yourBrowserStr = browserInf.browser ? (browserInf.browser+' '+browserInf.version+ANCIENT_VERSION): UNKNOWN_BROWSER;

        var msg = NOT_SUPPORTED_MSG.replace(/%%YourBrowser%%/g, yourBrowserStr );
        msg = msg.replace(/%%Browser%%/g, (browserInf.browser) ? browserInf.browser : '' );

        msg += NO_WEBGL_MSG.replace(", but f", "F") 
        if (browserInf.browser == 'Internet Explorer' && browserInf.version < 10) {
            msg += ' or the <a href="" onclick="$(\'#browserSupportErrorHolder\').hide(); CFInstall.check({ mode: \'overlay\', destination: document.location }); return false">Google Chrome Frame</a> plugin.'
        } else {
            msg += ".";
        }
        displayBrowserSupportError(msg, 'notSupported');
    }

});

function errorTrigger(){
    var e = $('#browserSupportErrorHolder');
    if ($(window).height() < (741+e.height())) {
        e.hide();
    } else {
        e.fadeTo(30, 0.6).position( { my: "bottom", at: "bottom", of: $(window) });
    }
}

function displayBrowserSupportError(msg, css_class) {
    var e = $('#browserSupportErrorHolder');
    if (css_class) e.addClass(css_class);
    e.html(msg);
    $(window).resize(errorTrigger);
    e.fadeTo(30, 0.6, function(){
        $(this).position( { my: "bottom", at: "bottom", of: $(window) });
    });
}

function loadGLLibs() {
    
    ThreeWebGL_loaded = false;
    ThreeExtras_loaded = false;
    RequestAnimationFrame_loaded = false;
    AnimationCode_loaded = true;

    VertexShaderLoaded = false;
    FragmentShaderLoaded = false;

    $.getScript($vf.resourcePath + "ThreeWebGL.js", function(){
        ThreeWebGL_loaded = true;
        checkIfGLLibsAreLoaded();
        trace("ThreeWebGL_loaded.");

        $.getScript($vf.resourcePath + "ThreeExtras.js", function(){
            ThreeExtras_loaded = true;
            checkIfGLLibsAreLoaded();
            trace("ThreeExtras_loaded.");
 
                $.getScript($vf.resourcePath + "RequestAnimationFrame.js", function(){
                    RequestAnimationFrame_loaded = true;
                    checkIfGLLibsAreLoaded();
                    trace("RequestAnimationFrame_loaded.");

                    $.get($vf.resourcePath + "clouds.vert", function(data) {
                        VertexShaderLoaded = true;        
                        vertexShader = data;
                        checkIfGLLibsAreLoaded();
                        trace("VertexShaderLoaded");
 
                        $.get($vf.resourcePath + "clouds.frag", function(data) {
                            FragmentShaderLoaded = true;
                            fragmentShader = data;
                            checkIfGLLibsAreLoaded();
                            trace("FragmentShaderLoaded");
                        }, "text");

                    }, "text");
                    
                });
                        
        });
        
    });
    

}   


function checkIfGLLibsAreLoaded() {
  
    if (ThreeExtras_loaded && ThreeWebGL_loaded && RequestAnimationFrame_loaded && FragmentShaderLoaded && VertexShaderLoaded && AnimationCode_loaded) {
        trace("GLLibs are loaded. Initializing animation.");
        initAnimation();
    }

}
