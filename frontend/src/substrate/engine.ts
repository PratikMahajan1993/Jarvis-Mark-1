import { Mesh, Program, Renderer, Texture, Triangle } from "ogl";
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
  type SubstrateIn,
  type SubstrateOut,
} from "./protocol";
import {
  createSpring,
  HERO_SPRING,
  setSpringTarget,
  springAtRest,
  stepSpring,
  type SpringState,
} from "./spring";

const EYE_NOISE_SIZE = 128;
const EYE_FRAME_MS = 1000 / 30;
const STATS_MS = 1000;

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
  /** Cap main-thread shim to 30 fps (worker uses eye quantisation either way). */
  fpsCap?: 30 | 60;
};

/**
 * Transport-agnostic substrate engine — one ogl Renderer, one Triangle, eye pass only.
 * Phase 1a: no particles, rays, scissor, adaptive quality, or context-loss recovery.
 */
export class SubstrateEngine {
  private readonly postOut: (msg: SubstrateOut) => void;
  private readonly fpsCap: number;

  private renderer: Renderer | null = null;
  private mesh: Mesh | null = null;
  private program: Program | null = null;
  private raf = 0;
  private lastFrame = 0;
  private lastTick = 0;
  private frozen = false;
  private frozenTime = 0;
  private hidden = false;
  private reducedMotion = false;
  private disposed = false;

  private lens: Lens = "watch";
  private eyeSpring: SpringState = createSpring(1, 1);
  private mouse = { x: 0, y: 0, tx: 0, ty: 0 };

  private frameDeltas: number[] = [];
  private lastStatsAt = 0;
  private framesSinceStats = 0;
  private cssW = 1;
  private cssH = 1;

  constructor(postOut: (msg: SubstrateOut) => void, options: EngineOptions = {}) {
    this.postOut = postOut;
    this.fpsCap = options.fpsCap ?? 60;
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
        this.syncMotion();
        break;
      case "mode":
      case "quality":
        break;
      default:
        break;
    }
  }

  dispose() {
    this.disposed = true;
    this.stopLoop();
    const gl = this.renderer?.gl;
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    this.renderer = null;
    this.mesh = null;
    this.program = null;
  }

  private init(
    msg: Extract<SubstrateIn, { type: "init" }>,
  ) {
    this.reducedMotion = msg.reducedMotion;
    this.lens = msg.lens;
    const preset = LENS_SUBSTRATE[msg.lens];
    this.eyeSpring = createSpring(preset.eye, preset.eye);

    const renderer = new Renderer({
      canvas: msg.canvas as HTMLCanvasElement,
      alpha: true,
      depth: false,
      antialias: false,
      premultipliedAlpha: false,
      dpr: EYE_INTERNAL_SCALE,
      powerPreference: "high-performance",
      width: Math.max(1, msg.width),
      height: Math.max(1, msg.height),
    });
    const gl = renderer.gl;
    if (!gl) {
      return;
    }
    gl.clearColor(0, 0, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    const noiseData = generateNoiseTexture(EYE_NOISE_SIZE);
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

    const geometry = new Triangle(gl);
    const program = new Program(gl, {
      vertex: PRESENCE_VERTEX,
      fragment: PRESENCE_FRAGMENT,
      uniforms: {
        uTime: { value: 0 },
        uResolution: {
          value: [gl.canvas.width, gl.canvas.height, gl.canvas.width / Math.max(gl.canvas.height, 1)],
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
        uEye: { value: this.eyeSpring.x },
        uCenter: { value: [...preset.center] },
        uPresenceScale: { value: preset.scale },
      },
    });

    this.renderer = renderer;
    this.program = program;
    this.mesh = new Mesh(gl, { geometry, program });
    this.cssW = Math.max(1, msg.width);
    this.cssH = Math.max(1, msg.height);
    this.resize(msg.width, msg.height, msg.dpr);

    this.postOut({ type: "ready", webgl2: Boolean(renderer.isWebgl2) });
    this.lastStatsAt = performance.now();
    this.syncMotion();
    if (springAtRest(this.eyeSpring)) {
      this.postOut({ type: "settled", lens: this.lens });
    }
  }

  private setLens(lens: Lens, snap: boolean) {
    this.lens = lens;
    const preset = LENS_SUBSTRATE[lens];
    setSpringTarget(this.eyeSpring, preset.eye, snap || this.reducedMotion);
    if (this.program) {
      this.program.uniforms.uCenter.value = [...preset.center];
      this.program.uniforms.uPresenceScale.value = preset.scale;
    }
  }

  private resize(width: number, height: number, _dpr: number) {
    if (!this.renderer || !this.program) return;
    this.cssW = Math.max(1, width);
    this.cssH = Math.max(1, height);
    this.renderer.dpr = EYE_INTERNAL_SCALE;
    this.renderer.setSize(this.cssW, this.cssH);
    const gl = this.renderer.gl;
    this.program.uniforms.uResolution.value = [
      gl.canvas.width,
      gl.canvas.height,
      gl.canvas.width / Math.max(gl.canvas.height, 1),
    ];
  }

  private syncMotion() {
    const nextFrozen = this.reducedMotion || this.hidden;
    if (nextFrozen && !this.frozen) {
      this.frozenTime = performance.now();
    }
    this.frozen = nextFrozen;
    if (this.frozen) {
      this.stopLoop();
      this.renderFrame(this.frozenTime);
    } else {
      this.startLoop();
    }
  }

  private stopLoop() {
    if (!this.raf) return;
    cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  private startLoop() {
    this.stopLoop();
    this.lastFrame = 0;
    this.lastTick = performance.now();
    const minFrame = Math.max(EYE_FRAME_MS, 1000 / this.fpsCap);
    const tick = (time: number) => {
      this.raf = requestAnimationFrame(tick);
      if (this.frozen || this.disposed) return;
      if (time - this.lastFrame < minFrame) return;
      const dt = this.lastFrame ? (time - this.lastFrame) / 1000 : 1 / 30;
      this.lastFrame = time;
      this.step(dt, time);
    };
    this.raf = requestAnimationFrame(tick);
  }

  private step(dt: number, time: number) {
    stepSpring(this.eyeSpring, dt, HERO_SPRING);
    if (!this.frozen) {
      this.mouse.x += (this.mouse.tx - this.mouse.x) * 0.05;
      this.mouse.y += (this.mouse.ty - this.mouse.y) * 0.05;
    }
    this.renderFrame(time);
    this.noteFrame(dt * 1000, time);
    if (springAtRest(this.eyeSpring)) {
      // settled is idempotent enough for Phase 1a
    }
  }

  private renderFrame(time: number) {
    if (!this.renderer || !this.program || !this.mesh) return;
    const eye = this.eyeSpring.x;
    this.program.uniforms.uEye.value = eye;
    this.program.uniforms.uMouse.value = [this.mouse.x, this.mouse.y];
    // Noise time quantised to 30 Hz (vision rule 5 / owner lock).
    const tMs = this.frozen ? this.frozenTime : time;
    const quant = Math.floor(tMs / EYE_FRAME_MS) * EYE_FRAME_MS;
    this.program.uniforms.uTime.value = quant * 0.001;

    if (eye < 0.01) {
      const gl = this.renderer.gl;
      gl.clear(gl.COLOR_BUFFER_BIT);
      return;
    }
    this.renderer.render({ scene: this.mesh });
  }

  private noteFrame(deltaMs: number, time: number) {
    this.frameDeltas.push(deltaMs);
    if (this.frameDeltas.length > 60) this.frameDeltas.shift();
    this.framesSinceStats += 1;
    if (time - this.lastStatsAt < STATS_MS) return;
    const elapsed = (time - this.lastStatsAt) / 1000;
    const fps = elapsed > 0 ? this.framesSinceStats / elapsed : 0;
    const p95 = percentile(this.frameDeltas, 95);
    this.postOut({ type: "stats", fps, p95ms: p95, scale: EYE_INTERNAL_SCALE });
    this.lastStatsAt = time;
    this.framesSinceStats = 0;
  }
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[Math.max(0, idx)] ?? 0;
}
