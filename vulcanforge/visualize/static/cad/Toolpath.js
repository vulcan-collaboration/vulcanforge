/* $RCSfile: Toolpath.js,v $
 * $Revision: 1.8 $ $Date: 2012/08/14 18:58:30 $
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
 */

"use strict;"

function Toolpath (builder, id) {
    var ret = builder.make(id, this, "toolpath");
    if (ret) return ret;

    this.count = 0;
    
    var el = builder.getElement(id);
    
    var pnodes = el.getElementsByTagName("p");
    if (pnodes.length > 0) {
	this.loadAll(pnodes);
	return;
    }

    this.href = el.getAttribute("href");
    if (!this.href) 
	throw new Error ("Empty toolpath w/o href");

    this.size = parseInt(el.getAttribute("size"));
    this.length = parseFloat(el.getAttribute("length"));

    this.bbox = BoundingBox.fromArray(
	parse_float_vec(el.getAttribute("bbox", 6)));

}

METHODS (Toolpath, {

    loadData : function(tree, gl) {
	if (this.isLoaded()) return;

	if (!this.href) return;

	this.gl = gl;
	var self = this;

	
	LOADER.addRequest(this.href, this);
//	    function(doc) {
//		return self.load(doc.documentElement, viewer);
//	    });
    },

    load : function(el) {
//	console.log ("Loading toolpath from "+this.href);
	var pnodes = el.getElementsByTagName("p");
	this.loadAll(pnodes);	
    },
	
    loadAll : function(pnodes) {
	/* Number of sammples in the toolpath */
	var len = pnodes.length;
    
	this.path = new Float32Array(len*3);
	this.axis = new Float32Array(len*3);
	this.bbox = new BoundingBox();

	this.tsamples = new Float32Array(len);
	this.dsamples = new Float32Array(len);

	for (var i=0; i<pnodes.length; i++) {
	    var p = pnodes[i];
	    
	    if (i == 0) {
		this.tsamples[i] = 0.;
		this.dsamples[i] = 0.;
	    }
	    else {
		if (p.hasAttribute("t"))
		    this.tsamples[i] = get_float(p.getAttribute("t"));
		this.dsamples[i] = get_float(p.getAttribute("d"));
	    }
	    
	    var vec = parse_float_vec(p.getAttribute("l"));
	    
	    if (vec.length == 6) {
		for (var j=0; j<3; j++) {
		    this.path[i*3 +j] = vec[j];
		    this.axis[i*3 +j] = vec[3+j];
		}
	    } else if (vec.length == 3) {
		for (var j=0; j<3; j++) 
		    this.path[i*3 +j] = vec[j];
		this.axis = null;
	    } else {
		throw new Error ("vec.length != 3 or 6 =" +vec.length);
	    }
	    
	    //	console.log ("Append vec: "+vec);
	    
	    this.bbox.updateVec(vec);
	}
    },

    isLoaded : function() {
	return this.path != null;
    },
    
    getName : function() {return "Toolpath";},
    
    getBoundingBox : function() {
	if (!this.bbox)
	    throw new Error ("No bounding box for toolpath");
	return this.bbox;
    },
    

    getLength : function() {
	if (!this.isLoaded())
	    return this.length;
	
	return this.dsamples[this.dsamples.length-1];
    },

    getDuration : function() {
	return this.tsamples[this.tsamples.length-1];
    },


    /* get the tool position and axis at a given distance along the toolpath */
    getToolPositionByD : function(location, axis, d) {
	if (!this.isLoaded())
	    throw new Error ("Not loaded");

	var i;
	
	for (i=1; i<this.dsamples.length; i++) {
	    var cmp = this.dsamples[i];
	    if (cmp >= d)
		break;
	}

	if (i > this.dsamples.length)
	    throw new Error ("Distance too far");

	var prev = i==1 ? 0. : this.dsamples[i-1];
	var next = this.dsamples[i];

	var f = (d-prev) / (next-prev);

	for (var j=0; j<3; j++) {
	    var v1 = this.path[(i-1)*3 +j];
	    var v2 = this.path[(i)*3   +j];
	    location[j] = v1 + f*(v2-v1);
	}

	if (this.axis == null) {
	    axis[0] = 0.;
	    axis[1] = 0.;
	    axis[2] = 1.;
	}
	else {
	    for (var j=0; j<3; j++) {
		var v1 = this.axis[(i-1)*3 +j];
		var v2 = this.axis[(i)*3   +j];
		axis[j] = v1 + f*(v2-v1);
	    }
	}

	vec3.normalize(axis);
    },
    

    makeSceneGraph : function(cx, loadables, xform) {
	if (!this.isLoaded()) {
	    if (this.count == 0)
		loadables.push(this);
	}

	this.count++;
	return new ToolpathNode(cx, this, xform);
    },

    updateDraw : function(gl) {
	this.last_draw = gl.draw_serial;
    },

    getLastDraw : function() {
	return this.last_draw;
    },
    
    
});


////////////////////////////////////////////

function ToolpathNode(cx, sg, xform)
{
    this.SGNode(cx, sg, xform);
}

SUBTYPE(SGNode, ToolpathNode);

METHODS(ToolpathNode, {
    
    draw : function(gl, tn) {
	var sg = this.sg

	sg.updateDraw(gl);
	
	if (!sg.isLoaded())
	    return;
	
	var saved = gl.saveTransform();

	this.setGlMode(gl);

	if (!sg.location_buff) {
	    sg.location_buff = gl.createBuffer();
	    gl.bindBuffer(gl.ARRAY_BUFFER, sg.location_buff);
	    gl.bufferData(gl.ARRAY_BUFFER, sg.path, gl.STATIC_DRAW);
	}

	gl.bindBuffer(gl.ARRAY_BUFFER, sg.location_buff);
	gl.vertexAttribPointer(gl.pos_loc, 3, gl.FLOAT, false, 0, 0);
	
	/* Force the surface normal to be a constant.
	 * We don't need this since the toolpath is not lit.
	 */
	gl.disableVertexAttribArray(gl.norm_loc);
	gl.vertexAttrib3f(gl.norm_loc, 0,0,1);

	var old_light = gl.getLight();
	gl.setLight(false);
//	gl.uniform1i(gl.light_on, false);

	//	gl.vertexAttrib4f(gl.color_loc, .9, .9, 0., 1.);
	var old_color = gl.saveColor();
	gl.setColor(.9, .9, 0., 1.);
	
	gl.drawArrays(gl.LINE_STRIP, 0, sg.path.length / 3);

	gl.setLight(old_light);
//	gl.uniform1i(gl.light_on, true);
	gl.enableVertexAttribArray(gl.norm_loc);

	gl.restoreTransform(saved);
	gl.restoreColor(old_color);
	
    },

    
});
