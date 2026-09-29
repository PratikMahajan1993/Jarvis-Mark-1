import {
  Camera,
  Geometry,
  Mesh,
  Program,
  RenderTarget,
  Transform,
  Triangle,
  type OGLRenderingContext,
  type Renderer,
} from "ogl";
import { VISIBLE_HALF_HEIGHT, type SwarmUniforms } from "./swarm";

const TETRA_SIZE = 0.25;
const BLOOM_STRENGTH = 1.8;
const BLOOM_RADIUS = 0.4;
const AUTO_ROTATE_RAD_S = (Math.PI * 2) / 30;

const SWARM_VERTEX = /* glsl */ `
precision highp float;
attribute vec3 position;
attribute vec3 offset;
attribute vec3 icolor;
uniform mat4 projectionMatrix;
uniform mat4 viewMatrix;
uniform float uAngle;
uniform float uWorldScale;
uniform float uTetra;
uniform vec2 uShift;
uniform vec3 uTint;
uniform float uTintMix;
uniform float uBrightness;
varying vec3 vColor;
void main() {
  vec3 p = offset * uWorldScale + position * uTetra;
  float c = cos(uAngle);
  float s = sin(uAngle);
  p = vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
  vec4 clip = projectionMatrix * viewMatrix * vec4(p, 1.0);
  clip.xy += uShift * clip.w;
  gl_Position = clip;
  vColor = mix(icolor, uTint, uTintMix) * uBrightness;
}
`;

const SWARM_FRAGMENT = /* glsl */ `
precision highp float;
varying vec3 vColor;
void main() {
  gl_FragColor = vec4(vColor, 1.0);
}
`;

const QUAD_VERTEX = /* glsl */ `
attribute vec2 uv;
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const BLUR_FRAGMENT = /* glsl */ `
precision highp float;
uniform sampler2D tMap;
uniform vec2 uDir;
varying vec2 vUv;
void main() {
  vec4 c = texture2D(tMap, vUv) * 0.2270270270;
  c += texture2D(tMap, vUv + uDir * 1.3846153846) * 0.3162162162;
  c += texture2D(tMap, vUv - uDir * 1.3846153846) * 0.3162162162;
  c += texture2D(tMap, vUv + uDir * 3.2307692308) * 0.0702702703;
  c += texture2D(tMap, vUv - uDir * 3.2307692308) * 0.0702702703;
  gl_FragColor = c;
}
`;

const COMPOSITE_FRAGMENT = /* glsl */ `
precision highp float;
uniform sampler2D tScene;
uniform sampler2D tBloomNear;
uniform sampler2D tBloomFar;
uniform float uStrength;
uniform float uRadius;
uniform float uDim;
varying vec2 vUv;
void main() {
  vec3 scene = texture2D(tScene, vUv).rgb;
  vec3 bloom = texture2D(tBloomNear, vUv).rgb * (1.0 - uRadius * 0.5)
    + texture2D(tBloomFar, vUv).rgb * (0.5 + uRadius);
  vec3 c = (scene + bloom * uStrength * 0.45) * uDim;
  c = min(c, vec3(1.0));
  float a = max(c.r, max(c.g, c.b));
  gl_FragColor = vec4(c, a);
}
`;

/** Regular tetrahedron, radius 1 (three.js TetrahedronGeometry vertices). */
function tetrahedron() {
  const k = 1 / Math.sqrt(3);
  const position = new Float32Array([k, k, k, -k, -k, k, -k, k, -k, k, -k, -k]);
  const index = new Uint16Array([2, 1, 0, 0, 3, 2, 1, 3, 0, 2, 3, 1]);
  return { position, index };
}

/**
 * Swarm pass: 20k instanced tetrahedra into an offscreen target, then bloom
 * (downsample → separable blur at 1/2 and 1/4) and a premultiplied composite.
 */
export class SwarmPass {
  private readonly gl: OGLRenderingContext;
  private readonly camera: Camera;
  private readonly scene = new Transform();
  private readonly geometry: Geometry;
  private readonly program: Program;
  private readonly blurProgram: Program;
  private readonly compositeProgram: Program;
  private readonly blurMesh: Mesh;
  private readonly compositeMesh: Mesh;
  private rtScene: RenderTarget;
  private rtHalfA: RenderTarget;
  private rtHalfB: RenderTarget;
  private rtQuarterA: RenderTarget;
  private rtQuarterB: RenderTarget;
  private angle = 0;
  private bloomScale = 0.5;
  private width = 1;
  private height = 1;

  constructor(gl: OGLRenderingContext, count: number, positions: Float32Array, colors: Float32Array) {
    this.gl = gl;
    this.camera = new Camera(gl, { fov: 60, near: 0.1, far: 1000 });
    this.camera.position.z = 100;
    const tetra = tetrahedron();
    this.geometry = new Geometry(gl, {
      position: { size: 3, data: tetra.position },
      index: { data: tetra.index },
      offset: { instanced: 1, size: 3, data: positions, usage: gl.DYNAMIC_DRAW },
      icolor: { instanced: 1, size: 3, data: colors, usage: gl.DYNAMIC_DRAW },
    });
    this.geometry.instancedCount = count;
    this.program = new Program(gl, {
      vertex: SWARM_VERTEX,
      fragment: SWARM_FRAGMENT,
      uniforms: {
        uAngle: { value: 0 },
        uWorldScale: { value: 60 },
        uTetra: { value: TETRA_SIZE },
        uShift: { value: [0, 0] },
        uTint: { value: [1, 0.69, 0.125] },
        uTintMix: { value: 0 },
        uBrightness: { value: 1 },
      },
      cullFace: false,
      // The canvas is created with depth:false, so ogl never clears DEPTH_BUFFER_BIT.
      // Depth-testing the swarm against that stale buffer hides most of the volume
      // (back hemisphere, Cortex inner shell) on every section.
      depthTest: false,
      depthWrite: false,
    });
    const mesh = new Mesh(gl, { geometry: this.geometry, program: this.program });
    mesh.frustumCulled = false;
    mesh.setParent(this.scene);

    const triangle = new Triangle(gl);
    this.blurProgram = new Program(gl, {
      vertex: QUAD_VERTEX,
      fragment: BLUR_FRAGMENT,
      uniforms: { tMap: { value: null }, uDir: { value: [0, 0] } },
      depthTest: false,
      depthWrite: false,
    });
    this.compositeProgram = new Program(gl, {
      vertex: QUAD_VERTEX,
      fragment: COMPOSITE_FRAGMENT,
      uniforms: {
        tScene: { value: null },
        tBloomNear: { value: null },
        tBloomFar: { value: null },
        uStrength: { value: BLOOM_STRENGTH },
        uRadius: { value: BLOOM_RADIUS },
        uDim: { value: 1 },
      },
      depthTest: false,
      depthWrite: false,
    });
    this.blurMesh = new Mesh(gl, { geometry: triangle, program: this.blurProgram });
    this.compositeMesh = new Mesh(gl, { geometry: triangle, program: this.compositeProgram });

    this.rtScene = new RenderTarget(gl, { width: 1, height: 1, depth: false });
    this.rtHalfA = new RenderTarget(gl, { width: 1, height: 1, depth: false });
    this.rtHalfB = new RenderTarget(gl, { width: 1, height: 1, depth: false });
    this.rtQuarterA = new RenderTarget(gl, { width: 1, height: 1, depth: false });
    this.rtQuarterB = new RenderTarget(gl, { width: 1, height: 1, depth: false });
  }

  setBloomScale(scale: number) {
    if (Math.abs(scale - this.bloomScale) < 1e-4) return;
    this.bloomScale = scale;
    this.resize(this.width, this.height);
  }

  resize(width: number, height: number) {
    this.width = Math.max(1, width);
    this.height = Math.max(1, height);
    this.camera.perspective({ aspect: this.width / this.height });
    this.rtScene.setSize(this.width, this.height);
    const hw = Math.max(1, Math.round(this.width * this.bloomScale));
    const hh = Math.max(1, Math.round(this.height * this.bloomScale));
    this.rtHalfA.setSize(hw, hh);
    this.rtHalfB.setSize(hw, hh);
    const qw = Math.max(1, Math.round(hw / 2));
    const qh = Math.max(1, Math.round(hh / 2));
    this.rtQuarterA.setSize(qw, qh);
    this.rtQuarterB.setSize(qw, qh);
  }

  advanceRotation(dt: number) {
    this.angle = (this.angle + dt * AUTO_ROTATE_RAD_S) % (Math.PI * 2);
  }

  private blur(renderer: Renderer, from: RenderTarget, to: RenderTarget, dx: number, dy: number) {
    this.blurProgram.uniforms.tMap.value = from.texture;
    this.blurProgram.uniforms.uDir.value = [dx / to.width, dy / to.height];
    renderer.render({ scene: this.blurMesh, target: to });
  }

  render(renderer: Renderer, u: SwarmUniforms) {
    const worldHeight = u.height * 2 * VISIBLE_HALF_HEIGHT;
    const p = this.program.uniforms;
    p.uAngle.value = this.angle;
    p.uWorldScale.value = worldHeight;
    p.uTetra.value = TETRA_SIZE * Math.min(1.2, Math.max(0.45, Math.sqrt(worldHeight / 80)));
    p.uShift.value = [u.center[0] * 2 - 1, 1 - u.center[1] * 2];
    p.uTint.value = u.tint;
    p.uTintMix.value = u.tintMix;
    p.uBrightness.value = u.brightness;
    const attrs = this.geometry.attributes;
    attrs.offset!.needsUpdate = true;
    attrs.icolor!.needsUpdate = true;

    const gl = this.gl;
    gl.clearColor(0, 0, 0, 0);
    renderer.render({ scene: this.scene, camera: this.camera, target: this.rtScene });

    this.blur(renderer, this.rtScene, this.rtHalfA, 1, 0);
    this.blur(renderer, this.rtHalfA, this.rtHalfB, 0, 1);
    this.blur(renderer, this.rtHalfB, this.rtQuarterA, 1, 0);
    this.blur(renderer, this.rtQuarterA, this.rtQuarterB, 0, 1);

    const c = this.compositeProgram.uniforms;
    c.tScene.value = this.rtScene.texture;
    c.tBloomNear.value = this.rtHalfB.texture;
    c.tBloomFar.value = this.rtQuarterB.texture;
    c.uDim.value = u.dim;
    renderer.render({ scene: this.compositeMesh });
  }
}
