/* $RCSfile: Workingstep.js,v $
 * $Revision: 1.10 $ $Date: 2012/08/14 18:58:30 $
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

function Workingstep(builder, id)
{
    var ret = builder.make(id, this, "workingstep");
    if (ret) return ret;
    var el = builder.getElement(id);

    this.initExecutable(builder, el);
    
    var or = el.getAttribute("orientation");
    if (or) {
	this.xform = new Placement(builder, or).xform;
    }

    this.op = new Operation(builder, el.getAttribute("op"));
}

Executable.RegisterSubtype("workingstep", Workingstep);

SUBTYPE(Executable, Workingstep);
METHODS (Workingstep, {

    getName : function() {return "Workingstep";},

    getOperation : function() {return this.op;},
    
    getBoundingBox : function() {
	var ret = new BoundingBox();
	
	ret.updateFrom(this.op.getBoundingBox(), this.xform);

	return ret;
    },
        
    makeSceneGraph : function(cx, loadables, xform) {
	var ret = new SGNode(cx, this, xform, this.xform);
	
	xform = ret.getXform();

	ret.appendChild(this.op.makeSceneGraph(cx, loadables, xform));

	this.makeSceneGraphExecutable(cx, loadables);
	
	return ret;
    },

    makeProjectTree : function(dom_parent, tn) {

	var doc = dom_parent.ownerDocument;
	var li = doc.createElement("li");

	li.treenode = tn;
	li.onclick = function() {
	    this.treenode.setActive();
	    this.treenode.redraw();
	};
	
	dom_parent.appendChild(li);
	
	this.appendTreeText(li, this.name);
	
    },

    setToolpathPos : function(ctl, tn, offset) {

	offset = get_float(offset);
	if (offset < 0.)
	    offset = 0.;
	else if (offset > this.op.length)
	    offset = this.op.length;
	
	ctl.setToolpath(this.op.length, offset);
    }
    
    
});
