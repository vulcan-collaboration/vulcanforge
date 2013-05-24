/* $RCSfile: Project.js,v $
 * $Revision: 1.11 $ $Date: 2012/08/14 18:58:30 $
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

function Project (builder)
{    
    var proj_el = builder.root_element.getElementsByTagName("project")[0];

    if (!proj_el) {
	throw new Error ("No project found");
    }

    this.asis = this.make_shape(builder, proj_el.getAttribute("as_is"));
    this.tobe = this.make_shape(builder, proj_el.getAttribute("to_be"));

    var wp = proj_el.getAttribute("wp");
    
    this.workplan = new Workplan(builder, wp);
}


METHODS (Project, {

    getName : function() {return "Project";},

    getBoundingBox : function() {
	var bbox = new BoundingBox();

	if (this.asis)
	    bbox.updateFrom(this.asis.getBoundingBox());
	if (this.tobe)
	    bbox.updateFrom(this.tobe.getBoundingBox());

	bbox.updateFrom(this.workplan.getBoundingBox());

	return bbox;
    },

    getTobe : function() {
	if (this.tobe)
	    return this.tobe;

	return this.workplan.getTobe();
    },

    getFixture : function() {
	return this.workplan.getFixture();
    },
    
    makeSceneGraph : function(cx, loadables) {
	var ret = new SGNode(cx, this);
	ret.appendChild(this.workplan.makeSceneGraph(cx, loadables));
	return ret;
    },
    
    makeProjectTree : function(wp_node, tn) {
        var doc = wp_node.ownerDocument;

	if (!doc)
	    throw new Error ("No document");
	
	var ul = doc.createElement("ul");
	wp_node.appendChild(ul);

	this.workplan.makeProjectTree(ul, tn.getChild(0));
	
	Tree(ul);

	tn.getChild(0).setActive();
    },

    
    /**********************************************/
    /* Private methods
     */

    make_shape : function(builder, id) {
	if (!id)
	    return null;

	return new Shape(builder, id);
    }
    
});
