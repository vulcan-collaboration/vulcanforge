function initAnimation() {
    //var container;
    //var camera, scene, renderer, sky, mesh, geometry, material,
    //i, h, color, colors = [], sprite, size, x, y, z;

    mouseX = 0, mouseY = 0;
    start_time = new Date().getTime();

    container = document.createElement( 'div' );
    container.id="cloudContainer";
    document.body.appendChild( container );

    camera = new THREE.Camera( 30, window.innerWidth / (window.innerHeight-285), 1, 3000 );
    camera.position.z = 6000;
    camera.position.x = 0;
    camera.position.y = 27;

    scene = new THREE.Scene();

    geometry = new THREE.Geometry();

    var texture = THREE.ImageUtils.loadTexture( $vf.resourcePath +  'cloud_texture.png' );
    texture.magFilter = THREE.LinearMipMapLinearFilter;
    texture.minFilter = THREE.LinearMipMapLinearFilter;

    var fog = new THREE.Fog( 0x252e40, - 100, 3000 );

    material = new THREE.MeshShaderMaterial( {

        uniforms: {

            "map": { type: "t", value:2, texture: texture },
            "fogColor" : { type: "c", value: fog.color },
            "fogNear" : { type: "f", value: fog.near },
            "fogFar" : { type: "f", value: fog.far }

        },
        vertexShader: vertexShader,
        fragmentShader: fragmentShader,

        depthTest: false

    } );

    var plane = new THREE.Mesh( new THREE.Plane( 64, 64 ) );

    for ( i = 0; i < 8000; i++ ) {

        plane.position.x = Math.random() * 1600 - 800;
        plane.position.y = - Math.random() * Math.random() * 200 - 15;
        plane.position.z = i;
        plane.rotation.z = Math.random() * Math.PI;
        plane.scale.x = plane.scale.y = Math.random() * Math.random() * 1.5 + 0.5;

        GeometryUtils.merge( geometry, plane );

    }

    mesh = new THREE.Mesh( geometry, material );
    scene.addObject( mesh );

    mesh = new THREE.Mesh( geometry, material );
    mesh.position.z = - 8000;
    scene.addObject( mesh );

    renderer = new THREE.WebGLRenderer( { antialias: false } );
    renderer.setSize( window.innerWidth, window.innerHeight );
    container.appendChild( renderer.domElement );

    window.addEventListener( 'resize', onWindowResize, false );

    animate();

}


function animate() {
    requestAnimationFrame( animate );
    if ( ACTIVE !== false ) {
        render();
    }
}

/**
 *
 *This is the renderer functions
 *
 */
function render() {

    position = ( ( new Date().getTime() - start_time ) * 0.008 ) % 8000;

    camera.position.z = Math.round( 100 * ( - position + 8000 ) ) / 100;

    renderer.render( scene, camera );

}




/**
 * 
 * On resizing the window we resize the rendere, too
 *
 */
function onWindowResize( event ) {

    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();

    renderer.setSize( window.innerWidth, window.innerHeight );

}


