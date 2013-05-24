/* $RCSfile: ViewVolume.js,v $
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
 *
 * A view volume contains the transforms to display the a scene graph.
 * There are two matrices : the projection, and the modelview.
 * Note that the lighting should be applied after the modelview matrix so
 * that the part rotates relative to the lighting.
 */

"use strict";

function ViewVolume(canvas) {
    this.canvas = canvas;
    
    this.camera_ratio = 2.;
    this.zoom_ratio = 1.;

    this.use_perspective = true;
//    this.use_perspective = false;
    
    this.bound_radius = 0.;
    this.center = [0, 0, 0];
    this.rot = mat4.create();
    mat4.identity(this.rot);
}

METHODS (ViewVolume, {

    setViewBbox : function(bbox) {   
	this.center = bbox.center();        
	this.bound_radius = bbox.diagonal();	
    },

    getProjectionMatrix : function() {
	var near_cp = this.camera_ratio;
	var far_cp = near_cp + 4.;
	
	var view = near_cp / (this.zoom_ratio*(near_cp+1.));
	
	var w,h;

	var window_width = this.canvas.width;
	var window_height = this.canvas.height;
	
	if (window_width < window_height) {
	    w = view;
	    h = w * window_height / window_width;
	}
	else {
	    h = view;
	    w = h * window_width / window_height;
	}
	
	var ret;
    
	if (this.use_perspective)
	    ret = mat4.frustum(-w, +w, -h, +h, near_cp, far_cp);
	else
	    ret = mat4.ortho (-w, +w, -h, +h, near_cp, far_cp);

//	console.log ("Projection matrix: "+mat4.str(ret));

	return ret;
    },

    getPickMatrix : function(x,y) {
	var deltax;
	var deltay;
	deltax = deltay = .1;

	var vp_x = 0;
	var vp_y = 0;
	
	var vp_w = this.canvas.width;
	var vp_h = this.canvas.height;
	
    /* Translate and scale the picked region to the entire window */
	var mat = mat4.create();
	mat4.identity(mat);
	mat4.translate(mat, [(vp_w - 2 * (x - vp_x)) / deltax,
			     (vp_h - 2 * (y - vp_y)) / deltay,
			     0]);
	mat4.scale(mat, [vp_w / deltax, vp_h / deltay, 1.0]);

//	console.log ("Pick matrix: "+mat4.str(mat));

	var ret = mat4.create();
	mat4.multiply(mat, this.getProjectionMatrix(), ret);
	
	return ret;
    },
    


    
    getModelViewMatrix : function() {
	var near_cp = this.camera_ratio;
    
	var matrix = mat4.create();
	var scale = 1. / this.bound_radius;
	var center = [-this.center[0], -this.center[1], -this.center[2]];

	mat4.identity(matrix);
	
	mat4.translate (matrix, [0, 0, -near_cp - 2.]);       
	mat4.scale (matrix, [scale, scale, scale] );
	
	mat4.multiply (matrix, this.rot);
	mat4.translate (matrix, center);
	
	return matrix;
    },


    setZoom : function(z) { this.zoom_ratio = z;},

    getZoom : function() {return this.zoom_ratio;},
    
    moveCenter : function(delta) { vec3.add(this.center, delta)},

    rotate_axes : function(x, y) {

	vec3.normalize(x);
	vec3.normalize(y);
	
	/* Compute z */
	var z = Array(3);
	vec3.cross(x,y,z);
	vec3.normalize(z);
	
	/* recompute y to insure it is orthogonal to x and z */
	vec3.cross(z,x,y);
	vec3.normalize(y);

	var rot = this.rot;
	
	mat4.identity(rot);
	
	rot[0] = x[0];
	rot[1] = x[1];
	rot[2] = x[2];
	
	rot[4] = y[0];
	rot[5] = y[1];
	rot[6] = y[2];
	
	rot[8]  = z[0];
	rot[9]  = z[1];
	rot[10] = z[2];	
	
    },
    
    rotate : function(axis, angle) {
	/* Update the rotation matrix given the rotation and the direction.
	 * We could just multiply the current matrix, but that will result in
	 * ever increasing error.  Instead, extract the X and Y components from
	 * the matrix, transform those, and then recompute z
	 */

	vec3.normalize(axis);

	/* Do not attempt to rotate aroud a non-existant axis */
	if (axis[0] == 0 && axis[1] == 0 && axis[2] == 0)
	    return;
    
	var rot = this.rot;
    
	/* Extract the direction vectors from the rotation matrix.
	 */
	var x = [rot[0], rot[1], rot[2]];
	var y = [rot[4], rot[5], rot[6]];
	
	var rm = mat4.create();
	mat4.identity(rm);
	mat4.rotate(rm, angle, axis);
	
	mat4.multiplyVec3(rm, x);
	mat4.multiplyVec3(rm, y);
	
	vec3.normalize(x);
	
	/* Compute z */
	var z = Array(3);
	vec3.cross(x,y,z);
	vec3.normalize(z);
	
	/* recompute y to insure it is orthogonal to x and z */
	vec3.cross(z,x,y);
	vec3.normalize(y);
	
	mat4.identity(rot);
	
	rot[0] = x[0];
	rot[1] = x[1];
	rot[2] = x[2];
	
	rot[4] = y[0];
	rot[5] = y[1];
	rot[6] = y[2];
	
	rot[8]  = z[0];
	rot[9]  = z[1];
	rot[10] = z[2];	
    },

    saveState : function(parent_el) {
	var doc = parent_el.ownerDocument;
	var el = doc.createElement("view");
	parent_el.appendChild(el);

	var rot = this.rot;
    
	/* Extract the direction vectors from the rotation matrix.
	 */
	var x = [rot[0], rot[1], rot[2]];
	var y = [rot[4], rot[5], rot[6]];
	
	el.setAttribute("x", format_vec(x));
	el.setAttribute("y", format_vec(y));
	el.setAttribute("zoom", this.getZoom());
	el.setAttribute("center", format_vec(this.center));
    },

    restoreState : function(el) {
	var x = parse_float_vec(el.getAttribute("x", 3));
	var y = parse_float_vec(el.getAttribute("y", 3));

	this.rotate_axes(x,y);
	
	this.center = parse_float_vec(el.getAttribute("center", 3));
	this.zoom_ratio = get_float(el.getAttribute("zoom"));
	
    }
});
