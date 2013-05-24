/* $RCSfile: SceneGraph.js,v $
 * $Revision: 1.7 $ $Date: 2012/08/14 18:58:30 $
 * Auth: Jochen Fritz (jfritz@steptools.com)
 * 
 * Copyright (c) 1991-2012 by STEP Tools Inc. 
 * All Rights Reserved.
 * 
 * Permission to use, copy, modify, and distribute this software and
 * its documentation is hereby granted, provided that this copyright
 * notice and license appear on all copies of the software.
 * 
 * STEP TOOLS MAKES NO REPRESENTATIONS OR WARRANTIES ABOUT TH *E
 * SUITABILITY OF THE SOFTWARE, EITHER EXPRESS OR IMPLIED, INCLUDING
 * BUT NOT LIMITED TO THE IMPLIED WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT. STEP TOOLS
 * SHALL NOT BE LIABLE FOR ANY DAMAGES SUFFERED BY LICENSEE AS A
 * RESULT OF USING, MODIFYING OR DISTRIBUTING THIS SOFTWARE OR ITS
 * DERIVATIVES.
 * 
 * 		----------------------------------------
 *
 * A scene graph object
 *  
 */


"use strict";

function SGNode(cx, sg, parent_xform, child_xform)
{
    // for constructing subtype 
    if (!cx)
	return;
    this.SGNode(cx, sg, parent_xform, child_xform);    
}

STATIC (SGNode, {
    append_bbox_pt : function(arr, idx, x, y, z)
    {
	idx *= 3;
	arr[idx++] = x;
	arr[idx++] = y;
	arr[idx++] = z;
    }
});


METHODS (SGNode, {

    SGNode : function(context, sg, parent_xform, child_xform) {
	context.assignId(this);
	
	if (!parent_xform) {
	    this.xform = child_xform;
	}
	else if (!child_xform) {
	    this.xform = parent_xform;
	}
	else {
	    this.xform = mat4.create();
	    mat4.multiply(parent_xform, child_xform, this.xform);
	}
        
	this.sg = sg;
	this.children = [];
    },

    getId : function() {return this.SGContextId;},
    
    getName : function() {return "SGNode";},
    
    appendChild : function(child) {
	this.children.push(child);
	child.parent = this;
    },

    getChild : function(i) {return this.children[i];},

    getXform : function() {return this.xform;},

    getRootNode : function() {
	if (!this.parent)
	    return this;
	return this.parent.getRootNode();	
    },
    
    getRoot : function() {
	if (!this.parent)
	    return this.sg;
	return this.parent.getRoot();
    },

    getParent : function() {return this.parent;},
    
    getBoundingBox : function() {
	if (this.sg.getBoundingBox)
	    return this.sg.getBoundingBox();

	return null;
    },

    
    draw : function(gl, visible) {
	
	if (this.hide) {
	    return;
	}

	if (this.hasVisible) {
	    visible = this.visible;
	}
	
	var sg = this.sg;

	var selected = this.isSelected && this.isSelected();
	var pick = gl.isPicking();
	if (pick) selected = false;
	
	if (visible || selected) {
	    var saved = gl.saveTransform();
	    this.setGlMode(gl);

	    if (visible && this.drawNode) {
		if (pick) {
		    gl.setPickId(this.SGContextId);
		}
		this.drawNode(gl);
	    }

	    if (selected)
		this.drawBbox(gl);

	    gl.restoreTransform(saved);
	}
	
	for (var i=0; i<this.children.length; i++)
	    this.children[i].draw(gl, visible);
    },

    drawBbox : function(gl) {
	var bbox = this.sg.getBoundingBox();

	var bbcoords = new Float32Array(8 * 3); // 8 point * 3 coords/pt 
	SGNode.append_bbox_pt(bbcoords, 0, bbox.minx, bbox.miny, bbox.minz);
	SGNode.append_bbox_pt(bbcoords, 1, bbox.maxx, bbox.miny, bbox.minz);
	SGNode.append_bbox_pt(bbcoords, 2, bbox.maxx, bbox.maxy, bbox.minz);
	SGNode.append_bbox_pt(bbcoords, 3, bbox.minx, bbox.maxy, bbox.minz);

	SGNode.append_bbox_pt(bbcoords, 4, bbox.minx, bbox.miny, bbox.maxz);
	SGNode.append_bbox_pt(bbcoords, 5, bbox.maxx, bbox.miny, bbox.maxz);
	SGNode.append_bbox_pt(bbcoords, 6, bbox.maxx, bbox.maxy, bbox.maxz);
	SGNode.append_bbox_pt(bbcoords, 7, bbox.minx, bbox.maxy, bbox.maxz);

	// pairs is indices into the coords array.  Each pair represents
	// a line segment.  In this case, we are drawing a box.
	var lines = new Int16Array([
	    0,1,
	    1,2,
	    2,3,
	    3,0,
	    4,5,
	    5,6,
	    6,7,
	    7,4,
	    0,4,
	    1,5,
	    2,6,
	    3,7,

	    // Additional lines to draw the diagonals of the box.
	    // 0,6,
	    // 1,7,
	    // 2,4,
	    // 3,5,
	]);
	
	var buff = gl.createBuffer();
	gl.bindBuffer(gl.ARRAY_BUFFER, buff);
	gl.bufferData(gl.ARRAY_BUFFER, bbcoords, gl.STATIC_DRAW);

	var idx_buff = gl.createBuffer();
	gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, idx_buff);
	gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, lines, gl.STATIC_DRAW);
		      
	gl.bindBuffer(gl.ARRAY_BUFFER, buff);
	gl.vertexAttribPointer(gl.pos_loc, 3, gl.FLOAT, false, 0, 0);
	
	/* Force the surface normal to be a constant. */	
	gl.disableVertexAttribArray(gl.norm_loc);
	gl.vertexAttrib3f(gl.norm_loc, 0,0,1);

	var saved_light = gl.getLight();
	gl.setLight(false);

	var old_color = gl.saveColor();
	gl.setColor(.9, 0., 0., 1.);
	
	gl.drawElements(gl.LINES, lines.length, gl.UNSIGNED_SHORT, 0);
	
	gl.setLight(saved_light);
	gl.enableVertexAttribArray(gl.norm_loc);
		      
	gl.restoreColor(old_color);
	
	gl.bindBuffer(gl.ARRAY_BUFFER, null);
	gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, null);
		
	gl.deleteBuffer(buff);
	gl.deleteBuffer(idx_buff);
    },
    
    redraw : function() {
	this.getRoot().viewer.draw();
    },
    
    setGlMode : function(gl) {
	if (this.xform) {
	    gl.applyTransform(this.xform);
	    gl.flushTransform();
	}
	
    },    
});


function SGContext() {
    this.parts = [];
}

METHODS(SGContext, {

    assignId : function(sg) {
	if (this.parts.length >= 0x2000) {
	    console.log ("Too many objects");
	}

	this.parts.push(sg);
	sg.SGContextId = this.parts.length;

//	console.log ("Assigned ID: "+sg.SGContextId);
    },

    getPart : function(id) {
	return this.parts[id-1];	
    },
    
});
