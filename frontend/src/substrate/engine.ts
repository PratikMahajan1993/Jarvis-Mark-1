import { Renderer } from "ogl";
import type { SubstrateCanvas, SubstrateIn, SubstrateOut } from "./protocol";
import { PARTICLE_COUNT, SwarmSim } from "./swarm";
import { SwarmPass } from "./swarmPass";

const STATS_MS = 1000;
const MAX_DPR = 1.5;
/** Degrade order (X5): bloom resolution first, then a 30 Hz simulation under a 60 Hz render. */
const QUALITY_NOTCHES = [
  { bloom: 0.5, simEvery: 1 },
  { bloom: 0.33, simEvery: 1 },
  { bloom: 0.25, simEvery: 2 },
] as const;
/** Formula-eval budget (X5). Desk blend samples sit at 9–10 ms; settled is ~5 ms. */
const SIM_DEGRADE_MS = 6;
const SIM_RECOVER_MS = 5.5;
const P95_DEGRADE_MS = 20;
const P95_RECOVER_MS = 14;
const RECOVER_HOLD_MS = 5000;
const QUALITY_COOLDOWN_MS = 2000;
/** Coalesce GPU-switch loss/restore so one flicker does not rebuild and post ready. */
const CONTEXT_LOSS_DEBOUNCE_MS = 500;

export type EngineOptions = {
  /** Cap the main-thread shim to 30 fps (the worker runs at 60). */
  fpsCap?: 30 | 60;
  /** Particle count override (tests and tooling only). */
  count?: number;
};

/**
 * Transport-agnostic substrate engine — the only owner of the ogl Renderer.
 * One pass: the particle swarm with bloom. Adaptive quality and context recovery.
 */
export class SubstrateEngine {
  private readonly postOut: (msg: SubstrateOut) => void;
  private readonly baseFpsCap: number;
  private readonly count: number;

  private canvas: SubstrateCanvas | null = null;
  private renderer: Renderer | null = null;
  private pass: SwarmPass | null = null;
  private sim: SwarmSim | null = null;

  private raf = 0;
  private lastFrame = 0;
  private hidden = false;
  private routeActive = true;
  private reducedMotion = false;
  private disposed = false;
  private contextLost = false;
  private wasSettled = false;

  private frameDeltas: number[] = [];
  private simSamples: number[] = [];
  private lastStatsAt = 0;
  private framesSinceStats = 0;
  private cssW = 1;
  private cssH = 1;
  private deviceDpr = 1;
  private renderDpr = 1;

  private qualityNotch = 0;
  private targetFps: 30 | 60 = 60;
  private qualityForced = false;
  private lastQualityChangeAt = 0;
  private recoverCandidateSince = 0;

  private onContextLost: ((e: Event) => void) | null = null;
  private onContextRestored: (() => void) | null = null;
  private contextDebounce: ReturnType<typeof setTimeout> | null = null;
  private pendingContext: "lost" | "restored" | null = null;

  /** One-shot glance/pulse FX — does not touch particle count or the 6 ms degrader. */
  private fxUntil = 0;
  private fxMult = 1;
  private fxCx: number | null = null;
  private fxCy: number | null = null;

  constructor(postOut: (msg: SubstrateOut) => void, options: EngineOptions = {}) {
    this.postOut = postOut;
    this.baseFpsCap = options.fpsCap ?? 60;
    this.count = options.count ?? PARTICLE_COUNT;
  }

  handle(msg: SubstrateIn) {
    if (this.disposed) return;
    switch (msg.type) {
      case "init":
        this.init(msg);
        return;
      case "resize":
        this.resize(msg.width, msg.height, msg.dpr);
        break;
      case "sections":
        this.sim?.setSpecs(msg.specs);
        break;
      case "orb":
        this.sim?.setOrb(msg.from, msg.to, msg.blend);
        this.wasSettled = false;
        break;
      case "mode":
        this.sim?.setMode(msg.mode);
        this.wasSettled = false;
        break;
      case "level":
        this.sim?.setLevel(msg.value);
        break;
      case "gather":
        this.sim?.setGather(msg.progress);
        break;
      case "route":
        this.routeActive = msg.active;
        this.syncMotion();
        break;
      case "visibility":
        this.hidden = msg.hidden;
        this.syncMotion();
        break;
      case "reducedMotion":
        this.reducedMotion = msg.on;
        if (this.sim) this.sim.reducedMotion = msg.on;
        this.syncMotion();
        break;
      case "quality":
        this.applyQualityOverride(msg.scale, msg.fps);
        break;
      case "glance":
        this.fxUntil = performance.now() + Math.max(0, msg.ms);
        this.fxMult = 1.08;
        this.fxCx = msg.x;
        this.fxCy = msg.y;
        break;
      case "pulse":
        this.fxUntil = performance.now() + (msg.kind === "warn" ? 500 : 280);
        this.fxMult = msg.kind === "warn" ? 1.22 : 1.12;
        this.fxCx = null;
        this.fxCy = null;
        break;
      case "pointer":
        return;
      default:
        return;
    }
    if (this.reducedMotion) this.drawStill();
  }

  dispose() {
    this.disposed = true;
    if (this.contextDebounce !== null) {
      clearTimeout(this.contextDebounce);
      this.contextDebounce = null;
    }
    this.pendingContext = null;
    this.stopLoop();
    this.detachContextListeners();
    const gl = this.renderer?.gl;
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    this.renderer = null;
    this.pass = null;
  }

  private init(msg: Extract<SubstrateIn, { type: "init" }>) {
    if (this.canvas) return;
    this.reducedMotion = msg.reducedMotion;
    this.canvas = msg.canvas;
    this.cssW = Math.max(1, msg.width);
    this.cssH = Math.max(1, msg.height);
    this.deviceDpr = Math.max(0.1, msg.dpr || 1);
    this.renderDpr = Math.min(this.deviceDpr, MAX_DPR);
    this.sim = new SwarmSim(this.count);
    this.sim.reducedMotion = msg.reducedMotion;
    this.sim.setGather(msg.gather);
    this.attachContextListeners(msg.canvas);
    this.buildGpu(msg.canvas);
    if (!this.renderer) {
      this.postOut({ type: "contextLost" });
      return;
    }
    this.postOut({ type: "ready", webgl2: Boolean(this.renderer.isWebgl2) });
    this.lastStatsAt = performance.now();
    this.syncMotion();
  }

  private attachContextListeners(canvas: SubstrateCanvas) {
    this.detachContextListeners();
    this.onContextLost = (e: Event) => {
      e.preventDefault();
      if (this.disposed) return;
      this.scheduleContextEvent("lost");
    };
    this.onContextRestored = () => {
      if (!this.canvas || this.disposed) return;
      this.scheduleContextEvent("restored");
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
      this.canvas.removeEventListener("webglcontextrestored", this.onContextRestored as EventListener);
    }
    this.onContextLost = null;
    this.onContextRestored = null;
  }

  /** Last loss/restore in a 500 ms window wins: one rebuild, or one contextLost. */
  private scheduleContextEvent(kind: "lost" | "restored") {
    this.pendingContext = kind;
    if (kind === "lost") {
      this.contextLost = true;
      this.stopLoop();
    }
    if (this.contextDebounce !== null) clearTimeout(this.contextDebounce);
    this.contextDebounce = setTimeout(() => {
      this.contextDebounce = null;
      this.flushContextEvent();
    }, CONTEXT_LOSS_DEBOUNCE_MS);
  }

  private flushContextEvent() {
    const kind = this.pendingContext;
    this.pendingContext = null;
    if (this.disposed || !kind) return;
    if (kind === "lost") {
      this.contextLost = true;
      this.stopLoop();
      this.renderer = null;
      this.pass = null;
      this.postOut({ type: "contextLost" });
      return;
    }
    if (!this.canvas) return;
    try {
      this.contextLost = false;
      this.buildGpu(this.canvas);
      if (!this.renderer) {
        this.contextLost = true;
        this.postOut({ type: "contextLost" });
        return;
      }
      this.postOut({ type: "ready", webgl2: Boolean(this.renderer.isWebgl2) });
      this.wasSettled = false;
      this.syncMotion();
    } catch (err) {
      console.error("[substrate] context restore failed", err);
      this.contextLost = true;
      this.postOut({ type: "contextLost" });
    }
  }

  private buildGpu(canvas: SubstrateCanvas) {
    this.renderer = null;
    this.pass = null;
    let renderer: Renderer;
    try {
      renderer = new Renderer({
        canvas: canvas as HTMLCanvasElement,
        alpha: true,
        // Default framebuffer has no depth. SwarmPass must not depth-test: ogl's
        // clear mask follows this flag, so a depth attachment would never be cleared.
        depth: false,
        antialias: false,
        premultipliedAlpha: true,
        dpr: this.renderDpr,
        powerPreference: "high-performance",
        width: this.cssW,
        height: this.cssH,
      });
    } catch (err) {
      console.error("[substrate] renderer failed", err);
      return;
    }
    if (!renderer.gl || !this.sim) return;
    this.renderer = renderer;
    this.pass = new SwarmPass(renderer.gl, this.count, this.sim.positions, this.sim.colors);
    this.pass.setBloomScale(QUALITY_NOTCHES[this.qualityNotch]!.bloom);
    this.applyRendererSize();
  }

  private applyQualityOverride(scale: number, fps: 30 | 60) {
    this.qualityForced = true;
    this.renderDpr = Math.max(0.25, Math.min(MAX_DPR, scale));
    this.targetFps = fps;
    this.lastQualityChangeAt = performance.now();
    this.recoverCandidateSince = 0;
    this.applyRendererSize();
  }

  private resize(width: number, height: number, dpr: number) {
    this.cssW = Math.max(1, width);
    this.cssH = Math.max(1, height);
    this.deviceDpr = Math.max(0.1, dpr || 1);
    if (!this.qualityForced) this.renderDpr = Math.min(this.deviceDpr, MAX_DPR);
    this.applyRendererSize();
  }

  private applyRendererSize() {
    if (!this.renderer || !this.pass) return;
    this.renderer.dpr = this.renderDpr;
    this.renderer.setSize(this.cssW, this.cssH);
    const gl = this.renderer.gl;
    this.pass.resize(gl.canvas.width, gl.canvas.height);
  }

  private syncMotion() {
    if (this.contextLost || this.disposed) return;
    if (!this.routeActive) {
      this.stopLoop();
      this.clear();
      return;
    }
    if (this.hidden) {
      this.stopLoop();
      return;
    }
    if (this.reducedMotion) {
      this.stopLoop();
      this.drawStill();
      return;
    }
    this.startLoop();
  }

  private clear() {
    const gl = this.renderer?.gl;
    if (!gl) return;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
  }

  private stopLoop() {
    if (!this.raf) return;
    cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  /** Reduced motion: snap to targets and draw exactly one frame per change. */
  private drawStill() {
    if (this.disposed || this.contextLost || !this.routeActive || this.hidden) return;
    if (!this.sim || !this.pass || !this.renderer) return;
    this.sim.step(1 / 60);
    this.renderWithFx();
    this.maybePostSettled();
  }

  private renderWithFx() {
    if (!this.sim || !this.pass || !this.renderer) return;
    const u = this.sim.uniforms;
    if (performance.now() >= this.fxUntil) {
      this.pass.render(this.renderer, u);
      return;
    }
    const savedB = u.brightness;
    const savedC = u.center;
    u.brightness = savedB * this.fxMult;
    if (this.fxCx != null && this.fxCy != null) {
      u.center = [
        savedC[0]! + (this.fxCx - savedC[0]!) * 0.35,
        savedC[1]! + (this.fxCy - savedC[1]!) * 0.35,
      ];
    }
    this.pass.render(this.renderer, u);
    u.brightness = savedB;
    u.center = savedC;
  }

  private effectiveFpsCap(): number {
    return Math.min(this.baseFpsCap, this.targetFps);
  }

  private startLoop() {
    if (this.raf) return;
    this.lastFrame = 0;
    const tick = (time: number) => {
      this.raf = requestAnimationFrame(tick);
      if (this.disposed || this.contextLost || this.hidden || !this.routeActive) return;
      const minFrame = 1000 / this.effectiveFpsCap();
      if (this.lastFrame && time - this.lastFrame < minFrame - 1) return;
      const dt = this.lastFrame ? Math.min(0.1, (time - this.lastFrame) / 1000) : 1 / 60;
      this.lastFrame = time;
      this.step(dt, time);
    };
    this.raf = requestAnimationFrame(tick);
  }

  private step(dt: number, time: number) {
    if (!this.sim || !this.pass || !this.renderer) return;
    this.sim.step(dt);
    this.pass.advanceRotation(dt);
    this.renderWithFx();
    this.simSamples.push(this.sim.lastSimMs);
    if (this.simSamples.length > 60) this.simSamples.shift();
    this.noteFrame(dt * 1000, time);
    this.maybePostSettled();
  }

  private maybePostSettled() {
    const settled = Boolean(this.sim?.settled());
    if (settled && !this.wasSettled) this.postOut({ type: "settled" });
    this.wasSettled = settled;
  }

  private noteFrame(deltaMs: number, time: number) {
    this.frameDeltas.push(deltaMs);
    if (this.frameDeltas.length > 60) this.frameDeltas.shift();
    this.framesSinceStats += 1;
    if (!this.qualityForced) this.maybeAdaptQuality(time);
    if (time - this.lastStatsAt < STATS_MS) return;
    const elapsed = (time - this.lastStatsAt) / 1000;
    const fps = elapsed > 0 ? this.framesSinceStats / elapsed : 0;
    const simMs = this.simSamples.reduce((a, b) => a + b, 0) / Math.max(1, this.simSamples.length);
    this.postOut({
      type: "stats",
      fps,
      p95ms: percentile(this.frameDeltas, 95),
      scale: this.renderDpr,
      simMs,
    });
    this.lastStatsAt = time;
    this.framesSinceStats = 0;
  }

  private setNotch(notch: number, time: number) {
    this.qualityNotch = notch;
    const q = QUALITY_NOTCHES[notch]!;
    this.pass?.setBloomScale(q.bloom);
    if (this.sim) this.sim.simEvery = q.simEvery;
    this.lastQualityChangeAt = time;
    this.recoverCandidateSince = 0;
  }

  private maybeAdaptQuality(time: number) {
    if (this.frameDeltas.length < 30 || this.simSamples.length < 15) return;
    if (time - this.lastQualityChangeAt < QUALITY_COOLDOWN_MS) return;
    const p95 = percentile(this.frameDeltas, 95);
    // p95 of simSamples, not the posted mean: at simEvery=2 the mean is diluted by
    // skipped eval frames and would recover mid-blend while eval is still > 6 ms.
    const simCost = percentile(this.simSamples, 95);
    const overBudget = simCost > SIM_DEGRADE_MS || p95 > P95_DEGRADE_MS;
    const underBudget = simCost < SIM_RECOVER_MS && p95 < P95_RECOVER_MS;
    if (overBudget && this.qualityNotch < QUALITY_NOTCHES.length - 1) {
      this.setNotch(this.qualityNotch + 1, time);
      return;
    }
    if (underBudget && this.qualityNotch > 0) {
      if (!this.recoverCandidateSince) this.recoverCandidateSince = time;
      if (time - this.recoverCandidateSince >= RECOVER_HOLD_MS) this.setNotch(this.qualityNotch - 1, time);
    } else {
      this.recoverCandidateSince = 0;
    }
  }
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[Math.max(0, idx)] ?? 0;
}
