/* $RCSfile: Assembly.js,v $
 * $Revision: 1.13 $ $Date: 2012/08/15 19:08:06 $
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
 */

"use strict";

function Assembly(tree_el, root_el, url, save_el, rootid, save_dir)
{
    this.tree_el = tree_el;
    this.tree_doc = tree_el.ownerDocument;
    this.url = url;
    this.save_dir = save_dir;

    console.log("Save dir="+save_dir);
    
    var builder = new ShapeBuilder(root_el);
    if (!rootid)
	rootid = root_el.getAttribute("root");

    this.rootid = rootid;
    this.product = new Product(builder, rootid, this);

    this.loadable_nodes = [];
    this.sg_context = new SGContext;
    var tree_root = this.product.makeSceneGraph(
	this.sg_context, this.loadable_nodes);

    this.tree = tree_root;
    
    var tree_ul = this.product.makeAsmTree(tree_el, this.tree);    
    this.setRootVisible();

    var tree_doc = tree_ul.ownerDocument;
    var menu = this.initTreeMenu(tree_doc.getElementById("menu"))

    this.html_tree = new Tree(tree_ul, menu);
    
//    this.enableEditLinks(false);
    
    if (save_el) {
	this.save_el = save_el;
	var tn_el = get_child_element(this.save_el, "tn");

	if (tn_el) {
	    this.tree.clearAllVisible();
	    this.tree.restore(tn_el);
	}

	var loaded_el = get_child_element(this.save_el, "loaded");
	if (loaded_el) {
	    // Also need to restore root_id
	    
	    throw new Error ("Have loaded element: not yet implemented");
	}

	if (save_el.hasAttribute("load")) {
	    
	    var load_ids = save_el.getAttribute("load").split(" ");
	    var idhash = {};
	    var i;
	    
	    for (i=0; i<load_ids.length; i++)
		idhash[load_ids[i]] = true;

	    var new_loadables = [];
	    for (i=0; i<this.loadable_nodes.length; i++) {
		var n = this.loadable_nodes[i];
		if (idhash[n.getId()])
		    new_loadables.push(n);
	    }

	    this.load_request = new_loadables;
	}
    }

}

STATIC(Assembly, {
    load : function(viewer, tree_el, param_str, load_fn) {

	var url;
	var root_id;
	
	var params = parse_params(param_str);
	if (!params) {
//	    console.log ("Parse failed");
	    url = param_str;
	}
	else {
	    url = params.url;
	    root_id = params.root;
	    var dir = params.dir;
//	    console.log ("URL param="+url);	    
	}
	
	LOADER.addRequest(url, function(doc) {
	    LOADER.setRequestBase(url);
	    
	    var root_el = doc.documentElement;

	    if (root_el.tagName == "save") {
		var save_el = root_el;

		if (!root_id)
		    root_id = root_el.getAttribute("root");
		
		url = root_el.getAttribute("ref");
		if (url == "")
		    url = "./";
		
		LOADER.addRequest(url, function(doc) {
		    
		    LOADER.setRequestBase(url);

		    Assembly.init(viewer, tree_el, doc.documentElement,
				  url, save_el, load_fn, root_id, dir);

		    return null;
		});
	    }

	    else {
		Assembly.init(viewer, tree_el, root_el, url, null, load_fn,
			      root_id, dir);
	    }

	    return null;
	});
	
//	tree_el.ownerDocument.defaultView.collapse_all();    
	
    },
	
    init : function(viewer, tree_el, root_el, url, save_el, load_fn, root_id,
		   save_dir) {
	LOADER.autorun = false;
	
	var asm = new Assembly(tree_el, root_el, url, save_el, root_id,
			       save_dir);

	var load_req;
	var ignore_cost = false;
	
	if (asm.load_request) {	    
	    ignore_cost = true;
	    load_req = asm.load_request;
	}
	else  {
	    console.log ("Loading nodes:" +asm.loadable_nodes.length);
	    load_req = asm.loadable_nodes;
	}
	
	load_req.sort(function(a,b) {
	    var va = Assembly.getLoaderRank(a);
	    var vb = Assembly.getLoaderRank(b);

	    if (va == vb) return 0;

	    // items w/o a sort function come first
	    if (va == null) return -1;
	    if (vb == null) return +1;

	    return vb-va;
	});

	var i;

	var cost = 0;

	for (i=0; i<load_req.length; i++) {
	    var n = load_req[i];

	    var ncost =0;
	    if (n.getCost)
		ncost = n.getCost();

	    if (!ignore_cost && cost+ncost > MAX_COST) {
		// Keep loading shapes if we hit one big one.
		console.log ("Skipping nodes due to cost");
		
		if (cost + 100< MAX_COST)
		    continue;

		break;
	    }

	    cost += ncost;

	    n.loadData(asm.tree, viewer.gl);
	}

	LOADER.onComplete = function() {
	    asm.tree.clearTree();
	    asm.tree.updateTree();
	};
	
//	LOADER.sortQueue();		
	LOADER.runLoadQueue();
	
	viewer.loadScenegraph(asm);
	viewer.menu = asm.initViewMenu(document.getElementById("menu"));	
	asm.viewer = viewer;
	
	if (load_fn) {
	    load_fn(asm);
	}
    },

    getLoaderRank : function(n) {
	if (!n.getRank)
	    return null;

	return n.getRank();
    },
});


// Callback method to complete save 
var saveComplete;

METHODS (Assembly, {

    initTreeMenu : function (menu_el) {
	var menu = new Menu(menu_el);
	
	var self = this;
    
	menu.addOption("menu_show", function(el) {
	    el.treenode.showNode();
	    self.redraw();
	    self.tree.updateTree();	
	});

	menu.addOption("menu_show_only", function(el) {
	    el.treenode.showOnlyNode();
	    self.redraw();	
	    self.tree.updateTree();	
	});
    
	menu.addOption("menu_hide", function(el) {
	    el.treenode.hideNode();
	    self.redraw();	
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_show_all", function(el) {
	    self.setRootVisible();
	    self.redraw();
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_open_subpart", function(el) {
	    console.log ("Open subtype: "+self.save_dir);
	    
	    el.treenode.sg.openSubassembly(self.url, self.save_dir);
	    self.redraw();		
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_select", function(el) {
	    el.treenode.select(true);
	    self.redraw();
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_select_all", function(el) {
	    self.getTree().selectAll(el.treenode.sg);
	    self.redraw();
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_unselect", function(el) {
	    el.treenode.select(false);
	    self.redraw();		
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_unselect_all", function(el) {
	    self.getTree().clearSelection();
	    self.redraw();
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_props", function(el) {
	    var tn = el.treenode;
	    tn.sg.showProperties(self.url, self.save_dir);	
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_load_part", function(el) {
	    var tn = el.treenode;
	    tn.showNode(tn);	
	    tn.sg.loadPartTop(self.tree);
	    
	    LOADER.sortQueue();
	    LOADER.runLoadQueue();
	});
	
	menu.addOption("menu_unload_part", function(el) {
	    var tn = el.treenode;
	    tn.sg.unloadPart(self.viewer.gl);
	    
	    self.tree.clearTree();
	    self.tree.updateTree();
	    
	    self.redraw();
	});

	menu.addOption("menu_edit_links", function(el) {
	    el.treenode.editLink();
	});
	
	return menu;
    },

    initViewMenu : function(menu_el) {
	var menu = new Menu(menu_el);
	
	var self = this;
    
	menu.addOption("menu_select_show", function() {
	    self.tree.showSelect(menu);
	    self.redraw();
	    self.tree.updateTree();	
	});

	menu.addOption("menu_toggle_select", function() {
	    self.tree.toggleSelect(menu);
	    self.redraw();
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_show_only", function() {
	    self.tree.showOnlySelected(menu);
	    self.redraw();	
	    self.tree.updateTree();	
	});
    
	menu.addOption("menu_hide", function() {
	    self.tree.hideSelected(menu);
	    self.redraw();	
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_show_all", function() {
	    self.setRootVisible();
	    self.redraw();
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_open_subpart", function() {
	    console.log ("Open subpart dir="+self.save_dir);
	    
	    self.tree.openSelectedSubassembly(self.url, self.save_dir, menu);
	    self.redraw();		
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_select_all", function() {
	    self.getTree().selectAllSelected(menu);
	    self.redraw();
	    self.tree.updateTree();	
	});

	menu.addOption("menu_select_parent", function() {
	    self.tree.selectParent(menu);
	    self.redraw();
	    self.tree.updateTree();	
	});
	
	menu.addOption("menu_unselect_all", function() {
	    self.getTree().clearSelection();
	    self.redraw();
	    self.tree.updateTree();		
	});
	
	menu.addOption("menu_props", function() {
	    self.tree.showSelectedProperties(self.url, self.save_dir, menu);
	    self.redraw();		
	});
	
	return menu;	
    },
    
    getBoundingBox : function() {
	return this.product.getBoundingBox();
    },

    draw : function(gl) {
	this.tree.draw(gl);
    },

    redraw : function() {
	this.viewer.draw();	
    },

    pick : function(id, keep) {
	console.log ("Picking "+id);
	var part;

	if (id) {
	    part = this.sg_context.getPart(id);
	    part.expandNode();
	    part.element.scrollIntoView(false);
	}
	
	if (keep) {
	    if (!part)
		return;

	    part.select(!part.isSelected())
	}
	else {
	    this.getTree().clearSelection();
	    if (part)
		part.select(true);
	}	

	this.redraw();
	this.tree.updateTree();
    },
    
    setRootVisible : function() {
	/* Make sure the visible flag is initialized on all nodes.
	 * For backwards-compatibility, is the flag is unset, we ignore it.
	 */
	this.tree.clearAllVisible();
	this.tree.getChild(0).setVisible(true);
    },

    getTree : function() {
	return this.tree;
    },
    
    clearAllVisible : function() {
	this.tree.clearAllVisible();
    },

    setViewer : function(view) {
	this.product.viewer = view;
	this.viewer = view;
    },

    // isEnabledEditLinks : function() {
    // 	return this.enabledEditLinks;
    // },

//     enableEditLinks : function(yn) {
// 	this.enabledEditLinks = yn;
// 	var ss = this.tree_doc.styleSheets[0];
// 	var rule = ss.cssRules[0];

// 	if (rule.selectorText != ".edlinks") 
// 	    throw new Error("Expecting first CSS rule to be .edlinks");
	
// 	var style = rule.style;
	
// //	console.log ("First rule: "+rule.selectorText + " " +style.cssText);

// 	style.cssText = yn ? "" : "display: none";
//     },    


    getStateDocument : function() {
	var doc = document.implementation.createDocument(null, "save", null);
	var root_el = doc.documentElement;
	root_el.setAttribute("type", "step-assembly");

	var ref = this.url;
	
	root_el.setAttribute("ref", ref);

	this.viewer.saveView(root_el);
	this.tree.save(root_el);
	this.saveLoaded(root_el);

	return doc;
    },

    saveState : function() {
	if (this.save_dir) {
	    console.log ("Opening popup: "+this.save_dir);
	    
	    window.open(this.save_dir, "save",
			"height=400,width=300,scrollbars=yes");	    
	    
	    var self = this;
	    var doc = self.getStateDocument();
	    if (!doc)
		throw new Error ("Could not save state");
	
	    
	    saveComplete = function(path) {

		var req = new XMLHttpRequest();

		req.addEventListener("load", function(e) {
//		    alert ("Upload complete: " + req.statusText);
		}, false);
		
		req.open("PUT", path);
		req.setRequestHeader("x-stvault-type", "bookmark");
		req.send(doc);
		
//		alert ("Save completed: "+path+ " " +doc);
	    }
	}
	else
	    this.saveStateOffline();
    },
    
    saveStateOffline : function() {
	var xdoc = this.getStateDocument();
	
	var str = new XMLSerializer().serializeToString(xdoc);
	// Add newlines
	str = str.replace(/>/g, ">\n");
	
	var win = window.open(null, "save", "menubar,scrollbars");	
	var doc = win.document;
	doc.open("application/xml");
	doc.write(str);
	doc.close();
    },

    saveLoaded : function(parent_el) {

	var ids=[];
	var ln = this.loadable_nodes;
	var all_ids = []

	for (var i=0; i<ln.length; i++) {
	    
	    var n = ln[i];

	    all_ids.push(n.getId());
		
	    if (n.isLoaded())
		ids.push(n.getId());
	}

	parent_el.setAttribute("load", ids.join(" "));
	parent_el.setAttribute("root", this.rootid);
    },
    
    initialize : function() {
     	/* restore the state */
     	var save = this.save_el;
     	if (!save)
     	    return;
	
     	this.viewer.restoreView(get_child_element(save, "view"));
	
     	/* don't need the save data anymore */
     	delete this.save_el;
     },

    expandTree : function() {
	expand_all(this.tree_el);
    },
    
    collapseTree : function() {
	collapse_all(this.tree_el);
    },
    
});


/*************************************************/

function Product(builder, id, asm)
{
    var ret = builder.make(id, this, "product");
    if (ret)
	return ret;

    this.assembly = asm;    

    var el = builder.getElement(id);
    this.id = id;
    this.stepfile = el.getAttribute ("step");
    
    var i;
    this.shapes = [];
    this.bbox = new BoundingBox();

    this.name = el.getAttribute("name");
    
    var shapes = get_array_attrib(el, "shape");
    for (i=0; i<shapes.length; i++) {
	
	var shape = new Shape(builder, shapes[i]);
	shape.setProduct(this);
	
	this.shapes.push(shape);
	this.bbox.updateFrom(shape.getBoundingBox());
    }

    this.children = [];
    var children = get_array_attrib(el, "children");
    for (i=0; i<children.length; i++) {
	this.children.push(new Product(builder, children[i]));
    }
}

METHODS (Product, {

    getBoundingBox : function() {
     	return this.bbox;
    },

    getProductName : function() {return this.name;},

    getName : function() {return "Product";},
    
    makeSceneGraph : function(cx, loadables) {
	var ret = new SGNode(cx, this);
	
     	var i;
     	for (i=0; i<this.shapes.length; i++) 
     	    ret.appendChild(this.shapes[i].makeSceneGraph(cx, loadables));

	return ret;
    },

    loadData : function() {
     	for (var i=0; i<this.shapes.length; i++) 
     	    this.shapes[i].loadData();	
    },

    getStepFile : function() {
	return this.stepfile;
    },
	
    
    makeAsmTree : function(el, tn) {
	
	var doc = el.ownerDocument;
	var ul = doc.createElement("ul");
	ul.classList.add("unselected");
	el.appendChild(ul);		
	
	var i;
	for (i=0; i<this.shapes.length; i++) {
	    var ch_tn = tn.getChild(i);
	    ch_tn.sg.makeAsmTree(ul, ch_tn);
	}

	return ul;
    },
    
});

/*************************************************/
// Add methods to SGNode for the assembly application

METHODS(SGNode, {
    getAssembly : function() {
	return this.getRoot().assembly;
    },

    getGeomView : function() {
	return this.getAssembly().viewer;
    },
    
    ////////////////////////////////////////////////////////
    // Menu options

    showNode : function() {
	
	if (this.isVisible())
	    return;
	
     	this.clearAllVisible();
     	this.setVisible(true);
    },


    showOnlyNode : function() {
	this.getRoot().assembly.clearAllVisible();	
	this.setVisible(true);
    },

    hideNode : function() {
//	if (!this.isVisible())
//	    return;
	
	this.clearAllVisible();
	this.hideBranch();
	this.visible = false;
	
//	this.setHidden(true);
    },

    selectAll : function(sg) {
	
	if (this.sg == sg) {
	    this.select(true);
	    return;
	}

	for (var i=0; i<this.children.length; i++) 
	    this.children[i].selectAll(sg);
    },
    
    select : function(yn) {
	this.setSelected(yn);
    },

    getLabel : function() {
	if (this.sg.getLabel)
	    return this.sg.getLabel();
	return null;
    },

    appendSelected : function(arr, menu, force) {
	if (!force)
	    this.appendSelectedChildren(arr);
	
	if ((force || arr.length == 0) && menu) {
	    console.log("No selection, forcing from menu click");
	    this.getGeomView().pickRaw(
		menu.popupX, menu.popupY, false);

	    this.appendSelectedChildren(arr);
	    if (arr.length > 0)
		return true;
	}

	return false;
    },

    appendSelectedChildren : function(arr) {
	if (this.isSelected())
	    arr.push(this);

	for (var i=0; i<this.children.length; i++)
	    this.children[i].appendSelectedChildren(arr);
    },

    showSelect : function(menu) {
	console.log ("Show select");
	
	var sel = [];
	var impl = this.appendSelected(sel, menu);

	var shown = false;
	for (var i=0; i<sel.length; i++) {
	    var n = sel[i];
	    if (!n.isVisible()) {
		n.showNode();
		shown = true;
	    }
	}

	if (shown || impl)
	    return;

	this.appendSelected(sel, menu, true);
    },
    
    toggleSelect : function(menu) {
	var sel = [];
	var impl = this.appendSelected(sel, menu);

	if (impl)
	    return;

	var old_sel = sel;
	sel = [];
	this.appendSelected(sel, menu, true);

	for (var i=0; i<old_sel.length; i++)
	    old_sel[i].select(true);
	
	for (var i=0; i<sel.length; i++) {
	    var s = sel[i];
	    if (old_sel.indexOf(s) != -1)
		s.select(false);
	    else
		s.select(true);
	}	    
    },
    
    hideSelected : function(menu) {
	var sel = [];
	var impl = this.appendSelected(sel, menu);
	for (var i=0; i<sel.length; i++) {
	    sel[i].hideNode();
	}

	this.clearSelection();
    },

    selectParent : function(menu) {
	var sel = [];
	this.appendSelected(sel, menu);

	var parents = [];
	var i;
	
	for (i=0; i<sel.length; i++) {
	    // Do not select the root node
	    var par = sel[i].getParent();
	    if (!par ||  par == this) {
		par = sel[i];
	    }
	    
	    if (parents.indexOf(par) == -1)
		parents.push(par);
	}

	for (i=0; i<parents.length; i++) {
	    var par = parents[i];
	    par.clearSelection();
	    par.select(true);
	}
    },
    
    showOnlySelected : function(menu) {

	var sel = [];
	var impl = this.appendSelected(sel, menu);

	if (sel.length == 0)
	    return;
	
	this.getRoot().assembly.clearAllVisible();

	for (var i=0; i<sel.length; i++) {
	    sel[i].showNode();
	}

	if (impl)
	    this.clearSelection();
	
    },
    
    openSelectedSubassembly : function(url, save_dir, menu) {
	var sels = [];
	var impl = this.appendSelected(sels, menu);

	if (sels.length == 0)
	    return;
	
	if (sels.length > 1) {
	    alert ("Only a single item can be selected for this option");
	    return;
	}

	sels[0].sg.openSubassembly(url, save_dir);

	if (impl)
	    this.clearSelection();
	
    },
    
    selectAllSelected : function(menu) {
	var sel = [];
	this.appendSelected(sel, menu);

	console.log ("All selected="+sel.length);
	
	for (var i=0; i<sel.length; i++) {
	    var n = sel[i];
	    this.selectAll(n.sg);
	}
	
    },
    
    showSelectedProperties : function(url, save_dir, menu) {
	var sels = [];
	var impl = this.appendSelected(sels);

	if (sels.length == 0)
	    return;
	
	if (sels.length > 1) {
	    alert ("Only a single item can be selected for this option");
	    return;
	}
	
	sels[0].sg.showProperties(url, save_dir);
	if (impl)
	    this.getTree().clearSelection();
	

    },
    
    
    ////////////////////////////////////////////////////////

    setVisible : function(yn) {
	this.hasVisible = true;
	this.visible = yn;

	this.updateStyle();
    },   

    hideBranch : function() {
	this.setVisible(false)
	
	var parent = this.parent;
	if (!parent) {
	    return;
	}

	var done = parent.isExactlyVisible();

	for (var i=0; i<parent.children.length; i++) {
	    var ch = parent.children[i];
	    if (ch != this && ch.isVisible())
		ch.setVisible(true);
	}

	if (done) 
	    parent.hasVisible = false;
	else 
	    parent.hideBranch();
    },

    
    // Expand the HTML tree so that the given node is visible.  This is used
    // when loading a part insure only the loaded geometry is expanded.
    // (of course, the user can open and close tree elements as they want)
    expand : function(sg) {
	var exp = false;
	
	if (this.sg.containsNode && this.sg.containsNode(sg)) {
	    exp = true;
	}

	else
	    for (var i=0; i<this.children.length; i++) {
		var ch = this.children[i];
		if (ch.expand(sg))
		    exp = true;
	    }

	if (exp) {
	    if (this.element)
		if (!this.element.classList.contains("leaf"))
		    this.element.classList.remove("closed");
	}

	return exp;
    },


    // Expand a given node and all its parents
    expandNode : function() {
	if (this.element)
	    if (!this.element.classList.contains("leaf"))
		this.element.classList.remove("closed");

	var par = this.getParent();
	if (par)
	    par.expandNode();
    },
    
    setHidden : function(yn) {
	this.hide = yn;
	this.setVisible(!yn);
    },

    isVisible : function() {
	if (this.hide)
	    return false;

	if (this.hasVisible)
	    return this.visible;

	if (this.parent)
	    return this.parent.isVisible();

	return false;
    },
    
    isExactlyVisible : function() {
	return this.hasVisible && this.visible;
    },
    
    clearVisible : function() {
	this.hasVisible = false;
//	this.visible = false;
	this.hide = false;

	this.updateStyle();
    },
    
    clearAllVisible : function() {
	this.clearVisible();
	for (var i=0; i<this.children.length; i++)
	    this.children[i].clearAllVisible();
    },

    clearSelection : function() {
	
	this.setSelected(false);
	
	for (var i=0; i<this.children.length; i++)
	    this.children[i].clearSelection();
    },

    countSelects : function() {
	var count = 0;

	if (this.isSelected()) {
	    count++;
	}

	for (var i=0; i<this.children.length; i++) {
	    count += this.children[i].countSelects();
	}

	return count;
    },
    
    setSelected : function(yn) {
	this.selected = yn;
    },

    isSelected : function() {
	return this.selected;
    },
           

    clearTree : function() {

	if (this.element)
	    this.element.classList.remove("noshell");
	
	for (var i=0; i<this.children.length; i++)
	    this.children[i].clearTree();	
    },    


    
    updateStyle : function() {
	if (!this.element)
	    return;
	
	var sg = this.sg;
	var cl = this.element.classList;

	if (sg.hasShell && !sg.hasShell()) {
	    cl.add("noshell");
	}
	else
	    cl.remove("noshell");

	if (this.hasVisible) {
	    if (this.visible) {
		cl.add("visible");
		cl.remove("invisible");
	    }
	    else {
		cl.add("invisible");
		cl.remove("visible");
	    }
	}

	else {
	    cl.remove("visible");
	    cl.remove("invisible");
	}

	var selected = this.isSelected();
	if (selected) {
	    cl.add("selected");
	    cl.remove("unselected");
	}
	else {
	    cl.remove("selected");
	    cl.add("unselected");
	}
	
    },

    
    updateTree : function() {

	this.updateStyle();
	
	for (var i=0; i<this.children.length; i++)
	    this.children[i].updateTree();	
    },    


    save : function(parent_el) {
	var doc = parent_el.ownerDocument;
	var el = doc.createElement("tn");
	var i;
	parent_el.appendChild(el);

	var sg = this.sg;

	if (sg.getLabel)
	    el.setAttribute("label", sg.getLabel());
	    
//	if (sg.saveElement)
//	    sg.saveElement(el);
	
	if (this.hide)
	    el.setAttribute("hide", "y");

	if (this.hasVisible)  {
	    if (this.visible)
		el.setAttribute("visible", "y");
	    else
		el.setAttribute("hide", "y");
	}

	if (this.links) {
	    for (i=0; i<this.links.length; i++) {
		var link = this.links[i];
		
		var link_el = doc.createElement("link");
		el.appendChild(link_el);
		link_el.setAttribute("href", link.href);
		if (link.text)
		    link_el.setAttribute("label", link.text);
	    }
	}
	
	for (i=0; i<this.children.length; i++) {
	    this.children[i].save(el);
	}
    },

    getLinks : function() {return this.links;},
    
    addLink : function(href, text, update) {
	if (!href)
	    return;

	var html_el = this.element;
	var html_doc = html_el.ownerDocument;

	if (!this.link_div) {
	    var ul_el = get_child_element(html_el, "UL");
	    this.link_div = html_doc.createElement("span");

	    if (ul_el)
		html_el.insertBefore(this.link_div, ul_el);
	    else
		html_el.appendChild(this.link_div);


	}
	
	var link_el = html_doc.createElement("a");
	link_el.target="_blank";
	
	if (update) {
	    if (!this.links)
		this.links = [];
	    this.links.push({href: href, text: text});
	}
	
	if (!text)
	    text = href;
	
	append_text(link_el, text);
	link_el.href = href;
	
	this.link_div.appendChild(link_el);
	this.link_div.appendChild(html_doc.createElement("br"));
    },

    updateLinks : function() {
	/* delete the existing link targets */
	if (this.link_div) {
	    var n = this.link_div;
	    delete this.link_div;
	    n.parentNode.removeChild(n);
	}

	var links = this.links;
	
	for (var i=0; i<links.length; i++) {
	    var link = links[i];
	    this.addLink(link.href, link.text, false);
	}
    },
    
    restore : function(el) {

//	console.log ("Restore: "+el.getAttribute("label"));
	
	if (el.hasAttribute("hide")) {
	    this.setVisible(false);
//	    this.hide = true;
	}
	if (el.hasAttribute("visible")) {
	    this.setVisible(true);
	}

	var nl = el.childNodes;
//	var ch = 0;

	var i;

	this.links = [];

	var unlabeled = [];
	
	for (i=0; i<nl.length; i++) {
	    var n = nl[i];

	    if (n.nodeType != Node.ELEMENT_NODE)
		continue;
	    
	    if (n.tagName == "link") {
	     	var href = n.getAttribute("href");		
	     	var text = n.getAttribute("label");
		
	     	this.addLink(href, text, true);
	    }
	    
	    else if (n.tagName == "tn") {
		var lab = n.getAttribute("label");
		if (lab) {
		    this.restoreLabeledChild(n, lab);
		}
		else {
//		    console.log ("Have unlabeled");
		    unlabeled.push(n);
		}
	    }
	}

	if (unlabeled.length > 0) {
	    var idx = 0;

//	    console.log ("Have unlabeled count= "+unlabeled.length);
//	    console.log ("Children="+this.children.length);
	    
	    for (i=0; i<this.children.length; i++) {
		var ch = this.children[i];
		if (ch.restored) continue;

		ch.restore(unlabeled[idx++])

		if (idx > unlabeled.length)
		    throw new Error("Have too many unlabeled items");
	    }
	}
    },

    restoreLabeledChild : function(el, label) {
	var i;
	for (i=0; i<this.children.length; i++) {
	    
	    var ch = this.children[i];
	    if (ch.restored) continue;
	    
	    if (ch.getLabel() != label) continue;

	    ch.restore(el);
	    ch.restored = true;
	    return;
	}

	throw new Error ("Could not find child with label '"+label
			 +"' to restore");
    },
    
    editLink : function() {
	var win = window.open("edlink.html", null,
			      "height=300,width=500,scrollbars");
	win.TREENODE = this;
    },
        
});
