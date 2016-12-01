// Utility functions
/*
 *
 * Loading CSS document and insert it as a link
 *
 */
function getCSS(url) {
  $("head").append("<link>");
    css = $("head").children(":last");
    css.attr({
      rel:  "stylesheet",
      type: "text/css",
      href: url
    });
}

/*
 *
 * Disabling selection on element
 *
 */
// jQuery.fn.extend({
//         disableSelection : function() {
//                 this.each(function() {
//                         this.onselectstart = function() { return false; };
//                         this.unselectable = "on";
//                         jQuery(this).css('-moz-user-select', 'none');
//                 });
//         }
// });


/*
 *
 * Getting textwidth
 *
 */
$.fn.textWidth = function(){
  var html_org = $(this).html();
  var html_calc = '<span>' + html_org + '</span>'
  $(this).html(html_calc);
  var width = $(this).find('span:first').width();
  $(this).html(html_org);
  return width;
};



/**
 *
 * GUID generation
 *
 */
function S4() {
   return (((1+Math.random())*0x10000)|0).toString(16).substring(1);
}
function guid() {
   return (S4()+S4()+"-"+S4()+"-"+S4()+"-"+S4()+"-"+S4()+S4()+S4());
}

/**
 *
 *	Checks if a variable is set
 *
 */
function isSet( variable ) {
	return( typeof( variable ) != 'undefined' );
}

/**
 *
 *	Traces a msg on the console if available
 *
 */
function trace( msg, mode ) {

    if (isSet(window.DEBUG) && window.DEBUG==true) {
        if (isSet(window["console"])) {

            switch (mode) {
                case "error":

                    if (isSet(console.error)) {
                        var today=new Date();

                        var h=today.getHours();
                        var m=today.getMinutes();
                        var s=today.getSeconds();
                        var ms=today.getMilliseconds();

                        console.error("["+h+":"+m+":"+s+"."+ms+"] "+msg);

                        break;
                    }

                default:

                    if (isSet(console.log)) {
                        var today=new Date();

                        var h=today.getHours();
                        var m=today.getMinutes();
                        var s=today.getSeconds();
                        var ms=today.getMilliseconds();

                        console.log("["+h+":"+m+":"+s+"."+ms+"] "+msg);
                    }
            }
        }
    }
}

/**
 *
 * Loads an XML document a processes it with a processor function
 *
 */
function ProcessableXML() {

}

ProcessableXML.prototype = {

	contentLoaded: false,
	contentProcessed: false,
	contentXML: null,
	url: null,
	context: this,

	processor: null,
	postLoading: null,

	_processLoadedContent: function(xml) {

		this.contentXML = xml;
		trace("Content loaded from ["+this.url+"]");
		this.contentLoaded = true;

		if (jQuery.isFunction(this.processor)) {
			this.contentProcessed = this.processor.call(this.context, this.contentXML);
		} else {
			this.contentProcessed = true;
		}
		trace("Content from ["+this.url+"] process result is "+this.contentProcessed);

		if (jQuery.isFunction(this.postLoading)) {
			this.postLoading.call(this.context, this.contentLoaded, this.contentProcessed);
		}
	},

	_loadError: function(XMLHttpRequest, textStatus, errorThrown) {
		trace("Content from ["+this.url+"] could not be loaded. Error msg: "+textStatus+" "+errorThrown, "error");
		if (jQuery.isFunction(this.postLoading)) {
			this.postLoading.call(this.context, this.contentLoaded, this.contentProcessed);
		}
	},

	loadContent: function (location) {

		this.url = location;
		trace("Loading content from ["+this.url+"]");
		this.contentLoaded = false;
		this.contentProcessed = false;

        $.ajax({
            type: 'GET',
            url: this.url,
			dataType: ($.browser.msie) ? "text" : "xml",
            success: this._processLoadedContent,
			error: this._loadError,
			context: this,
			global: false
         });

	},

	setContent: function (xml) {

		this.url = "INTERNALLY_SPECIFIED";


		if (xml != null) {
			this.contentXML = xml;
			trace("Processable XML content set");
			contentLoaded = true;
			if (jQuery.isFunction(this.processor)) {
				this.contentProcessed = this.processor(this.contentXML);
			} else {
				this.contentProcessed = true;
			}
			trace("Content of ["+this.url+"] processing result is "+this.contentProcessed);

			if (jQuery.isFunction(this.postLoading)) {
				this.postLoading.call(this.context, this.contentLoaded, this.contentProcessed);
			}
		} else {
			// this is just for clearing and reseting the object

			delete contentXML;

			contentLoaded = false;
			contentProcessed = false;

		}

	}
}


// Canvas drawing extension
if (!!document.createElement('canvas').getContext) {
    $.extend(CanvasRenderingContext2D.prototype, {

        ellipse: function (aX, aY, r1, r2, fillIt) {
            aX = aX - r1;
            aY = aY - r2;

            var aWidth = r1*2;
            var aHeight = r2*2;

            var hB = (aWidth / 2) * .5522848,
                vB = (aHeight / 2) * .5522848,
                eX = aX + aWidth,
                eY = aY + aHeight,
                mX = aX + aWidth / 2,
                mY = aY + aHeight / 2;
            this.beginPath();
            this.moveTo(aX, mY);
            this.bezierCurveTo(aX, mY - vB, mX - hB, aY, mX, aY);
            this.bezierCurveTo(mX + hB, aY, eX, mY - vB, eX, mY);
            this.bezierCurveTo(eX, mY + vB, mX + hB, eY, mX, eY);
            this.bezierCurveTo(mX - hB, eY, aX, mY + vB, aX, mY);
            this.closePath();
            if (fillIt) this.fill();
            this.stroke();
        },

        circle: function(aX, aY, aDiameter, fillIt) {
           this.ellipse(aX, aY, aDiameter, aDiameter, fillIt)
        }
    });
}

/*
 *
 * EventDispatcher
 *
 */
function EventDispatcher(){
    this._eventList = {};
}
EventDispatcher.prototype = {
    _eventList: null,
    _getEvent: function(eventName, create){
        // Check if Array of Event Handlers has been created
        if (!this._eventList[eventName]){

            // Check if the calling method wants to create the Array
            // if not created. This reduces unneeded memory usage.
            if (!create){
                return null;
            }

            // Create the Array of Event Handlers
            this._eventList[eventName] = [];
            // new Array
        }

        // return the Array of Event Handlers already added
        return this._eventList[eventName];
    },
    addEventListener: function(eventName, handler, onlyOnce){
        // Get the Array of Event Handlers
        var evt = this._getEvent(eventName, true);

        // Add the new Event Handler to the Array
        evt.push({
            handler: handler,
            onlyOnce: onlyOnce
        });
    },
    removeEventListener: function(eventName, handler){
        // Get the Array of Event Handlers
        var evt = this._getEvent(eventName);

        if (!evt){
            return;
        }

        // Helper Method - an Array.indexOf equivalent
        var getArrayIndex = function(array, item){
            var i = 0;
            for (i = 0; i < array.length; i++){
                if (array[i] && array[i].handler === item){
                    return i;
                }
            }
            return - 1;
        };

        // Get the Array index of the Event Handler
        var index = getArrayIndex(evt, handler);

        if (index > -1){
            // Remove Event Handler from Array
            evt.splice(index, 1);
        }
    },
    removeAllEventListeners: function(eventName) {
                // Get the Array of Event Handlers
        var evt = this._getEvent(eventName);

        if (!evt){
            return;
        }

        evt.splice(0, evt.length);
    },
    dispatchEvent: function(eventName, eventArgs){
        // Get a function that will call all the Event Handlers internally
        var handler = this._getEventHandler(eventName);
        if (handler){
            // call the handler function
            // Pass in "sender" and "eventArgs" parameters
            handler(this, eventArgs);
        }
    },
    _getEventHandler: function(eventName){
        // Get Event Handler Array for this Event
        var evt = this._getEvent(eventName, false);
        if (!evt || evt.length === 0){
            return null;
        }

        // Create the Handler method that will use currying to
        // call all the Events Handlers internally
        var h = function(sender, args){
            for (var i = 0; i < evt.length; i++){
                var evt_e = evt[i];
                // If it should be called only once, we remove it
                if (evt[i].onlyOnce === true) {
                    evt.splice(i,1);
                    i--;
                }
                evt_e.handler(sender, args);
            }
        };

        // Return this new Handler method
        return h;
    }
};

Array.prototype.diff = function(a) {
    return this.filter(function(i) {return !(a.indexOf(i) > -1);});
};

if(!Array.indexOf){
    Array.prototype.indexOf = function(obj){
        for(var i=0; i<this.length; i++){
            if(this[i]==obj){
                return i;
            }
        }
        return -1;
    }
}

Array.prototype.removeElement = function (e) {
    var idx = this.indexOf(e);
    while (idx > -1) {
     this.splice(idx, 1); // Remove it if really found!
     var idx = this.indexOf(e);
  }
};


Object.size = function(obj) {
    var size = 0, key;
    for (key in obj) {
        if (obj.hasOwnProperty(key)) size++;
    }
    return size;
};

Object.equals = function( x, y ) {
  if ( x === y ) return true;
    // if both x and y are null or undefined and exactly the same

  if ( ! ( x instanceof Object ) || ! ( y instanceof Object ) ) return false;
    // if they are not strictly equal, they both need to be Objects

  if ( x.constructor !== y.constructor ) return false;
    // they must have the exact same prototype chain, the closest we can do is
    // test there constructor.

  for ( var p in x ) {
    if ( ! x.hasOwnProperty( p ) ) continue;
      // other properties were tested using x.constructor === y.constructor

    if ( ! y.hasOwnProperty( p ) ) return false;
      // allows to compare x[ p ] and y[ p ] when set to undefined

    if ( x[ p ] === y[ p ] ) continue;
      // if they have the same strict value or identity then they are equal

    if ( typeof( x[ p ] ) !== "object" ) return false;
      // Numbers, Strings, Functions, Booleans must be strictly equal

    if ( ! Object.equals( x[ p ],  y[ p ] ) ) return false;
      // Objects and Arrays must be tested recursively
  }

  for ( p in y ) {
    if ( y.hasOwnProperty( p ) && ! x.hasOwnProperty( p ) ) return false;
      // allows x[ p ] to be set to undefined
  }
  return true;
};

function isIE8Browser() {
    var rv = -1;
    var ua = navigator.userAgent;
    var re = new RegExp("Trident\/([0-9]{1,}[\.0-9]{0,})");
    if (re.exec(ua) != null) {
        rv = parseFloat(RegExp.$1);
    }
    return (rv == 4);
}

function detectIfBrowserSUpported(req){
    var version = 0;
    var browser = null;
    var supported = false;

    var userAgent = navigator.userAgent.toLowerCase();
    $.browser.chrome = /chrome/.test(navigator.userAgent.toLowerCase());

    // Is this a version of IE?
    if($.browser.msie ||
        navigator.appName === 'Netscape' && (new RegExp("Trident/.*rv:([0-9]{1,}[\.0-9]{0,})").exec(navigator.userAgent)) !== null){
        userAgent = $.browser.version;
        userAgent = userAgent.substring(0,userAgent.indexOf('.'));
        version = userAgent;
        browser = 'Internet Explorer';
    }

    // Is this a version of Chrome?
    if($.browser.chrome){
        userAgent = userAgent.substring(userAgent.indexOf('chrome/') +7);
        userAgent = userAgent.substring(0,userAgent.indexOf('.'));
        version = userAgent;
        // If it is chrome then jQuery thinks it's safari so we have to tell it it isn't
        $.browser.safari = false;
        browser = 'Chrome';
    }

    // Is this a version of Safari?
    if($.browser.safari){
        userAgent = userAgent.substring(userAgent.indexOf('safari/') +7);
        userAgent = userAgent.substring(0,userAgent.indexOf('.'));
        version = userAgent;
        browser = 'Safari';
    }

    // Is this a version of Mozilla?
    if($.browser.mozilla){
    //Is it Firefox?
    if(navigator.userAgent.toLowerCase().indexOf('firefox') != -1){
        userAgent = userAgent.substring(userAgent.indexOf('firefox/') +8);
        userAgent = userAgent.substring(0,userAgent.indexOf('.'));
        version = userAgent;
        browser = 'Firefox';
    }
    // If not then it must be another Mozilla
    else{
    }
    }

    // Is this a version of Opera?
    if($.browser.opera){
        userAgent = userAgent.substring(userAgent.indexOf('version/') +8);
        userAgent = userAgent.substring(0,userAgent.indexOf('.'));
        version = userAgent;
        browser = 'Opera';
    }

    supported = isSet(req[browser]) && req[browser].minVersion <= version;

    cookiesSupported = false;

    $.cookie('test_cookie', 'cookie_value', { path: '/' });
    if ($.cookie('test_cookie') == 'cookie_value') {
        cookiesSupported = true;
    }

    trace('Browser information: '+supported+' '+browser+' '+version+' '+cookiesSupported);

    return {
        'supported': supported,
        'browser': browser,
        'version': version,
        'cookiesSupported': cookiesSupported};
}


$(document).ready(function () {

    // Calculating scrollbar size
    

    var inner = document.createElement('p');
    inner.style.width = "100%";
    inner.style.height = "200px";

    var outer = document.createElement('div');
    outer.style.position = "absolute";
    outer.style.top = "0px";
    outer.style.left = "0px";
    outer.style.visibility = "hidden";
    outer.style.width = "200px";
    outer.style.height = "150px";
    outer.style.overflow = "hidden";
    outer.appendChild (inner);

    document.body.appendChild (outer);
    var w1 = inner.offsetWidth;
    outer.style.overflow = 'scroll';
    var w2 = inner.offsetWidth;
    if (w1 == w2) w2 = outer.clientWidth;

    document.body.removeChild (outer);

    window.SCROLLBAR_WIDTH = (w1 - w2);
});

// Inserting text at cursor in textarea

jQuery.fn.extend({
    insertAtCaret: function(myValue){
        return this.each(function(i) {
            if (document.selection) {
                //For browsers like Internet Explorer
                this.focus();
                sel = document.selection.createRange();
                sel.text = myValue;
                this.focus();
            }
            else if (this.selectionStart || this.selectionStart == '0') {
                //For browsers like Firefox and Webkit based
                var startPos = this.selectionStart;
                var endPos = this.selectionEnd;
                var scrollTop = this.scrollTop;
                this.value = this.value.substring(0, startPos)+myValue+this.value.substring(endPos,this.value.length);
                this.focus();
                this.selectionStart = startPos + myValue.length;
                this.selectionEnd = startPos + myValue.length;
                this.scrollTop = scrollTop;
            } else {
                this.value += myValue;
                this.focus();
            }
        })
    }
});

/* pause execution in process */
function pause(ms) {
    ms += new Date().getTime();
    while (new Date() < ms){}
}

function getParameterByName(name, myFrame){
    var frame = myFrame || window;
    name = name.replace(/[\[]/, "\\\[").replace(/[\]]/, "\\\]");
    var regexS = "[\\?&]" + name + "=([^&#]*)";
    var regex = new RegExp(regexS);
    var results = regex.exec(frame.location.search);
    if(results == null)
        return "";
    else
        return decodeURIComponent(results[1].replace(/\+/g, " "));
}

function encodeParameters(obj) {
    /* encode an object name, value pairs in URL parameter form */
    var name, queryList = [];
    for (name in obj) {
        if (obj.hasOwnProperty(name)) {
            queryList.push(encodeURIComponent(name) + '=' + encodeURIComponent(obj[name]));
        }
    }
    return queryList.join("&");
}

if (!String.prototype.endsWith) {
    String.prototype.endsWith = function(searchString, position) {
        var subjectString = this.toString();
        if (typeof position !== 'number' || !isFinite(position) || Math.floor(position) !== position || position > subjectString.length) {
            position = subjectString.length;
        }
        position -= searchString.length;
        var lastIndex = subjectString.indexOf(searchString, position);
        return lastIndex !== -1 && lastIndex === position;
    };
}