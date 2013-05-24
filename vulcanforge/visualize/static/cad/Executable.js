/* $RCSfile: Executable.js,v $
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


/*
 * This is a bit of a hack, but it allows us to create the proper subtype
 * w/o knowing the needed type.
 */

function Executable(builder, id)
{
    /* For inheritance */
    if (!builder)
	return;
    
    var ret = builder.find(id);
    if (ret) return ret;

    var el = builder.getElement(id);
    var type = el.tagName;
    var func = Executable.subtypes[type];

    if (!func) {
	throw new Error ("No executable type for "+type);
    }

    if (func == Executable.unimplemented)
	return null;
    
    return new func(builder, id);
}

STATIC (Executable, {
    subtypes : {},
    
    RegisterSubtype : function(name, ctor) {Executable.subtypes[name] = ctor;},

    unimplemented : function() {
	throw new Error ("Unimplemented executable");
    }
});

METHODS (Executable, {

    initExecutable : function(builder, el) {
	this.name = el.getAttribute("name");
	this.enabled = get_boolean(el.getAttribute("enabled"), true);

	this.asis_shape = this.make_shape(builder, el.getAttribute("as_is"));
	this.tobe_shape = this.make_shape(builder, el.getAttribute("to_be"));

	this.fixture_shape
	    = this.make_shape(builder, el.getAttribute("fixture"));
	this.setup = this.make_setup(builder, el.getAttribute("setup"));
    },


    makeSceneGraphExecutable : function(cx, loadables) {
	if (this.setup) {
	    if (this.setup.fixture)
		this.fixture = this.setup.fixture.makeSceneGraph(cx, loadables);
	}
	else {
	    if (this.fixture_shape) {
		this.fixture = this.fixture_shape.makeSceneGraph(cx, loadables);
	    }
	}

	if (this.asis_shape)
	    this.asis = this.asis_shape.makeSceneGraph(cx, loadables);

	if (this.tobe_shape)
	    this.tobe = this.tobe_shape.makeSceneGraph(cx, loadables);
	
    },
    
    /* base version so there is something for subtypes to chain to */
    getTobeExecutable : function() {
	if (this.tobe)
	    return this.tobe;
	return null;
    },

    getTobe : function() {
	return this.getTobeExecutable();
    },

    getFixture : function() {
//	if (this.setup)
//	    return this.setup.fixture;
	    
	if (this.fixture) {
	    return this.fixture;
	}

	return null;
    },

    getFixtureWorkpieceRef : function() {
	if (this.setup)
	    return this.setup.workpiece_ref;
	    
	return null;
    },

    getFixtureMountRef : function() {
	if (this.setup)
	    return this.setup.mount_ref;
	    
	return null;
    },

    getSetupOrigin : function() {
	if (this.setup)
	    return this.setup.origin;
	    
	return null;
    },
    
    isEnabled : function() {
	return this.enabled;
    },

    appendTreeText : function(parent_el, str) {
	var re = /^\!.*?\!/;
	
	return append_text(parent_el, str.replace(re, ""));
    },
    
    /**********************************************/
    /* Private methods
     */

    make_shape : function(builder, id) {
	if (!id)
	    return null;

	return new Shape(builder, id);
    },

    make_setup : function(builder, id) {
	if (!id)
	    return null;

	return new Setup(builder, id);
    },
    
});


/* No-op executables (for now) */

Executable.RegisterSubtype("frame_definition_workingstep",
			   Executable.unimplemented);
Executable.RegisterSubtype("compensation_workingstep",
			   Executable.unimplemented);
