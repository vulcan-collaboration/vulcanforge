/* $RCSfile: Shape.js,v $
 * $Revision: 1.16 $ $Date: 2012/08/14 18:58:30 $
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

function Shape(builder, id)
{
    var ret = builder.make(id, this, "shape");
    if (ret)
	return ret;

    var el = builder.getElement(id);
    this.id = id;
    
    var shell_ids = el.getAttribute("shell");
    
    this.shells = [];
    if (shell_ids) {
	var shells = shell_ids.split(" ");
	
	for (var i=0; i<shells.length; i++) 
	    this.shells.push(new Shell(builder, shells[i]));
    }

    var annotation_ids = el.getAttribute("annotation");
    this.annotations = [];
    if (annotation_ids) {
	var annotations = annotation_ids.split(" ");
	for (var i=0; i<annotations.length; i++)
	    this.annotations.push(new Annotation(builder, annotations[i]));
    }
    
    this.children=[];
    
    var child_els = el.getElementsByTagName("child");
    if (child_els.length > 0) {
	
	for (var i=0; i<child_els.length; i++) {
	    var ch_el = child_els[i];
	    var m = mat4.create(ch_el.getAttribute("xform").split(" "));

	    var inv = mat4.create();
	    mat4.inverse(m, inv);
	    	    
	    var ref = ch_el.getAttribute("ref");

	    this.children.push( {
		shape : new Shape(builder, ref),
		xform : m,
		inv_xform : inv
	    });
	}
    }

    
}


STATIC (Shape, {
    FromDocument : function(el) {

	var builder = new ShapeBuilder(el);
	
	var root_ids = el.getAttribute("root").split(" ");
	if (root_ids.length <= 0) 
	    throw new Error ("No roots specified");

	var ret = [];
	for (var i=0; i<root_ids.length; i++) {
	    var shape = new Shape (builder, root_ids[i]);
	    ret.push(shape);
	}

	return ret[0];
    }
});


METHODS (Shape, {

    getName : function() {return "Shape";},

    getFacetCount : function() {
	var ret = 0;
	var i;
	for (i=0; i<this.children.length; i++) {
	    var ch = this.children[i].shape;
	    
	    if (ch.getFacetCount) {
		ret += ch.getFacetCount();
	    }
	}

	for (i=0; i<this.shells.length; i++) {
	    console.log("Shell="+i);
	    ret += this.shells[i].getFacetCount();
	}

	return ret;
    },

    getUnloadedCost : function() {
	var ret = 0;
	var i;
	for (i=0; i<this.children.length; i++) {
	    var ch = this.children[i].shape;
	   	    
	    if (ch.getUnloadedCost) {
		ret += ch.getUnloadedCost();
	    }
	}

	for (i=0; i<this.shells.length; i++) {
	    var shell = this.shells[i];
	    if (shell.isLoaded())
		continue;
	    ret += shell.getCost();
	}

	return ret;
    },
    
    getBoundingBox : function() {
	var i;
	var bbox = new BoundingBox;

	for (i=0; i<this.shells.length; i++) 
	    bbox.updateFrom(this.shells[i].bbox);

//	for (i=0; i<this.annotations.length; i++) 
//	    bbox.updateFrom(this.annotations[i].bbox);
	
	for (i=0; i<this.children.length; i++) {
	    var child = this.children[i];

	    if (!child.shape) {
		throw new Error ("No child.shape");
	    }
	    
	    bbox.updateFrom(child.shape.getBoundingBox(), child.inv_xform);
	}
	
	return bbox;	
    },

    
    drawSimple : function(gl) {
	var i;
	
	for (i=0; i<this.shells.length; i++)
	    this.shells[i].draw(gl);

	if (gl.show_annotations) {
	    for (i=0; i<this.annotations.length; i++) 
		this.annotations[i].draw(gl);
	}

	for (i=0; i<this.children.length; i++) {
	    var child = this.children[i];	    
	    var saved = gl.saveTransform();
	    
	    gl.applyTransform(child.xform);
	    gl.flushTransform();
	    child.shape.draw(gl);
	    gl.restoreTransform(saved);	
	}	
    },

    hasShell : function() {
	var i;
	if (this.shells.length > 0) {
	    for (i=0; i<this.shells.length; i++) {
		if (this.shells[i].isLoaded()) {
		    return true;
		}
	    }

	}

	for (var i=0; i<this.children.length; i++) {
	    if (this.children[i].shape.hasShell())
		return true;
	}

	return false;
    },
    
    draw : function(gl, tn) {
	
	throw new Error("Shape.draw called");
	
	if (!tn)
	    this.drawSimple(gl);
    },

    
    makeSceneGraph : function(cx, loadables, xform, ch_xform) {

	this.children.sort(function(a,b) {
	    var na = a.shape.getLabel();
	    var nb = b.shape.getLabel();

	    if (na == nb) return 0;
	    if (!na) return +1;
	    if (!nb) return -1;

	    if (na < nb)
		return -1;
	    return +1;
	});
	
	var ret = new SGShape(cx, this, xform, ch_xform);
	var i;

	for (i=0; i<this.children.length; i++) {
	    var child = this.children[i];
	    ret.appendChild(child.shape.makeSceneGraph(cx, loadables, ret.xform,
						       child.xform));
	}

	for (i=0; i<this.annotations.length; i++) {
	    this.annotations[i].incrCount(loadables);
	}

	for (i=0; i<this.shells.length; i++)
	    this.shells[i].incrCount(loadables);
	
	return ret;
    },

    containsNode : function(n) {
	for (var i=0; i<this.shells.length; i++)
	    if (this.shells[i] == n)
		return true;

	return false;
	
    },
    
    loadData : function(tree, gl) {
	var i;
	
	for (i=0; i<this.children.length; i++) {
	    var child = this.children[i];
	    child.shape.loadData(tree, gl);
	}
	
     	for (i=0; i<this.shells.length; i++) 
     	    this.shells[i].loadData(tree, gl);	

     	for (i=0; i<this.annotations.length; i++) 
     	    this.annotations[i].loadData(tree, gl);	
    },
    
    setProduct : function(p) {this.product = p;},

    makeAsmTree : function(dom_parent, tn) {

	var label;
	if (this.product) {
	    label = this.product.getProductName();
	    if (!label)
		label = this.id;
	}
	else {
	    label = "--raw shape-- " + this.id;
	}

	var doc = dom_parent.ownerDocument;
	var li = doc.createElement("li");
	dom_parent.appendChild(li);
	var n = append_text(li, label + " ", "product");

//	var link = doc.createElement("a");
//	link.treenode = tn;
//	var span = append_text(link, "[Links]");
//	span.className = "edlinks";
//	link.href = "#";

//	link.addEventListener("click", function(e) {
//	    this.treenode.editLink();
//	    e.stopPropagation();	    
//	}, false);
	
//	li.appendChild(link);
	
	li.appendChild(doc.createElement("br"));
	
	tn.element = li;
	n.treenode = tn;

	n.addEventListener("click", function(e) {	    
	    var tn = this.treenode;
	    var tree = tn.getRootNode();

	    var selected = tn.isSelected();	    

	    var preserve = e.shiftKey;

	    if (!preserve) {
		if (selected && tree.countSelects() > 0) 
		    selected = false;

		tree.clearSelection();
	    }

	    tn.select(!selected);
	    
	    tn.redraw();
	    tree.updateTree();
	    
	    e.stopPropagation();	    
	}, false);

	n.addEventListener("contextmenu", function(e) {
	    var prod = this.treenode.sg.product;
	    var stp = prod.getStepFile();
	    var menu = tn.getRoot().assembly.html_tree.menu;
	    
	    menu.setStepFile(stp);
	    
	    menu.popup(n);
	    e.stopPropagation();
	    e.preventDefault();
	}, false);
	
	if (this.children.length > 0) {
	    var ul = doc.createElement("ul");
	    li.appendChild(ul);
	
	    for (var i=0; i<this.children.length; i++) {
		var child = this.children[i];
		var child_tn = tn.getChild(i);
	    	
		child.shape.makeAsmTree(ul, child_tn);
	    }
	}

//	if (!this.hasShell()) {
//	    li.classList.add("noshell");
//	}
    },


    // saveElement : function(el) {
    // 	if (this.product)
    // 	    el.setAttribute("label", this.product.getProductName());	
    // },

    getLabel : function() {
	if (this.product)
	    return this.product.getProductName();
	return null;
    },
    
    toggleVisibility : function(tn) {
	if (tn.isExactlyVisible()) {
	    tn.clearAllVisible();
	    tn.getRoot().assembly.setRootVisible();
	}

	else {
	    tn.getRoot().assembly.clearAllVisible();
	    tn.setVisible(true);
	}	

	tn.redraw();
    },

    // showNode : function(tn) {
    // 	tn.clearAllVisible();
    // 	tn.setVisible(true);
    // 	tn.redraw();
    // },

    // FIXME: pass a Assembly object and get the url and save_dir from there
    getSubassemblyUrl : function(url, save_dir) {
	var prod = this.product.id;

	console.log ("getSubURL: "+save_dir);
	
	var loc = window.parent.location;

	var m = loc.href.match(/^(.*?)\?/);
	if (!m)
	    throw new Error ("No query string");

	var base = m[1];
//	console.log ("url="+base);

	var req = base+"?url="+url+"&root="+prod;
	if (save_dir)
	    req += "&dir="+save_dir
	
	return req;
    },
    
    openSubassembly : function(url, save_dir) {
	window.open(this.getSubassemblyUrl(url, save_dir));
    },

    showProperties : function(url, save_dir) {

	// The null parameter would really like to be a string, but then the
	// DOMContentLoaded does not trigger if we are resuing a window.
	// I suppose we could cache the win handle, and check it is still open
	// and should do so at some point.  For now, we just allow multiple
	// popups.	
	var win = window.open("asm-info.html", /*"info"*/ null,
			      "location=no,height=200,width=350");

	win.focus();
	
	var self = this;

	var count = this.getFacetCount();
	console.log ("Count="+count);

	var suburl = this.getSubassemblyUrl(url, save_dir);

	var stp = this.product.getStepFile();
	var stplink;
	
	if (stp) {
	    console.log ("Have stp file");
	    
	    var stpurl = resolve_url(stp, LOADER.base, null);;
	    var stplink = '<a href="javascript:open_url(\'' +stpurl+ '\')" >' +
		stp +
		'</a>';
	}
	else {
	    stplink = "No STEP File available for download";
	}
	
	var label;
	if (this.product) {
	    label = this.product.getProductName();
	}
	else {
	    label = "--raw shape--";
	}
	
	var vlink = '<a href="javascript:open_url(\'' +suburl+ '\')" >' +
	    label+
	    '</a>';

	
//	var link = '<a href="' +stpurl+ '" >' +
//	    label +
//	    '</a>';
	
	
	function load() {
	    var doc = win.document;

	    doc.getElementById("stp").innerHTML=stplink;
	    doc.getElementById("prod").innerHTML=vlink;
	    doc.getElementById("facet_count").innerHTML=count;
	}

	// if (win.document.getElementById("prod")) {
	//     console.log ("Forcing load");
	//     load()
	// }
	// else 
	win.addEventListener("DOMContentLoaded", load, false);	
    },

    loadPart : function(tree, gl) {

	var i;
	for (i=0; i<this.children.length; i++) {
	    var ch=this.children[i].shape;
	    if (ch.loadPart)
		ch.loadPart(tree);
	}

	for (i=0; i<this.shells.length; i++) 
	    this.shells[i].loadData(tree, gl);

	for (i=0; i<this.annotations.length; i++) 
	    this.annotations[i].loadData(tree, gl);
    },

    loadPartTop : function(tree, gl) {
	var new_count = this.getUnloadedCost();
	console.log ("New cost="+new_count);

	if (new_count > MAX_COST) {
	    if (!window.confirm(
		"You are about to load a large amount of data.  This could cause your browser to become unresponsive.  Do you wish to continue?"))
		return;
	}

	this.loadPart(tree, gl);
    },

    unloadPart : function(gl) {
	var i;
	for (i=0; i<this.children.length; i++) {
	    var ch=this.children[i].shape;
	    if (ch.unloadPart)
		ch.unloadPart(gl);
	}

	for (i=0; i<this.shells.length; i++) 
	    this.shells[i].unloadData(gl);

	for (i=0; i<this.annotations.length; i++) 
	    this.annotations[i].unloadData(gl);
	
    },
});


////////////////////////////////////////////////////

function SGShape(cx, shape, par_xform, ch_xform)
{
    this.SGNode(cx, shape, par_xform, ch_xform);
}

SUBTYPE(SGNode, SGShape);

METHODS (SGShape, {

    getName : function() {return "SGShape";},

    drawNode : function(gl) {

	var shape = this.sg;
	var i;
	
	for (i=0; i<shape.shells.length; i++)
	    shape.shells[i].draw(gl);

	for (i=0; i<shape.annotations.length; i++)
	    shape.annotations[i].draw(gl);
    },

});
