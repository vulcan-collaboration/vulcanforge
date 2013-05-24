/* $RCSfile: ShapeBuilder.js,v $
 * $Revision: 1.5 $ $Date: 2012/04/25 15:46:31 $
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
 *  Utility class to build object JS objects from DOM data on demand.
 * 
 * This maintains two associative arrays, both indexes by ID.  One for XML
 * DOM elements, and the other for the JS objects created from those elements.
 * The expected pattern to use this is in the constructor for the JS object:
 *
 *   function Foo(builder, id) {
 *       var ret = builder.make(id, this, "foo");
 *       if (ret) return ret;  // Object already exists -- return it 
 *       var el = builder.getElement(id);
 *       this.name = el.getAttribute("name");;
 *   }
 *
 * Note that this pattern takes advantage of the fact that a constructor can
 * return something other than this, and in that case, the newly created object
 * is discarded and replaced with the (pre existing) value actually returned.
 */

"use strict";

function ShapeBuilder(element) {
    this.root_element = element;
    this.elmap = build_element_id_map(element);
    this.objs = {};
}

/* Flag value to indicate that an object is getting built. */
ShapeBuilder.IN_PROCESS = 1;

METHODS (ShapeBuilder, {

    getElement : function(id) {
	return this.elmap[id];
    },
    
    find : function(id) {
	return this.objs[id];
    },

    /*
     * Look for a JS object corresponding to an id in the root element.
     * If an object already exists, return it.  Otherwise, initialize the
     * value for that slot to the fallback object and return null.
     *
     * This function can also optionally assert that the element with the
     * specified ID has the correct tagname.
     *
     */
    make : function(id, fallback, elname) {
	if (!id)
	    throw new Error("null id");
	
	var ret = this.objs[id];
	if (ret)
	    return ret;

	if (elname) {
	    var el = this.getElement(id);
	    if (el.tagName != elname)
		throw new Error ("unexpected element name:" + el.tagName
				 +" wanted: "+elname);
	}
	
	this.objs[id] = fallback;
	return null;
    }
	
});
