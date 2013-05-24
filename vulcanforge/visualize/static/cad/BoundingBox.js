/* $RCSfile: BoundingBox.js,v $
 * $Revision: 1.5 $ $Date: 2012/08/03 17:00:47 $
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
 * Bounding box class
 */

"use strict;"


function BoundingBox() {
    this.empty();
}

STATIC (BoundingBox, {
    fromArray : function(bb) {
	var bbox = new BoundingBox();
	bbox.updateX(bb[0]);
	bbox.updateY(bb[1]);
	bbox.updateZ(bb[2]);
	bbox.updateX(bb[3]);
	bbox.updateY(bb[4]);
	bbox.updateZ(bb[5]);

	return bbox;
    },
});

METHODS (BoundingBox, {
    
    empty : function()
    {
	this.minx = NaN;
	this.maxx = NaN;
	this.miny = NaN;
	this.maxy = NaN;
	this.minz = NaN;
	this.maxz = NaN;
    },

    isEmpty : function() {
	return isNaN(this.minx);
    },

    diagonal : function() {
	if (this.isEmpty()) 
	    return 0;

	var s=0;
	var d;
	d = this.maxx - this.minx; s += d*d;
	d = this.maxy - this.miny; s += d*d;
	d = this.maxz - this.minz; s += d*d;
	
	return Math.sqrt(s);
    },
    
    center : function() {
	var ret = new Array(3);
	ret[0] = (this.maxx + this.minx) / 2.;
	ret[1] = (this.maxy + this.miny) / 2.;
	ret[2] = (this.maxz + this.minz) / 2.;
	
	return ret;
    },

    updateX : function (v) {
	if (isNaN(this.minx))
	    this.minx = this.maxx = v;
	else {
	    if (v < this.minx)
		this.minx = v;
	    if (v > this.maxx)
		this.maxx = v;
	}
    },


    updateY : function (v) {
	if (isNaN(this.miny))
	    this.miny = this.maxy = v;
	else {
	    if (v < this.miny)
		this.miny = v;
	    if (v > this.maxy)
		this.maxy = v;
	}
    },


    updateZ : function (v) {
	if (isNaN(this.minz))
	    this.minz = this.maxz = v;
	else {
	    if (v < this.minz)
		this.minz = v;
	    if (v > this.maxz)
		this.maxz = v;
	}
    },

    /*
     * Update the given axis.
     * i=0 for x,
     * i=1 for y,
     * i=2 for z
     */
    updateI : function (i, v) {
	switch (i) {
	case 0:
	    this.updateX(v);
	    break;
	    
	case 1:
	    this.updateY(v);
	    break;
	    
	case 2:
	    this.updateZ(v)
	    break;
	}
    },

    update : function (x, y, z, xform) {
	if (typeof x != "number") {
	    throw new Error ("expecting a number");
	}
	
	if (xform) {
	    var vec=[x,y,z];
	    var inv = mat4.create();
	    mat4.inverse(xform, inv);
	    mat4.multiplyVec3(inv, vec);
	    
	    x=vec[0];
	    y=vec[1];
	    z=vec[2];
	}
	
	this.updateX(x);
	this.updateY(y);
	this.updateZ(z);    
    },

    updateVec : function (vec, xform) {
	this.update(vec[0], vec[1], vec[2], xform);
    },
    
    updateFrom : function (bbox, xform) {
	if (!xform) {
	    this.update(bbox.minx, bbox.miny, bbox.minz);
	    this.update(bbox.maxx, bbox.maxy, bbox.maxz);
	}
	else {
	    this.update(bbox.minx, bbox.miny, bbox.minz, xform);
	    this.update(bbox.minx, bbox.miny, bbox.maxz, xform);
	    this.update(bbox.minx, bbox.maxy, bbox.minz, xform);
	    this.update(bbox.minx, bbox.maxy, bbox.maxz, xform);
	    this.update(bbox.maxx, bbox.miny, bbox.minz, xform);
	    this.update(bbox.maxx, bbox.miny, bbox.maxz, xform);
	    this.update(bbox.maxx, bbox.maxy, bbox.minz, xform);
	    this.update(bbox.maxx, bbox.maxy, bbox.maxz, xform);
	}
    },

    toString : function() {
	return ("(["+this.minx+ "," +this.maxx + "],["
		+this.miny+ "," + this.maxy + "],["
		+this.minz+"," + this.maxz + "])")
    }
});

    
    
