 /* $RCSfile: GeomView.js,v $
 * $Revision: 1.16 $ $Date: 2012/08/15 19:08:06 $
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
 * 3D geometry viewer for XML file generated from STEP data.
 */

"use strict";


function check_gl_error(gl) {
    var error = gl.getError();
    if (error != gl.NO_ERROR && error != gl.CONTEXT_LOST_WEBGL) {
        var str = "GL Error: " + error;
        throw str;
    }
}


function get_script_element_text(id)
{
    var el = document.getElementById(id);
    if (!el) {
	throw new Error ("Cannot find element: "+id);
    }

    return el.text;
}



function loadShader(gl, type, shaderSrc) {
    var shader = gl.createShader(type);
    gl.shaderSource(shader, shaderSrc);
    gl.compileShader(shader);

    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS) &&
        !gl.isContextLost()) {
        var infoLog = gl.getShaderInfoLog(shader);
        gl.deleteShader(shader);
	throw new Error ("Error compiling shader:\n" + infoLog);
    }
    return shader;
}

/*
 * Creates the program object and loads the shaders into it.
 * The program object is returned
 */
function create_program(gl, vertex_shader_src, fragment_shader_src) {
    var vertexShader = loadShader(gl, gl.VERTEX_SHADER, vertex_shader_src);
    var fragmentShader=loadShader(gl, gl.FRAGMENT_SHADER, fragment_shader_src);

    // Create the program object
    var programObject = gl.createProgram();
    gl.attachShader(programObject, vertexShader);
    gl.attachShader(programObject, fragmentShader);

    // Link the program
    gl.linkProgram(programObject);

    // Check the link status
    var linked = gl.getProgramParameter(programObject, gl.LINK_STATUS);
    if (!linked && !gl.isContextLost()) {
        var infoLog = gl.getProgramInfoLog(programObject);
        gl.deleteProgram(programObject);
	throw new Error ("Error linking program:\n" + infoLog);
    }
    
    check_gl_error(gl);

    return programObject;
}


function create_program_by_element(gl, vid, fid)
{
    return create_program(gl, get_script_element_text(vid),
			  get_script_element_text(fid));
}


function load_shells(url) {
  var req = new XMLHttpRequest();

  req.open ("GET", url, false);
  req.send();
  
  var doc = req.responseXML;

  var root = doc.documentElement;

  var shells = root.getElementsByTagName("shell");

  var shell_list = new Array(shells.length);
  
  for (var i=0; i<shells.length; i++)
      shell_list[i] = new Shell(shells[i]);

  return shell_list;
}

function init_canvas(canvas) {
    
    var vshader = [
	"precision mediump float;",

	"uniform mat4 u_projMatrix;", 
	"uniform mat4 u_modelViewMatrix;", 

	// is the light on 
	"uniform bool u_light_on;",
	
	"attribute vec3 a_normal;",
	"attribute highp vec4 a_color;",
	"attribute vec4 a_position;",

	"varying vec4 v_eye_loc;",
	"varying highp vec4 v_Color;",
	"varying vec3 v_normal;",
	
	"void main()",
	"{",
	"    v_eye_loc = u_modelViewMatrix * a_position;",
	"    gl_Position = u_projMatrix * v_eye_loc;",
        "    v_Color = a_color;",
	"    v_normal = a_normal;",
	"}"
    ].join("\n");
    
    var fshader = [
	"precision mediump float;",

	"uniform mat3 u_normalMatrix;",
	"uniform vec3 u_ambient;",
	
	"uniform bool u_light_on;",

	"varying highp vec4 v_Color;",
	"varying vec4 v_eye_loc;",
	"varying vec3 v_normal;",


	// material properties.  If we want to change these, they should
	// be passed in as uniforms.
	"const float mat_ambient=.15;",
	"const float mat_diffuse=1.;",
	"const float mat_specular=.4;",
	"const float shine=6.;",
	
	"void main()",
	"{",
        "    if (!u_light_on) {",
	"      gl_FragColor = v_Color;",
	"      return;", 
	"    }",
	
	//  if u_normalMatrix were normalized, the call to normalize() 
	//  here would not be necessary 
        "    vec3 normal = normalize(u_normalMatrix * v_normal);",

	// ambient color generation
	"    float color_factor = .65 * mat_ambient;",
	
        "    float light_dot =  dot(normal, vec3(-.4082, .4082, .8165));",
	"    if ( light_dot > 0.)",
	"        color_factor += .45 * mat_diffuse * light_dot;",

	// vector from point to light.  We are placing a point light in the
	// scenegraph at the same level as the near clipping plane.
	// The z value of the vector may want to be a uniform so that it can
	// be derived from the camera_ratio.
	"    vec3 dir = normalize(vec3(0., 1., -3.) - v_eye_loc.xyz);",
	"    light_dot = dot(normal, dir);",
	"    if (light_dot > 0.) {",
	"        color_factor += .4 * mat_diffuse * light_dot;",
	"        vec3 s = normalize(dir + vec3(0.,0.,1.));",
	"        float ndot = dot(s,normal);",
	"        color_factor += mat_specular * max(pow(ndot, shine), 0.);",
	"    ",
	"    }",
	
	"    gl_FragColor = vec4(color_factor * v_Color.rgb, v_Color.a);",
	"}",
    ].join("\n");
    
    var gl = WebGLUtils.setupWebGL(canvas);

    if (!gl)
	throw new Error ("setupWebGL failed");
    
    if (typeof WebGLDebugUtils != 'undefined') {
	gl = WebGLDebugUtils.makeDebugContext(
	    gl, function(err, funcName, args) {
		throw new Error (WebGLDebugUtils.glEnumToString(err));
	    });
    }

    var prog = create_program(gl, vshader, fshader);
    gl.useProgram(prog);
    
    gl.proj_mtx = gl.getUniformLocation(prog, "u_projMatrix");
    if (!gl.proj_mtx) 
	throw new Error ("Could not get proj matrix");

    gl.mv_mtx = gl.getUniformLocation(prog, "u_modelViewMatrix");
    if (!gl.mv_mtx) 
	throw new Error ("Could not get model viewmatrix");
    
    gl.normal_mtx = gl.getUniformLocation(prog, "u_normalMatrix");

    gl.light_on = gl.getUniformLocation(prog, "u_light_on");
    if (gl.light_on) {
	gl.uniform1i(gl.light_on, true);
	gl.light = true;
    }
    
    gl.xforms = new GLTransform(gl, gl.proj_mtx, gl.mv_mtx, gl.normal_mtx);
    
    gl.pos_loc = gl.getAttribLocation(prog, "a_position");
    gl.norm_loc = gl.getAttribLocation(prog, "a_normal");
    gl.color_loc = gl.getAttribLocation(prog, "a_color");

    if (gl.pos_loc < 0 || gl.norm_loc < 0 || gl.color_loc < 0) 
	throw new Error ("Could not get location");

    /* used by the drawing code.  Initialize a default value.  We may want to
     * create a visibility object for various types of classes.
     */
    gl.show_annotations = true;
    
    return gl;
}


function create_rotation(controller)
{
    var mat = mat4.create();
    mat4.identity(mat);

    mat4.rotateX(mat, -controller.xRot * Math.PI / 180);
    mat4.rotateY(mat, -controller.yRot * Math.PI / 180);

    return mat;
};


function unproject(winX, winY, winZ, model, proj, view, objPos)
{
    /** @type {Array.<number>} */
    /** @type {Array.<number>} */
    var finalMatrix = mat4.create();

    mat4.multiply(proj, model, finalMatrix);
    mat4.inverse(finalMatrix);
    
    /* Map x and y from window coordinates */

    var xfract = (winX - view[0]) / view[2];
    var yfract = (winY - view[1]) / view[3];
    
    var inp = [
	xfract * 2 - 1,
	yfract * 2 - 1,	
	winZ * 2 - 1,
	1.0
        ];

    var out = new Array(4);

    mat4.multiplyVec4(finalMatrix, inp, out);
    
    if (out[3] === 0.0) {
	return false;
    }
    
    out[0] /= out[3];
    out[1] /= out[3];
    out[2] /= out[3];

    objPos[0] = out[0];
    objPos[1] = out[1];
    objPos[2] = out[2];
    
    return true;
};


function GeomView(canvas)
{
    var gl = init_canvas(canvas);
    if (!gl)
	throw new Error ("Failed to init GL");

    this.gl = gl;
    this.dragging = false;
    this.canvas = canvas;
    this.mouse_mode = "rotate";
    this.gl.draw_serial = 0;
    
    /* Need to assign to a temp so for the callback */
    var gv = this;

    gl.enable(gl.DEPTH_TEST);

    canvas.addEventListener("mousedown", function(ev) {
	console.log ("Buttons="+ev.button);
	
	if (ev.button != 0)
	    return;
	
	if (gv.menu && gv.menu.isUp()) {
	    gv.menu.popdown();
	}
	
	var x = ev.clientX;
	var y = ev.clientY;
	
	gv.mouseDown(x,y,ev);
    }, false);

    canvas.addEventListener("mouseup", function(ev) {
	var x = ev.clientX;
	var y = ev.clientY;

	gv.mouseUp(x,y);
    }, false);
    
    canvas.addEventListener("mousemove", function(ev) {	
	var x = ev.clientX;
	var y = ev.clientY;

	gv.mouseDrag(x,y);
    }, false);

    canvas.addEventListener("mouseout", function(ev) {	
	var x = ev.clientX;
	var y = ev.clientY;

	gv.mouseUp(x,y);
    }, false);

    canvas.addEventListener("contextmenu", function(ev) {
	if (gv.menu) {
	    gv.menu.popupAt(ev.clientX, ev.clientY);
	}
	
	ev.preventDefault();
    }, false);
};


METHODS (GeomView, {
    unproject : function(x,y,z)
    {
	var scene = this.getView();
	var ret = new Array(3);
	var gl = this.gl;
	
	unproject(x,y,z, scene.getModelViewMatrix(),
		  scene.getProjectionMatrix(),
		  gl.getParameter(gl.VIEWPORT), ret);
	
	return ret;
    },


    /*
     * Convert the window X,Y coordinates to the location on the unit sphere
     * inscribed in the window for trackball usage.
     */
    getTrackballCoords : function(x,y)
    {
	var w = this.canvas.width;
	var h = this.canvas.height;

	var d = Math.sqrt(w*w + h*h);
    
	x = (x-w/2.) / d;
	y = (y-h/2.) / d;
	
	var r = Math.sqrt(x*x + y*y);
    
	if ( r > 1) {
	    return [x,y,0];
	}
	
	var z = Math.sqrt(1 - r*r);
	
	return [x,y,z];
    },

    initRotate : function(x,y)
    {
	this.prevx = x;
	this.prevy = y;
	
	this.dragging = true;
    },


    dragRotate : function(x,y)
    {
	var xyz1 = this.getTrackballCoords(this.prevx, this.prevy);
	var xyz2 = this.getTrackballCoords(x,y);

	var axis = new Array(3);
	vec3.cross (xyz1, xyz2, axis);
	
	if (axis == [0,0,0]) {
	    throw new Error ("Zero axis");
	}
	
	var angle = Math.acos(vec3.dot(xyz1, xyz2)) * 3;
	
	this.getView().rotate(axis, angle);
    
	this.initRotate(x,y);
	this.draw();
    },


    initPan : function(x,y)
    {
	this.prevx = x;
	this.prevy = y;
	this.dragging = true;

	var o = new Array();
	var x1 = new Array();
	var y1 = new Array();
    
	var o = this.unproject (x,  y,  .5);
	var x1 = this.unproject(x+1,y,  .5);
	var y1 = this.unproject(x,  y+1,.5);
	
	this.dx = new Array(3);
	vec3.subtract(x1, o, this.dx);

	this.dy = new Array(3);
	vec3.subtract(y1, o, this.dy);
	
	var dx=this.dx;
	var dy=this.dy;
    },

    dragPan : function(x,y)
    {
	var pan_x = this.prevx - x;
	var pan_y = this.prevy - y;

	var delta = [
	    pan_x*this.dx[0] + pan_y*this.dy[0],
	    pan_x*this.dx[1] + pan_y*this.dy[1],
	    pan_x*this.dx[2] + pan_y*this.dy[2]
	];

	this.getView().moveCenter(delta);
	
	this.draw();
	
	this.initPan(x,y);    
    },

    pickRaw : function(x,y) {
	this.pick(x, this.canvas.height - y, false);
    },
    
    pick : function(x,y, shift) {
	
	if (!this.scenegraph || !this.scenegraph.pick) {
	    console.log ("No pick funtion");
	}
	
	var gl = this.gl;

	gl.draw_serial ++;

	gl.beginPick();

	this.initPick(x,y);
	this.scenegraph.draw(gl);
	check_gl_error(gl);
	
	var id = gl.endPick();

	console.log ("Pick draw pass complete");
	
	this.scenegraph.pick(id, shift);
    },
    
    mouseDown : function(x,y,e)
    {
	y = this.canvas.height - y;
	
	if (this.mouse_mode == 'rotate') 
	    this.initRotate(x,y);
	else if (this.mouse_mode == 'pan')
	    this.initPan(x,y);
	else if (this.mouse_mode == 'pick')
	    this.pick(x,y, e.shiftKey);
    },


    mouseUp : function(x,y)
    {
	y = this.canvas.height - y;
	
	this.dragging = false;
    },

    
    mouseDrag : function(x,y)
    {
	y = this.canvas.height - y;
	
	if (!this.dragging)
	    return;

	if (this.mouse_mode == 'rotate')
	    this.dragRotate(x,y);
	else if (this.mouse_mode == 'pan')
	    this.dragPan(x,y);    
    },
    

    initDraw : function()
    {
	var width = this.canvas.width;
	var height = this.canvas.height;
	this.gl.viewport(0,0, width, height);    
    
	var gl = this.gl;
	var view = this.getView();

	gl.clearColor(.1, .35, .40, 1.);	
	gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

	if (!view) return;

	gl.setProjection(view.getProjectionMatrix());
	gl.setModelView(view.getModelViewMatrix());
	gl.flushTransform();
	
	gl.enableVertexAttribArray(gl.pos_loc);
	gl.enableVertexAttribArray(gl.norm_loc);
	gl.disableVertexAttribArray(gl.color_loc);

	gl.setColor(.7, .7, .7, 1.);	
    },

    // FIXME factor this with initDraw above 
    initPick : function(x,y)
    {
	var width = this.canvas.width;
	var height = this.canvas.height;
	this.gl.viewport(0,0, width, height);    
    
	var gl = this.gl;
	var view = this.getView();

	gl.clearColor(0., 0., 0., 1.);		
	gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

	if (!view) return;

	gl.setProjection(view.getPickMatrix(x,y));

	gl.setModelView(view.getModelViewMatrix());
	gl.flushTransform();
	
	gl.enableVertexAttribArray(gl.pos_loc);
	gl.enableVertexAttribArray(gl.norm_loc);
	gl.disableVertexAttribArray(gl.color_loc);
    },
    
    draw : function() {
	var gl = this.gl;

	gl.draw_serial ++;
	
	this.initDraw();
	if (this.scenegraph) 
	    this.scenegraph.draw(gl);    
	check_gl_error(gl);
    },
    
    loadShells : function(url)
    {

	var shells = load_shells(url);
	this.shells = shells;

	var bbox = new BoundingBox;
	
	for (var i=0; i<shells.length; i++) {
	    var shell = shells[i];
	    shell.loadBuffers(this.gl);
	    bbox.updateFrom(shell.bbox);
	}
	
	this.getView().setViewBbox(bbox);    
    },

    
    loadScenegraph : function(sg)
    {
	this.scenegraph = sg;
	if (sg.setViewer)
	    sg.setViewer(this);

	if (!sg.getView) {
	    this.view = new ViewVolume(this.canvas);
	    this.view.setViewBbox(this.scenegraph.getBoundingBox());
	}

	if (sg.initialize)
	    sg.initialize();
    },

    getScenegraph : function() {return this.scenegraph;},
    
    getView : function() {
	if (this.scenegraph && this.scenegraph.getView)
	    return this.scenegraph.getView();
	return this.view;
    },
    
    setMouseMode : function(m)  {this.mouse_mode = m; },

    saveView : function(el) {
	this.view.saveState(el);
    },

    restoreView : function(el) {
	this.view.restoreState(el);
    }
});


/* Add methods to the WebGL context */
METHODS(WebGLRenderingContext, {

    setProjection : function(m) {
	this.xforms.setProjection(m);
    },

    setModelView : function(m) {
	this.xforms.setModelView(m);
    },

    flushTransform : function() {
	this.xforms.flush();
    },    

    saveTransform : function() {
	return this.xforms.save();
    },    

    restoreTransform : function(s) {
	this.xforms.restore(s);
    },    

    applyTransform : function(xf) {
	this.xforms.apply(xf);
    },

    /*****************************/
    setColor : function(r,g,b,a) {
	this.setColorv([r,g,b,a]);
    },
    
    setColorv : function(v) {

//	console.log ("set color");
	
	// when picking, we use the color to indicate the part, so do not
	// change it
	if (this.is_picking) {
	    return;
	}
	
	this.current_color = v;
	
	this.vertexAttrib4fv(this.color_loc, v);
    },
    
    saveColor : function() {
	return this.current_color;
    },
    
    restoreColor : function(s) {
	this.setColorv(s);
    },

    setLight : function(yn) {
	// when picking, we disable shading, so the color is constant.
	if (this.is_picking)
	    return;
	
	this.uniform1i(this.light_on, yn);
	this.light = yn;
    },
    
    getLight : function() {
	return this.light;
    },

    isPicking : function() {return this.is_picking;},

    beginPick : function() {
	this.setLight(false);
	this.is_picking = true;
	
	var gl = this;
	
	if (!this.pick_fb) {
	    var wh = 4;

	    this.pick_cb = this.createRenderbuffer();
	    this.bindRenderbuffer(this.RENDERBUFFER, this.pick_cb);
	    this.renderbufferStorage(this.RENDERBUFFER, this.RGB565, wh,wh);

	    var depth = this.createRenderbuffer();
	    this.bindRenderbuffer(this.RENDERBUFFER, depth);
	    this.renderbufferStorage(this.RENDERBUFFER,
				     this.DEPTH_COMPONENT16, wh,wh);
	    	    
	    var stencil = this.createRenderbuffer();
	    this.bindRenderbuffer(this.RENDERBUFFER, stencil);
	    this.renderbufferStorage(this.RENDERBUFFER,
				     this.STENCIL_INDEX8, wh,wh);

	    this.pick_fb = this.createFramebuffer();
	    this.bindFramebuffer(this.FRAMEBUFFER, this.pick_fb);
	    
	    this.framebufferRenderbuffer(
		this.FRAMEBUFFER, this.COLOR_ATTACHMENT0, this.RENDERBUFFER,
		this.pick_cb);

	    this.framebufferRenderbuffer(
		this.FRAMEBUFFER, this.DEPTH_ATTACHMENT, this.RENDERBUFFER,
		depth);

	    // this.framebufferRenderbuffer(
	    // 	this.FRAMEBUFFER, this.STENCIL_ATTACHMENT, this.RENDERBUFFER,
	    // 	stencil);	    
	}
	
	this.bindFramebuffer(this.FRAMEBUFFER, this.pick_fb);
	var stat = this.checkFramebufferStatus(this.FRAMEBUFFER);
	if (stat != this.FRAMEBUFFER_COMPLETE) {

	    this.endPick();
	    throw new Error ("Framebuffer status="+stat.toString(16) +
			     "complete=" +this.FRAMEBUFFER_COMPLETE);
	}
	
    },

    endPick : function() {

	var buff = new Uint8Array(4);

	this.readPixels(1,1,1,1,this.RGBA, this.UNSIGNED_BYTE, buff);
	
	this.is_picking = false;	
	this.bindFramebuffer(this.FRAMEBUFFER, null);
	this.setLight(true);

	var r = buff[0];
	var g = buff[1];
	var b = buff[2];

	var r = (buff[0] + 0.) / 256;
	var g = (buff[1] + 0.) / 256;
	var b = (buff[2] + 0.) / 256;
	
	r = (Math.round( r * (1 << 4)));
	g = (Math.round( g * (1 << 5)));
	b = (Math.round( b * (1 << 4)));

	return r << 9 | g << 4 | b;
    },

    setPickId : function(id) {

	// We only have 13 bits we can use reliably 
	if (id >= 0x2000)
	    throw new Error ("ID is too big -- cannot pick");

	// We are using a 565 rgb encoding 
	var r = ((id & 0x1e00) >> 9);
	var g = ((id & 0x01f0) >> 4);
	var b = ((id & 0x000f));

	// console.log (
	//     "Set pick id:"+id.toString(16) + " "
	// 	+ r.toString(16) + " " + g.toString(16) + " " + b.toString(16));

	// Note that we are leaving the LSB as zero.  It can be randomly
	// mangled by the shader
	r = (r << 1) / (1 << 5);
	g = (g << 1) / (1 << 6);
	b = (b << 1) / (1 << 5);
	
	// console.log ("Scaled:"+ " "
	// 	     + r + " " + g + " " + b);

	this.vertexAttrib4fv(this.color_loc, [r,g,b,1.]);
    },
    
});
