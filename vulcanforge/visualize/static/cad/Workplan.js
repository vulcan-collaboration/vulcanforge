/* $RCSfile: Workplan.js,v $
 * $Revision: 1.9 $ $Date: 2012/08/14 18:58:30 $
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

function Workplan (builder, id)
{
    var ret = builder.make(id, this, "workplan");
    if (ret) return ret;
    
    var el = builder.getElement(id);

    this.initExecutable(builder, el);
    
    this.elements = [];
    
    var wp_els = get_array_attrib(el, "elements");
    
    for (var i=0; i<wp_els.length; i++) {
	var ex = Executable(builder, wp_els[i]);
	if (ex)
	    this.elements.push(ex);
    }
}

Executable.RegisterSubtype("workplan", Workplan);

SUBTYPE(Executable, Workplan);

METHODS (Workplan, {

    getName : function() {return "Workplan";},
    
    getBoundingBox : function() {
	var bbox = new BoundingBox();

	if (this.fixture)
	    bbox.updateFrom(this.fixture.getBoundingBox());
	
	for (var i=0; i<this.elements.length; i++) {
	    bbox.updateFrom(this.elements[i].getBoundingBox());
	}
	return bbox;
    },

    getTobe : function() {
	var ret = this.getTobeExecutable();
	if (ret) return ret;

	return this.elements[this.elements.length-1].getTobe();
    },

    makeSceneGraph : function(cox, loadables, xform) {
	
	var ret = new SGNode(cox, this);
	
	for (var i=0; i<this.elements.length; i++) {
	    var el = this.elements[i];
	    var ch = this.elements[i].makeSceneGraph(cox, loadables, xform);

	    ret.appendChild(ch);
	}

	this.makeSceneGraphExecutable(cox, loadables);
	
	return ret;
    },

    makeProjectTree : function(dom_parent, tn) {

	var doc = dom_parent.ownerDocument;
	var li = doc.createElement("li");
	dom_parent.appendChild(li);
	var n = this.appendTreeText(li, this.name);

	n.treenode = tn;
	n.onclick = function() {
	    this.treenode.setActive();
	    this.treenode.redraw();
	};
	
	var ul = doc.createElement("ul");
	li.appendChild(ul);
	
	for (var i=0; i<this.elements.length; i++) {
	    var child = this.elements[i];
	    var child_tn = tn.getChild(i);
	    	    
	    child.makeProjectTree(ul, child_tn);
	}

	return li;
    }
    
});
