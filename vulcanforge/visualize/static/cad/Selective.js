/* $RCSfile: Selective.js,v $
 * $Revision: 1.6 $ $Date: 2012/08/14 18:58:30 $
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

function Selective(builder, id)
{
    var ret = builder.make(id, this, "selective");
    if (ret) return ret;

    var el = builder.getElement(id);
    this.initExecutable(builder, el);    

    this.elements = [];

    var els = get_array_attrib(el, "elements");

    for (var i=0; i<els.length; i++) {
//	console.log ("Sel element:" +els[i]);
	var ex = Executable(builder, els[i]);
	if (ex)
	    this.elements.push(ex);
    }
}

Executable.RegisterSubtype("selective", Selective);

SUBTYPE(Executable, Selective);

METHODS (Selective, {

    getName : function() {return "Selective";},
    
    getBoundingBox : function() {
	var bbox = new BoundingBox();
	
	for (var i=0; i<this.elements.length; i++) {
//	    console.log ("sel elements="+this.elements[i].getName());
	    bbox.updateFrom(this.elements[i].getBoundingBox());
	}

//	console.log ("Selective bbox="+bbox);
	return bbox;	
    },
    
    makeSceneGraph : function(cx, loadables, xform) {
	var ret = new SGNode(cx, this);

	for (var i=0; i<this.elements.length; i++)
	    ret.appendChild(this.elements[i].makeSceneGraph(cx, loadables,xform));

	this.makeSceneGraphExecutable(cx, loadables);
	
	return ret;
    },

    makeProjectTree : function(dom_parent, tn) {
	var doc = dom_parent.ownerDocument;
	var li = doc.createElement("li");
	dom_parent.appendChild(li);
	var n = this.appendTreeText(li, "SEL: "+this.name);

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
    },

    // FIXME - make SGNode subtype
    draw : function(gl, tn) {
	for (var i=0; i<this.elements.length; i++) {
	    var el = this.elements[i];

	    if (!el.isEnabled) {
		console.log ("el type="+el.getName());
		throw new Error ("No isenabled method");
	    }
	    
	    if (el.isEnabled()) 
		tn.getChild(i).draw(gl);
	}
    },

    getActive : function() {
	
    }
});
