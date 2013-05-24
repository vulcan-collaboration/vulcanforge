/* $RCSfile: Shell.js,v $
 * $Revision: 1.15 $ $Date: 2012/08/14 18:58:30 $
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
 * A 3D shell of triangles.  This will process the XML element
 * and build a Shell object for use by WebGL
 */

"use strict";

function Shell (builder, id) {

    this.use_count = 0;

    var ret = builder.make(id, this, "shell");
    if (ret)
	return ret;

    this.id = id;
    
    var el = builder.getElement(id);

    var vtags = el.getElementsByTagName("verts");
    if (vtags.length > 0) {
	this.load_all(el);
	return;
    }
    
    this.href = el.getAttribute("href");

    this.bbox
	= BoundingBox.fromArray(parse_float_vec(el.getAttribute("bbox"), 6));

    this.size = parseInt(el.getAttribute("size"));
}


METHODS(Shell, {

    getName : function() {return "Shell";},

    getBoundingBox: function() {
        return this.bbox;
    },

    loadData : function(tree, gl) {
	
	if (this.isLoaded())
	    return;

	this.gl = gl;
	
	var self = this;

	if (!this.href)
	    return;

	this.tree_el = tree;
	
	LOADER.addRequest(
	    this.href, this, 
	    function() {return self.getRank();} );
    },

    unloadData : function(gl) {
	this.loaded = false;
	this.loading = false;
	
	if (!this.faces)
	    return;
	
	for (var i=0; i<this.faces.length; i++)
	    this.faces[i].unloadData(gl);

	delete this.color;
	delete this.faces;
    },

    getId : function() {return  this.id;},
    
    getCost : function() {
	return this.getFacetCount() * 3;
    },

    load_all : function(el) {
	var cont = this.loadElement(el);
	while (cont)
	    cont = cont();
    },

    load : function(doc) {
	return this.loadElement(doc.documentElement);
    },
    
    loadElement : function(el) {
	
	var tree = this.tree_el;
	this.loading = true;
	
	if (tree) tree.expand(this);
	
	var verts = el.getElementsByTagName("verts")[0]
	    .getElementsByTagName("v");
	var points = new Float32Array(verts.length * 3);
	
	this.bbox = new BoundingBox();
	
	var color = el.getAttribute("color");
	if (color)
	    this.color = parse_color(color);

	var faces = el.getElementsByTagName("facets");
	this.faces = [];

	return this.continue_load(verts, points, faces, 0);

    },

    continue_load : function(verts, points, faces, first) {

	if (!this.loading)
	    return;

	var self = this;
	var i;


	var first_facet=0;
	if (first >= verts.length)
	    first_facet = first - verts.length
	else  {
	    var last_pt = first + 1000;
	    for (i=first; i<verts.length; i++) {
		if (i >= last_pt) {
		    return function() {
			return self.continue_load(verts, points, faces,
						  last_pt); 
		    }
		}
		
		var pt = verts[i].getAttribute("p");
		var coords = pt.split(" ", 3);
		
		if (coords.length != 3) {
		    throw new Error(
			"Must have exactly three coordinates in a point");
		}
		
		for (var j=0; j<3; j++) {
		    var v = parseFloat(coords[j]);
		    if (!isFinite(v))
			throw new Error("Number is not finite");
		    
		    this.bbox.updateI(j, v);
		    points[i*3 + j] = v;
		}
	    }
	}
	    
	var facet_count =0;
	
	for (i=first_facet; i<faces.length; i++) {
	    var face = new Face(this.gl, faces[i], points)
	    this.faces.push(face);

	    facet_count += face.facetCount();
	    if (facet_count > 1000) {
		return function() {
		    return self.continue_load(verts, points, faces,
					      verts.length+i+1); 
		}
	    }
	}

	this.loaded = true;
	this.loading = false;

	return null;
    },

    
    isLoaded : function() {
	return this.loaded;
    },
    
    getFacetCount : function() {
		
	if (this.size !== undefined)
	    return this.size;

	if (!this.faces) {
	    console.log ("No faces in shell: "+this.id);
	}

	console.log ("faces="+this.faces);
	
	this.size = 0;
	for (var i=0; i<this.faces.length; i++) {
	    this.size += this.faces[i].facetCount();
	}

	console.log ("After loop");
	return this.size;
    },
    
    incrCount : function(loadables) {
	if (this.use_count == 0) {
	    if (!this.loaded)
		loadables.push(this);
	}
	this.use_count++
    },

    getRank : function() {
	if (this.rank) return this.rank;
	
	if (this.faces) {
	    this.rank = 0;
	    return 0;
	}

	var sz = this.size;
	if (sz == 0)
	    sz = 1.e20;

	var vol =
	    (this.bbox.maxx - this.bbox.minx) *
	    (this.bbox.maxy - this.bbox.miny) *
	    (this.bbox.maxz - this.bbox.minz);
	
	this.rank = this.use_count *vol / sz;

	return this.rank;
    },

    getLastDraw : function() {
	return this.last_draw;
    },
    
    draw : function(gl) {
	this.last_draw = gl.draw_serial;
	
	if (!this.faces)
	    return;
	
	var old_color = gl.saveColor();
	if ( this.color)
	    gl.setColorv(this.color);

	for (var i=0; i<this.faces.length; i++)
	    this.faces[i].draw(gl);
	
	gl.restoreColor(old_color);
    },

});


/*******************************/

function Face(gl, el, points)
{
    var color = el.getAttribute("color");
    if (color)
	this.color = parse_color(color);
    
    var facets = el.getElementsByTagName("f");

    var coords_buff = new Float32Array(facets.length * 9);
    var normals_buff = new Float32Array(facets.length * 9);

    this.facet_count = facets.length;
    
    for (var i=0; i<facets.length; i++) {
	var facet = facets[i];
	
	var idxs = facet.getAttribute("v").split(" ", 3);
	if (idxs.length != 3) 
	    throw new Error ("v elements does not have exactly 3 members");
	
	for (var j=0; j<3; j++) 
	    for (var k=0; k<3; k++)
		coords_buff[i*9 + j*3 + k] = points[idxs[j]*3 + k];

	var normals = facet.getElementsByTagName("n");
	if (normals.length != 3)
	    throw new Error("Expecting 3 n elements, have "+normals.length);
	    
	for (var j=0; j<3; j++) {
	    var coords = normals[j].getAttribute("d").split(" ", 3);
	    if (coords.length != 3)
		throw new Error ("Expecting 3 elements in the normal");
	    
	    for (var k=0; k<3; k++) {
		var v = parseFloat(coords[k]);
		if (!isFinite(v))
		    throw new Error ("normal number is not finite");
		normals_buff[i*9 + j*3 + k] = v;
	    }
	}
    }

    if (gl)
	this.init(gl, coords_buff, normals_buff);
    else {
	this.coords = coords_buff;
	this.normals = normals_buff;
    }
    
}

METHODS(Face, {
    facetCount : function() {
	return this.facet_count;
//	return this.coords.length / 9;
    },

    unloadData : function(gl) {
	if (this.location_buff)
	    gl.deleteBuffer(this.location_buff);
	if (this.normal_buff)
	    gl.deleteBuffer(this.normal_buff);	
    },

    init : function(gl, coords, normals) {
	if (!this.location_buff) {
 	    this.location_buff = gl.createBuffer();
	    gl.bindBuffer(gl.ARRAY_BUFFER, this.location_buff);
	    gl.bufferData(gl.ARRAY_BUFFER, coords, gl.STATIC_DRAW);
	}

	if (!this.normal_buff) {
	    this.normal_buff = gl.createBuffer();
	    gl.bindBuffer(gl.ARRAY_BUFFER, this.normal_buff);
	    gl.bufferData(gl.ARRAY_BUFFER, normals, gl.STATIC_DRAW);	
	}		
    },
    
    draw : function(gl) {
	if (!this.location_buff || !this.normal_buff)
	    this.init(gl, this.coords, this.normals);
	
	gl.bindBuffer(gl.ARRAY_BUFFER, this.location_buff);
	gl.vertexAttribPointer(gl.pos_loc, 3, gl.FLOAT, false, 0, 0);
	
	gl.bindBuffer(gl.ARRAY_BUFFER, this.normal_buff);
	gl.vertexAttribPointer(gl.norm_loc, 3, gl.FLOAT, false, 0, 0);
	
	var count = this.facetCount() * 3;

	var old_color = gl.saveColor();
	if ( this.color)
	    gl.setColorv(this.color);
	
	gl.drawArrays(gl.TRIANGLES, 0, this.facetCount() *3 );

	gl.restoreColor(old_color);	
    },
});
