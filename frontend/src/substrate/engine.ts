import { Mesh, Program, Renderer, Texture, Triangle } from "ogl";
import { createParticlePass, type ParticlePass } from "./particles";
import {
  EYE_INTERNAL_SCALE,
  hexToVec3,
  PRESENCE_FRAGMENT,
  PRESENCE_VERTEX,
  STOCK_EYE,
} from "./presence.frag";
import {
  LENS_SUBSTRATE,
  type Lens,
  type SubstrateCanvas,
  type SubstrateIn,
  type SubstrateOut,
} from "./protocol";
import { createRayPass, type RayPass } from "./rays";
import {
  createSpring,
  HERO_SPRING,
  setSpringTarget,
  springAtRest,
  stepSpring,
  type SpringState,
} from "./spring";

const EYE_NOISE_SIZE = 128;
const STATS_MS = 1000;
/* Idle Watch at EvilEye dpr (0.55); degrade steps down from there. */
const QUALITY_SCALES = [0.55, 0.45, 0.4] as const;
const QUALITY_FPS: readonly (30 | 60)[] = [60, 30, 30];
const P95_DEGRADE_MS = 20;
const P95_RECOVER_MS = 14;
const RECOVER_HOLD_MS = 5000;
const QUALITY_COOLDOWN_MS = 2000;
const PILOT_SCALE = 0.15;
const WEIGHT_EPS = 0.01;

function generateNoiseTexture(size = EYE_NOISE_SIZE): Uint8Array {
  const data = new Uint8Array(size * size * 4);

  function hash(x: number, y: number, s: number): number {
    let n = x * 374761393 + y * 668265263 + s * 1274126177;
    n = Math.imul(n ^ (n >>> 13), 1274126177);
    return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
  }

  function noise(px: number, py: number, freq: number, seed: number): number {
    const fx = (px / size) * freq;
    const fy = (py / size) * freq;
    const ix = Math.floor(fx);
    const iy = Math.floor(fy);
    const tx = fx - ix;
    const ty = fy - iy;
    const w = freq | 0;
    const v00 = hash(((ix % w) + w) % w, ((iy % w) + w) % w, seed);
    const v10 = hash((((ix + 1) % w) + w) % w, ((iy % w) + w) % w, seed);
    const v01 = hash(((ix % w) + w) % w, (((iy + 1) % w) + w) % w, seed);
    const v11 = hash((((ix + 1) % w) + w) % w, (((iy + 1) % w) + w) % w, seed);
    return v00 * (1 - tx) * (1 - ty) + v10 * tx * (1 - ty) + v01 * (1 - tx) * ty + v11 * tx * ty;
  }

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let v = 0;
      let amp = 0.4;
      let totalAmp = 0;
      for (let o = 0; o < 8; o++) {
        const f = 32 * (1 << o);
        v += amp * noise(x, y, f, o * 31);
        totalAmp += amp;
        amp *= 0.65;
      }
      v /= totalAmp;
      v = (v - 0.5) * 2.2 + 0.5;
      v = Math.max(0, Math.min(1, v));
      const val = Math.round(v * 255);
      const i = (y * size + x) * 4;
      data[i] = val;
      data[i + 1] = val;
      data[i + 2] = val;
      data[i + 3] = 255;
    }
  }

  return data;
}

export type EngineOptions = {
  /** Cap main-thread shim to 30 fps (worker uses adaptive / quality otherwise). */
  fpsCap?: 30 | 60;
};

type Springs = {
  eye: SpringState;
  orb: SpringState;
  centerX: SpringState;
  centerY: SpringState;
  scale: SpringState;
  accentR: SpringState;
  accentG: SpringState;
  accentB: SpringState;
  dim: SpringState;
};

/**
 * Transport-agnostic substrate engine — one ogl Renderer.
 * Passes: rays → particles → presence. Springs, scissor, adaptive quality, context recovery.
 */
export class SubstrateEngine {
  private readonly postOut: (msg: SubstrateOut) => void;
  private readonly baseFpsCap: number;

  private canvas: SubstrateCanvas | null = null;
  private renderer: Renderer | null = null;
  private triangle: Triangle | null = null;
  private presenceMesh: Mesh | null = null;
  private presenceProgram: Program | null = null;
  private noiseTexture: Texture | null = null;
  private particles: ParticlePass | null = null;
  private rays: RayPass | null = null;

  private raf = 0;
  private lastFrame = 0;
  private frozen = false;
  private frozenTime = 0;
  private hidden = false;
  private reducedMotion = false;
  private disposed = false;
  private contextLost = false;
  private settledPosted = false;

  private lens: Lens = "watch";
  private springs: Springs = springsFromPreset("watch");
  private mouse = { x: 0, y: 0, tx: 0, ty: 0 };

  private frameDeltas: number[] = [];
  private lastStatsAt = 0;
  private framesSinceStats = 0;
  private cssW = 1;
  private cssH = 1;
  private deviceDpr = 1;

  private qualityNotch = 0;
  private internalScale = EYE_INTERNAL_SCALE;
  private targetFps: 30 | 60 = 60;
  private qualityForced = false;
  private lastQualityChangeAt = 0;
  private recoverCandidateSince = 0;
  private noiseData: Uint8Array | null = null;

  private onContextLost: ((e: Event) => void) | null = null;
  private onContextRestored: (() => void) | null = null;

  constructor(postOut: (msg: SubstrateOut) => void, options: EngineOptions = {}) {
    this.postOut = postOut;
    this.baseFpsCap = options.fpsCap ?? 60;
  }

  handle(msg: SubstrateIn) {
    if (this.disposed) return;
    switch (msg.type) {
      case "init":
        this.init(msg);
        break;
      case "resize":
        this.resize(msg.width, msg.height, msg.dpr);
        break;
      case "lens":
        this.setLens(msg.lens, false);
        break;
      case "pointer":
        this.mouse.tx = msg.x;
        this.mouse.ty = msg.y;
        break;
      case "glance":
        this.mouse.tx = msg.x;
        this.mouse.ty = msg.y;
        break;
      case "visibility":
        this.hidden = msg.hidden;
        this.syncMotion();
        break;
      case "reducedMotion":
        this.reducedMotion = msg.on;
        if (msg.on) this.snapAllSprings();
        this.syncMotion();
        break;
      case "quality":
        this.applyQualityOverride(msg.scale, msg.fps);
        break;
      case "mode":
        break;
      default:
        break;
    }
  }

  dispose() {
    this.disposed = true;
    this.stopLoop();
    this.detachContextListeners();
    const gl = this.renderer?.gl;
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    this.clearGpuRefs();
  }

  private init(msg: Extract<SubstrateIn, { type: "init" }>) {
    this.reducedMotion = msg.reducedMotion;
    this.lens = msg.lens;
    this.springs = springsFromPreset(msg.lens);
    if (this.reducedMotion) this.snapAllSprings();
    this.canvas = msg.canvas;
    this.cssW = Math.max(1, msg.width);
    this.cssH = Math.max(1, msg.height);
    this.deviceDpr = Math.max(0.1, msg.dpr || 1);
    this.noiseData = generateNoiseTexture(EYE_NOISE_SIZE);
    this.attachContextListeners(msg.canvas);
    this.buildGpu(msg.canvas);
    if (!this.renderer) return;
    this.postOut({ type: "ready", webgl2: Boolean(this.renderer.isWebgl2) });
    this.lastStatsAt = performance.now();
    this.maybePostSettled();
    this.syncMotion();
  }

  private attachContextListeners(canvas: SubstrateCanvas) {
    this.detachContextListeners();
    this.onContextLost = (e: Event) => {
      e.preventDefault();
      if (this.disposed) return;
      this.contextLost = true;
      this.stopLoop();
      this.clearGpuRefs();
      this.postOut({ type: "contextLost" });
    };
    this.onContextRestored = () => {
      if (!this.canvas || this.disposed) return;
      try {
        this.contextLost = false;
        this.buildGpu(this.canvas);
        if (!this.renderer) {
          this.contextLost = true;
          this.postOut({ type: "contextLost" });
          return;
        }
        this.postOut({ type: "ready", webgl2: Boolean(this.renderer.isWebgl2) });
        this.settledPosted = false;
        this.maybePostSettled();
        this.syncMotion();
      } catch (err) {
        console.error("[substrate] context restore failed", err);
        this.contextLost = true;
        this.postOut({ type: "contextLost" });
      }
    };
    canvas.addEventListener("webglcontextlost", this.onContextLost as EventListener);
    canvas.addEventListener("webglcontextrestored", this.onContextRestored as EventListener);
  }

  private detachContextListeners() {
    if (!this.canvas) return;
    if (this.onContextLost) {
      this.canvas.removeEventListener("webglcontextlost", this.onContextLost as EventListener);
    }
    if (this.onContextRestored) {
      this.canvas.removeEventListener(
        "webglcontextrestored",
        this.onContextRestored as EventListener,
      );
    }
    this.onContextLost = null;
    this.onContextRestored = null;
  }

  private clearGpuRefs() {
    this.renderer = null;
    this.triangle = null;
    this.presenceMesh = null;
    this.presenceProgram = null;
    this.noiseTexture = null;
    this.particles = null;
    this.rays = null;
  }

  private buildGpu(canvas: SubstrateCanvas) {
    this.clearGpuRefs();
    const renderer = new Renderer({
      canvas: canvas as HTMLCanvasElement,
      alpha: true,
      depth: false,
      antialias: false,
      premultipliedAlpha: false,
      dpr: this.internalScale,
      powerPreference: "high-performance",
      width: Math.max(1, this.cssW),
      height: Math.max(1, this.cssH),
    });
    const gl = renderer.gl;
    if (!gl) return;

    gl.clearColor(0, 0, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    const noiseData = this.noiseData ?? generateNoiseTexture(EYE_NOISE_SIZE);
    this.noiseData = noiseData;
    const noiseTexture = new Texture(gl, {
      image: noiseData,
      width: EYE_NOISE_SIZE,
      height: EYE_NOISE_SIZE,
      generateMipmaps: false,
      flipY: false,
    });
    noiseTexture.minFilter = gl.LINEAR;
    noiseTexture.magFilter = gl.LINEAR;
    noiseTexture.wrapS = gl.REPEAT;
    noiseTexture.wrapT = gl.REPEAT;

    const triangle = new Triangle(gl);
    const preset = LENS_SUBSTRATE[this.lens];
    const program = new Program(gl, {
      vertex: PRESENCE_VERTEX,
      fragment: PRESENCE_FRAGMENT,
      uniforms: {
        uTime: { value: 0 },
        uResolution: {
          value: [
            gl.canvas.width,
            gl.canvas.height,
            gl.canvas.width / Math.max(gl.canvas.height, 1),
          ],
        },
        uNoiseTexture: { value: noiseTexture },
        uPupilSize: { value: STOCK_EYE.pupilSize },
        uIrisWidth: { value: STOCK_EYE.irisWidth },
        uGlowIntensity: { value: STOCK_EYE.glowIntensity },
        uIntensity: { value: STOCK_EYE.intensity },
        uScale: { value: STOCK_EYE.scale },
        uNoiseScale: { value: STOCK_EYE.noiseScale },
        uMouse: { value: [0, 0] },
        uPupilFollow: { value: STOCK_EYE.pupilFollow },
        uFlameSpeed: { value: STOCK_EYE.flameSpeed },
        uEyeColor: { value: hexToVec3(STOCK_EYE.eyeColor) },
        uBgColor: { value: hexToVec3(STOCK_EYE.backgroundColor) },
        uLightMode: { value: STOCK_EYE.lightMode },
        uEye: { value: this.springs.eye.x },
        uOrb: { value: this.springs.orb.x },
        uCenter: { value: [this.springs.centerX.x, this.springs.centerY.x] },
        uPresenceScale: { value: this.springs.scale.x },
        uAccent: {
          value: [this.springs.accentR.x, this.springs.accentG.x, this.springs.accentB.x],
        },
        uDim: { value: this.springs.dim.x },
      },
      transparent: true,
      depthTest: false,
    });

    const particles = createParticlePass(gl);
    const rays = createRayPass(gl, triangle, { raysColor: [...preset.accent] });

    this.renderer = renderer;
    this.triangle = triangle;
    this.presenceProgram = program;
    this.presenceMesh = new Mesh(gl, { geometry: triangle, program });
    this.noiseTexture = noiseTexture;
    this.particles = particles;
    this.rays = rays;

    this.applyRendererSize();
  }

  private setLens(lens: Lens, snap: boolean) {
    this.lens = lens;
    this.settledPosted = false;
    const preset = LENS_SUBSTRATE[lens];
    const doSnap = snap || this.reducedMotion;
    setSpringTarget(this.springs.eye, preset.eye, doSnap);
    setSpringTarget(this.springs.orb, preset.orb, doSnap);
    setSpringTarget(this.springs.centerX, preset.center[0], doSnap);
    setSpringTarget(this.springs.centerY, preset.center[1], doSnap);
    setSpringTarget(this.springs.scale, preset.scale, doSnap);
    setSpringTarget(this.springs.accentR, preset.accent[0], doSnap);
    setSpringTarget(this.springs.accentG, preset.accent[1], doSnap);
    setSpringTarget(this.springs.accentB, preset.accent[2], doSnap);
    setSpringTarget(this.springs.dim, preset.dim, doSnap);
    if (doSnap) this.maybePostSettled();
  }

  private snapAllSprings() {
    for (const s of Object.values(this.springs)) {
      s.x = s.target;
      s.v = 0;
    }
  }

  private applyQualityOverride(scale: number, fps: 30 | 60) {
    this.qualityForced = true;
    const notch = closestNotch(scale);
    this.qualityNotch = notch;
    this.internalScale = scale;
    this.targetFps = fps;
    this.lastQualityChangeAt = performance.now();
    this.recoverCandidateSince = 0;
    this.applyRendererSize();
    // Leaving forced mode when returning to default EYE_INTERNAL_SCALE / 60 so adaptive can run again.
    if (Math.abs(scale - EYE_INTERNAL_SCALE) < 1e-6 && fps === 60) {
      this.qualityForced = false;
      this.qualityNotch = 0;
      this.internalScale = EYE_INTERNAL_SCALE;
      this.targetFps = 60;
    }
  }

  private resize(width: number, height: number, dpr: number) {
    this.cssW = Math.max(1, width);
    this.cssH = Math.max(1, height);
    this.deviceDpr = Math.max(0.1, dpr || 1);
    this.applyRendererSize();
  }

  private applyRendererSize() {
    if (!this.renderer || !this.presenceProgram) return;
    this.renderer.dpr = this.internalScale;
    this.renderer.setSize(this.cssW, this.cssH);
    const gl = this.renderer.gl;
    const w = gl.canvas.width;
    const h = gl.canvas.height;
    this.presenceProgram.uniforms.uResolution.value = [w, h, w / Math.max(h, 1)];
    this.particles?.resize(this.cssW, this.cssH, this.internalScale);
    this.rays?.resize(w, h);
  }

  private syncMotion() {
    if (this.contextLost || this.disposed) return;
    // visibility.hidden → stop after one frozen frame
    if (this.hidden) {
      this.frozen = true;
      this.frozenTime = performance.now();
      this.stopLoop();
      this.renderFrame(this.frozenTime);
      return;
    }
    // reducedMotion → springs snapped, loop at 30 fps, uTime frozen
    if (this.reducedMotion) {
      this.frozen = true;
      if (!this.frozenTime) this.frozenTime = performance.now();
      this.startLoop();
      return;
    }
    this.frozen = false;
    this.startLoop();
  }

  private stopLoop() {
    if (!this.raf) return;
    cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  private effectiveFpsCap(): number {
    if (this.reducedMotion) return 30;
    return Math.min(this.baseFpsCap, this.targetFps);
  }

  private startLoop() {
    this.stopLoop();
    this.lastFrame = 0;
    const tick = (time: number) => {
      this.raf = requestAnimationFrame(tick);
      if (this.disposed || this.contextLost || this.hidden) return;
      const minFrame = 1000 / this.effectiveFpsCap();
      if (this.lastFrame && time - this.lastFrame < minFrame) return;
      const dt = this.lastFrame ? (time - this.lastFrame) / 1000 : 1 / 30;
      this.lastFrame = time;
      this.step(dt, time);
    };
    this.raf = requestAnimationFrame(tick);
  }

  private step(dt: number, time: number) {
    if (!this.reducedMotion) {
      stepSpring(this.springs.eye, dt, HERO_SPRING);
      stepSpring(this.springs.orb, dt, HERO_SPRING);
      stepSpring(this.springs.centerX, dt, HERO_SPRING);
      stepSpring(this.springs.centerY, dt, HERO_SPRING);
      stepSpring(this.springs.scale, dt, HERO_SPRING);
      stepSpring(this.springs.accentR, dt, HERO_SPRING);
      stepSpring(this.springs.accentG, dt, HERO_SPRING);
      stepSpring(this.springs.accentB, dt, HERO_SPRING);
      stepSpring(this.springs.dim, dt, HERO_SPRING);
    }

    if (!this.frozen) {
      this.mouse.x += (this.mouse.tx - this.mouse.x) * 0.05;
      this.mouse.y += (this.mouse.ty - this.mouse.y) * 0.05;
    }

    const particleFrozen = this.frozen || this.reducedMotion;
    this.particles?.tick(dt * 1000, particleFrozen);

    this.renderFrame(time);
    this.noteFrame(dt * 1000, time);
    this.maybePostSettled();
  }

  private allSpringsAtRest(): boolean {
    return Object.values(this.springs).every(springAtRest);
  }

  private maybePostSettled() {
    if (this.settledPosted) return;
    if (!this.allSpringsAtRest()) return;
    this.settledPosted = true;
    this.postOut({ type: "settled", lens: this.lens });
  }

  private renderFrame(time: number) {
    if (!this.renderer || !this.presenceProgram || !this.presenceMesh) return;
    const gl = this.renderer.gl;
    const eye = this.springs.eye.x;
    const orb = this.springs.orb.x;
    const scale = this.springs.scale.x;
    const center: [number, number] = [this.springs.centerX.x, this.springs.centerY.x];
    const accent: [number, number, number] = [
      this.springs.accentR.x,
      this.springs.accentG.x,
      this.springs.accentB.x,
    ];
    const dim = this.springs.dim.x;

    this.presenceProgram.uniforms.uEye.value = eye;
    this.presenceProgram.uniforms.uOrb.value = orb;
    this.presenceProgram.uniforms.uCenter.value = center;
    this.presenceProgram.uniforms.uPresenceScale.value = scale;
    this.presenceProgram.uniforms.uAccent.value = accent;
    this.presenceProgram.uniforms.uDim.value = dim;
    this.presenceProgram.uniforms.uMouse.value = [this.mouse.x, this.mouse.y];

    // Continuous frame clock — no 30 Hz quant (that hold-and-jump made the iris flake).
    const tMs = this.frozen || this.reducedMotion ? this.frozenTime || time : time;
    this.presenceProgram.uniforms.uTime.value = tMs * 0.001;

    const pilot = scale < PILOT_SCALE;
    const glW = gl.canvas.width;
    const glH = gl.canvas.height;

    if (pilot) {
      // center Y is top-left (status cluster); scissor origin is bottom-left.
      const sideX = 3 * scale * glW;
      const sideY = 3 * scale * glH;
      const rawX = center[0] * glW - sideX * 0.5;
      const rawY = (1 - center[1]) * glH - sideY * 0.5;
      const x0 = Math.max(0, Math.floor(rawX));
      const y0 = Math.max(0, Math.floor(rawY));
      const x1 = Math.min(glW, Math.ceil(rawX + sideX));
      const y1 = Math.min(glH, Math.ceil(rawY + sideY));
      const sw = Math.max(1, x1 - x0);
      const sh = Math.max(1, y1 - y0);
      gl.enable(gl.SCISSOR_TEST);
      gl.scissor(x0, y0, sw, sh);
      gl.clear(gl.COLOR_BUFFER_BIT);
      this.renderer.render({ scene: this.presenceMesh, clear: false });
      gl.disable(gl.SCISSOR_TEST);
      return;
    }

    gl.disable(gl.SCISSOR_TEST);
    gl.clear(gl.COLOR_BUFFER_BIT);

    if (orb > WEIGHT_EPS && this.rays) {
      this.rays.setOrb(orb);
      this.rays.setColor(accent);
      this.rays.setMouse(this.mouse.x, this.mouse.y);
      this.rays.setTime(this.reducedMotion ? (this.frozenTime || time) * 0.001 : time * 0.001);
      this.renderer.render({ scene: this.rays.mesh });
    }

    if (orb > WEIGHT_EPS && this.particles) {
      this.particles.setOrb(orb);
      this.renderer.render({ scene: this.particles.mesh, camera: this.particles.camera });
    }

    this.renderer.render({ scene: this.presenceMesh });
  }

  private noteFrame(deltaMs: number, time: number) {
    this.frameDeltas.push(deltaMs);
    if (this.frameDeltas.length > 60) this.frameDeltas.shift();
    this.framesSinceStats += 1;

    if (!this.qualityForced && !this.reducedMotion && !this.hidden) {
      this.maybeAdaptQuality(time);
    }

    if (time - this.lastStatsAt < STATS_MS) return;
    const elapsed = (time - this.lastStatsAt) / 1000;
    const fps = elapsed > 0 ? this.framesSinceStats / elapsed : 0;
    const p95 = percentile(this.frameDeltas, 95);
    this.postOut({ type: "stats", fps, p95ms: p95, scale: this.internalScale });
    this.lastStatsAt = time;
    this.framesSinceStats = 0;
  }

  private maybeAdaptQuality(time: number) {
    if (this.frameDeltas.length < 30) return;
    const p95 = percentile(this.frameDeltas, 95);
    if (time - this.lastQualityChangeAt < QUALITY_COOLDOWN_MS) return;

    if (p95 > P95_DEGRADE_MS && this.qualityNotch < QUALITY_SCALES.length - 1) {
      this.qualityNotch += 1;
      this.internalScale = QUALITY_SCALES[this.qualityNotch]!;
      this.targetFps = QUALITY_FPS[this.qualityNotch]!;
      this.lastQualityChangeAt = time;
      this.recoverCandidateSince = 0;
      this.applyRendererSize();
      return;
    }

    if (p95 < P95_RECOVER_MS && this.qualityNotch > 0) {
      if (!this.recoverCandidateSince) this.recoverCandidateSince = time;
      if (time - this.recoverCandidateSince >= RECOVER_HOLD_MS) {
        this.qualityNotch -= 1;
        this.internalScale = QUALITY_SCALES[this.qualityNotch]!;
        this.targetFps = QUALITY_FPS[this.qualityNotch]!;
        this.lastQualityChangeAt = time;
        this.recoverCandidateSince = 0;
        this.applyRendererSize();
      }
    } else {
      this.recoverCandidateSince = 0;
    }
  }
}

function springsFromPreset(lens: Lens): Springs {
  const p = LENS_SUBSTRATE[lens];
  return {
    eye: createSpring(p.eye, p.eye),
    orb: createSpring(p.orb, p.orb),
    centerX: createSpring(p.center[0], p.center[0]),
    centerY: createSpring(p.center[1], p.center[1]),
    scale: createSpring(p.scale, p.scale),
    accentR: createSpring(p.accent[0], p.accent[0]),
    accentG: createSpring(p.accent[1], p.accent[1]),
    accentB: createSpring(p.accent[2], p.accent[2]),
    dim: createSpring(p.dim, p.dim),
  };
}

function closestNotch(scale: number): number {
  let best = 0;
  let bestDist = Infinity;
  for (let i = 0; i < QUALITY_SCALES.length; i++) {
    const d = Math.abs(QUALITY_SCALES[i]! - scale);
    if (d < bestDist) {
      bestDist = d;
      best = i;
    }
  }
  return best;
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[Math.max(0, idx)] ?? 0;
}
