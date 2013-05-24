/* $RCSfile: sti_utils.js,v $
 * $Revision: 1.13 $ $Date: 2012/08/03 17:00:48 $
 * Auth: Jochen Fritz (jfritz@steptools.com)
 * 
 * Copyright (c) 1991-2012 by STEP Tools Inc. 
 * All Rights Reserved.
 * 
 * Permission to use, copy, modify, and distribute this software and
 * its documentation is hereby granted, provided that this copyright
 * notice and license appear on all copies of the software.
 * 
 * STEP TOOLS MAKES NO REPRESENTATIONS OR WARRANTIES ABOUT THE
 * SUITABILITY OF THE SOFTWARE, EITHER EXPRESS OR IMPLIED, INCLUDING
 * BUT NOT LIMITED TO THE IMPLIED WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT. STEP TOOLS
 * SHALL NOT BE LIABLE FOR ANY DAMAGES SUFFERED BY LICENSEE AS A
 * RESULT OF USING, MODIFYING OR DISTRIBUTING THIS SOFTWARE OR ITS
 * DERIVATIVES.
 * 
 * 		----------------------------------------
 *
 * A set of small STEP Tools utility functions
 */

/*
 * declare the members of a class. 
 */
function METHODS (cls, members) {
    for (var n in members) {
	cls.prototype[n] = members[n];
    }
}

function STATIC (cls, members) {
    for (var n in members) {
	cls[n] = members[n];
    }
}

/*
 * Declare sub as a subtype of sup
 */
function SUBTYPE(sup, sub) {
    sub.prototype = new sup();
    sub.prototype.constructor = sub;
    
}


/*
 * Parse the search string (from location.search).  There is a leading ? 
 */
function parse_search(s, def) {
    if (s.length == 0)
	return def;
    
    if (s.charAt(0) != '?')
	throw new Error ("Expecting query string starting with '?'");

    var ret = s.substr(1);
    return ret;
}


function load_document(url)
{
    var req = new XMLHttpRequest();

    console.log ("Loading "+url);
    
    req.open ("GET", url, false);
    req.send();
  
    var doc = req.responseXML;
    return doc;
}


/*
 * Get the direct child element of a given element with the given name
 */
function get_child_element(parent_el, ch_name)
{
    var nl = parent_el.childNodes;
    for (var i=0; i<nl.length; i++) {
	var n = nl[i];
	if (n.nodeType == Node.ELEMENT_NODE) {
	    if (n.tagName == ch_name)
		return n;	    
	}
    }

    return null;
//    throw new Error("Could not find child: "+ch_name);
}


/*
 * wrapper around parseFloat that throws and error on malformed values
 */
function get_float(str)
{
    var ret = parseFloat(str);
    if (!isFinite(ret))
	throw new Error ("malformed float value: "+ str);

    return ret;
}

/*
 * Parse a string into an arry of float values.
 */
function parse_float_vec(str, count)
{
//    console.log ("Parse float vec: "+str);
    
    var vals = str.split(" ");
    if (count != null && vals.length != count) {
	throw new Error (
	    "parse_float_vec: unexpected number of elements expecting "+count
		+ " have " + vals.length);
    }
    
    count = vals.length;
    var ret = new Array(count);
    
    for (var i=0; i<count; i++) {
	var v = parseFloat(vals[i]);
	if (!isFinite(v))
	    throw new Error ("number is not finite");
	ret[i] = v;
    }

    return ret;
}


function parse_xform(str)
{
    
    if (str == null)
	return null;
    
    var arr = parse_float_vec(str);
    return mat4.create(arr);
}


function format_xform(mat)
{
    var ret = mat[0];
    for (var i=1; i<16; i++) {
	ret += " " + mat[i];
    }

    return ret;
}

function format_vec(v)
{
    return v[0] + " " + v[1] + " " + v[2];
}

function get_boolean(str, def)
{
    if (str == "true")
	return true;
    else if (str == "false")
	return false;

    return def;
}


function build_element_id_map(el)
{
    var ids = {};

    for (var i=0; i<el.childNodes.length; i++) {
	var ch = el.childNodes[i];

	if (ch.nodeType != Node.ELEMENT_NODE)
	    continue;

	var id = ch.getAttribute("id");
	if (id) {
	    ids[id] = ch;
	}
    }

    return ids;
}


/* Get the XML attribute, from an element an split it info an array.
 * if empty or missing, return empty array.
 */
function get_array_attrib(el, name)
{
    var val = el.getAttribute(name);
    
    
    if (!val)
	return [];

    return val.split(" ");
}

/*
 * Utility function to create a span node, fill it with text, and append it
 * to the parent.
 */
function append_text(parent, str)
{
    var doc = parent.ownerDocument;
    var ret = doc.createElement("span");
    parent.appendChild(ret);
    var text = doc.createTextNode(str);
    ret.appendChild(text);
    return ret;
}

var EPSILON=1.e-10;
var PI_OVER_180 = (Math.PI / 180.);

/*
 * Get a normal value to a vector 
 */
function get_normal(vec)
{
    var a = vec[0];
    var b = vec[1];
    var c = vec[2];
    
    var azero = Math.abs(a) < EPSILON;
    var bzero = Math.abs(b) < EPSILON;
    var czero = Math.abs(c) < EPSILON;

//    console.log("a="+a+" b="+b+" c="+c);
    
    if (azero && (bzero || czero)) {
	/* This also includes the case a==b==c==0, which should not happen.
	 * But if it does, any unit vector at all will meet the constraints.
	 */
	return [1., 0., 0.];
    }
    
    else if (bzero && czero) {
	return [0., 1., 0.];
    }

    /* If we get here, there is a most one zero coefficient */

    else if (azero) {
	var b2 = b*b;
	var c2 = c*c;
	var y=Math.sqrt(c2 / (b2 + c2));

	return [0., y, -b*y / c];
    }

    else if (bzero) {
	var a2 = a*a;
	var c2 = c*c;
	var x=Math.sqrt(c2 / (a2 + c2));

	return [x, 0., -a*x / c];
    }

    else {
	/* let z = 0 (c may == 0, but it does not matter) */
	
	var a2 = a*a;
	var b2 = b*b;
	var x=Math.sqrt(b2 / (a2 + b2));

	return [x, -a*x / b, 0.];
    }

}

function transform_pt(xform, pt)
{
    var ret = new Array(3);
    mat4.multiplyVec3(xform, pt, ret);
    return ret;
}

function transform_dir(xdir, xform, dir)
{
    var xo = transform_pt(xform, [0,0,0]);
    var xp = transform_pt(xform, dir);

    vec3.subtract(xp, xo, xdir);
    return xdir;
}
    
function parse_color(hex)
{
    var cval = parseInt(hex, 16);
    var ret = [
	((cval >>16) & 0xff) / 255,
	((cval >>8) & 0xff) / 255,
	((cval >>0) & 0xff) / 255,
	1.,
    ];

    return ret;
}


// Parse the params string into a set of kw=value pairs
function parse_params(params)
{
    var kwval = /^(\w+?)=(.*)$/;

    var args = params.split("&");

    var ret = {};
    
    for (var i=0; i<args.length; i++) {
	var found = args[i].match(kwval);
	if (!found) {
	    // support for legacy (non-parameterized) use cases
	    if (args.length == 1)
		return null;
	    throw new Error ("Error parsing params:"+params);
	}

	var kw = found[1];
	var val = found[2];
	console.log ("Got param: "+kw+" = "+val);
	
	ret[kw] = val;
    }

    return ret;
}
