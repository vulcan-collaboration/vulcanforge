/* $RCSfile: GLTransform.js,v $
 * $Revision: 1.5 $ $Date: 2012/03/07 23:38:26 $
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
 * 		----------------------------------------
 *
 * Model view matrix implementation.  This class provides the same
 * functionality as gl(Push|Pop)Matrix in the C API.  We require that the
 * shader have two uniform matrix parameters: one for the projection and
 * modelview (composed), and one for the normals (inverse transpose of the
 * model view matrix.
 */

"use strict";

/* Constructor */
function GLTransform(gl, u_proj, u_mv, u_normal)
{
    this.gl = gl;
//    this.u_proj_mv = u_proj_mv;
    this.u_proj = u_proj;
    this.u_mv = u_mv;
    this.u_normal = u_normal;
}

METHODS (GLTransform, {

    setProjection : function(m)
    {
	this.projection = m;
    },

    setModelView : function(m)
    {
	this.modelview = m;
    },

    /*
     * Flush the computed values to the GL uniform variables
     */    
    flush : function()
    {
//	if (!this.proj_view)
//	    this.proj_view = mat4.create();
	
//	mat4.multiply(this.projection, this.modelview, this.proj_view);    
	
	if (!this.normal)
	    this.normal = mat3.create();
	
	mat4.toInverseMat3(this.modelview, this.normal);
	mat3.transpose(this.normal);    

//	this.gl.uniformMatrix4fv(this.u_proj_mv, false, this.proj_view);
	this.gl.uniformMatrix4fv(this.u_proj, false, this.projection);
	this.gl.uniformMatrix4fv(this.u_mv, false, this.modelview);

	this.gl.uniformMatrix3fv(this.u_normal, false, this.normal);
    },
    
    /*
     * Return an object representing the current state info
     */
    save : function()
    {
	return {
	    modelview : new Float32Array(this.modelview)
	};
    },

    /*
     * Restore a saved state
     */
    restore : function(s)
    {
	this.modelview = mat4.create(s.modelview);
    },


    /*
     * Apply a transform to the given state.
     */
    apply : function(xf) {
	mat4.multiply(this.modelview, xf);
    },    
});

