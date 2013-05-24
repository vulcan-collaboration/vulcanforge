/* $RCSfile: Operation.js,v $
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

"use strict";

function Operation(builder, id)
{
    var ret = builder.make(id, this, "operation");
    if (ret) return ret;
    var el = builder.getElement(id);

    var tps = get_array_attrib(el, "toolpath");
    this.toolpath = [];

    var toolid = el.getAttribute("tool");
    if (toolid)
	this.tool_shape = new Shape(builder, toolid);

    this.lengths = [];
    
    var len = 0;
    for (var i=0; i<tps.length; i++) {
	var tp = new Toolpath(builder, tps[i]);
	this.toolpath.push(tp);
	len += tp.getLength();
	this.lengths.push(len);
    }

    this.length = len;

    this.tool_length = get_float(el.getAttribute("tool_length"));
}

METHODS (Operation, {

    getName : function() {return "Operation";},
    
    getBoundingBox : function() {
	var bbox = new BoundingBox();

	for (var i=0; i<this.toolpath.length; i++) 
	    bbox.updateFrom(this.toolpath[i].getBoundingBox());

	return bbox;
    },
    
    getToolPositionByD : function(location, axis, d) {

	/* Find the toolpath segment that the requested position is in */
	for (var idx=0; idx<this.lengths.length; idx++) {
	    if (this.lengths[idx] >= d)
		break;
	}

	if (idx >= this.lengths.length) {
	    idx = this.lengths.length - 1;
	    d = this.lengths[idx];
	}

	if (idx > 0)
	    d -= this.lengths[idx-1];

	var tp = this.toolpath[idx];
	tp.getToolPositionByD(location, axis, d);
    },

    makeSceneGraph : function(cx, loadables, xform) {
	
	var ret = new SGNode(cx, this, xform);
	
	for (var i=0; i<this.toolpath.length; i++)
	    ret.appendChild(this.toolpath[i].makeSceneGraph(cx, loadables, xform));

	this.tool = this.tool_shape.makeSceneGraph(cx, loadables);
	
	return ret;
    },

    
});
