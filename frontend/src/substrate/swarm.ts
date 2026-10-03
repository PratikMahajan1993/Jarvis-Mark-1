import { FORMULAS } from "./formulas";
import type { FormulaColor, FormulaTarget, OrbFormula, ThreeStub } from "./formulas/types";
import type { ControlValue, OrbSpec, OrbStateSpec, PresenceMode } from "./protocol";
import { createSpring, setSpringTarget, springAtRest, stepSpring, type SpringState } from "./spring";

export const PARTICLE_COUNT = 20000;
const BLEND_EPS = 1e-3;
const STAGGER = 0.15;
const BULGE = 0.12;

/** Same cube the landing gather eases away from. Shared with the GPU sim. */
export function makeScatter(count: number): Float32Array {
  const n = count * 3;
  const scatter = new Float32Array(n);
  let seed = 1337;
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  for (let j = 0; j < n; j++) scatter[j] = (rand() - 0.5) * 1.0;
  return scatter;
}

export type GpuFormulaState = {
  /** 0 cortex, 1 asci, 2 chat. */
  slot: number;
  clock: number;
  fitCy: number;
  fitInvH: number;
  radiusOuter: number;
  radiusInner: number;
  neuroActivity: number;
  chaosFactor: number;
  pulseSpeed: number;
  scale: number;
  flow: number;
  chaos: number;
  twist: number;
};

export type GpuFrame = {
  easeK: number;
  blend: number;
  gather: number;
  reduced: boolean;
  a: GpuFormulaState;
  b: GpuFormulaState;
};
/** Camera at z = 100 with a 60° vertical field of view: half the visible height at z = 0. */
export const VISIBLE_HALF_HEIGHT = 100 * Math.tan(Math.PI / 6);
const CONTROL_TAU_S = 0.13;
const LEVEL_TAU_S = 0.06;
const HITL_MIN_HEIGHT = 0.6;
const PULSE_AMP = 0.15;
const FIT_SAMPLE_TIMES = [0, 7.3, 19.1];
const PLACEMENT_SPRING = { k: 120, c: 20, m: 1.2 } as const;

const THREE_STUB: ThreeStub = {
  Vector3: class {
    constructor(
      public x = 0,
      public y = 0,
      public z = 0,
    ) {}
  },
};
const noop = () => undefined;

function clamp01(v: number) {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}

function smoothstep(v: number) {
  const t = clamp01(v);
  return t * t * (3 - 2 * t);
}

function hue2rgb(p: number, q: number, t: number) {
  if (t < 0) t += 1;
  if (t > 1) t -= 1;
  if (t < 1 / 6) return p + (q - p) * 6 * t;
  if (t < 1 / 2) return q;
  if (t < 2 / 3) return p + (q - p) * 6 * (2 / 3 - t);
  return p;
}

/** Reusable writer objects handed to formula bodies: no allocation per particle. */
class Writer {
  x = 0;
  y = 0;
  z = 0;
  r = 1;
  g = 1;
  b = 1;
  readonly target: FormulaTarget = {
    set: (x, y, z) => {
      this.x = x;
      this.y = y;
      this.z = z;
    },
  };
  readonly color: FormulaColor = {
    setRGB: (r, g, b) => {
      this.r = r;
      this.g = g;
      this.b = b;
    },
    setHSL: (h, s, l) => {
      const hh = ((h % 1) + 1) % 1;
      const ss = clamp01(s);
      const ll = clamp01(l);
      if (ss === 0) {
        this.r = this.g = this.b = ll;
        return;
      }
      const p = ll <= 0.5 ? ll * (1 + ss) : ll + ss - ll * ss;
      const q = 2 * ll - p;
      this.r = hue2rgb(q, p, hh + 1 / 3);
      this.g = hue2rgb(q, p, hh);
      this.b = hue2rgb(q, p, hh - 1 / 3);
    },
    set: (r, g, b) => {
      if (typeof r === "number" && typeof g === "number" && typeof b === "number") {
        this.r = r;
        this.g = g;
        this.b = b;
        return;
      }
      const hex = typeof r === "string" ? parseInt(r.replace("#", ""), 16) : Number(r);
      if (!Number.isFinite(hex)) return;
      this.r = ((hex >> 16) & 255) / 255;
      this.g = ((hex >> 8) & 255) / 255;
      this.b = (hex & 255) / 255;
    },
  };
}

export function resolveControl(v: ControlValue | undefined, level: number, fallback: number): number {
  if (v === undefined) return fallback;
  return typeof v === "number" ? v : v.base + v.level * level;
}

/** Per-formula runtime: its own never-restarting clock, eased controls and fitted bounds. */
export class FormulaRuntime {
  readonly formula: OrbFormula;
  clock = 0;
  rate = 1;
  /** Values handed to the body (speed controls pinned at idle). */
  readonly values: Record<string, number> = {};
  /** Normalisation: y-centre and 1 / height of the idle shape. */
  fitCy = 0;
  fitInvH = 1;
  private readonly writer = new Writer();
  private readonly addControl = (id: string, _l: string, _min: number, _max: number, initial: number) => {
    const v = this.values[id];
    return v === undefined ? initial : v;
  };

  constructor(formula: OrbFormula) {
    this.formula = formula;
    Object.assign(this.values, formula.params);
  }

  idleValue(id: string): number | undefined {
    return this.formula.params[id];
  }

  /** Ease controls and clock rate toward a state. */
  easeToward(state: OrbStateSpec | undefined, level: number, dt: number, snap: boolean) {
    const k = snap ? 1 : 1 - Math.exp(-dt / CONTROL_TAU_S);
    const controls = state?.controls ?? {};
    let targetRate = resolveControl(state?.rate, level, 1);
    for (const id of this.formula.speedControls) {
      const idle = this.idleValue(id);
      const wanted = controls[id];
      if (wanted !== undefined && idle) targetRate = resolveControl(wanted, level, idle) / idle;
    }
    this.rate += (targetRate - this.rate) * k;
    for (const id of Object.keys(this.formula.params)) {
      if (this.formula.speedControls.includes(id)) continue;
      const target = resolveControl(controls[id], level, this.formula.params[id]!);
      const cur = this.values[id] ?? target;
      this.values[id] = cur + (target - cur) * k;
    }
    for (const id of Object.keys(controls)) {
      if (id in this.formula.params || this.formula.speedControls.includes(id)) continue;
      const target = resolveControl(controls[id], level, 0);
      const cur = this.values[id] ?? target;
      this.values[id] = cur + (target - cur) * k;
    }
  }

  advance(dt: number) {
    this.clock += dt * this.rate;
  }

  /** Evaluate every particle into raw world-unit targets and colours. */
  evaluateRaw(count: number, time: number, outPos: Float32Array, outCol: Float32Array) {
    const w = this.writer;
    const body = this.formula.body;
    for (let i = 0; i < count; i++) {
      body(i, count, w.target, w.color, time, this.addControl, noop, noop, THREE_STUB);
      const j = i * 3;
      outPos[j] = w.x;
      outPos[j + 1] = w.y;
      outPos[j + 2] = w.z;
      outCol[j] = w.r;
      outCol[j + 1] = w.g;
      outCol[j + 2] = w.b;
    }
  }

  /** Evaluate at the current clock, normalised so the idle shape is one unit tall and y-centred. */
  evaluate(count: number, outPos: Float32Array, outCol: Float32Array) {
    this.evaluateRaw(count, this.clock, outPos, outCol);
    const inv = this.fitInvH;
    const cy = this.fitCy;
    for (let j = 0; j < count * 3; j += 3) {
      const x = outPos[j]!;
      const y = outPos[j + 1]!;
      const z = outPos[j + 2]!;
      outPos[j] = Number.isFinite(x) ? x * inv : 0;
      outPos[j + 1] = Number.isFinite(y) ? (y - cy) * inv : 0;
      outPos[j + 2] = Number.isFinite(z) ? z * inv : 0;
    }
  }

  /** Sample the idle shape to fit any formula's world units to `placement.height`. */
  fit(count: number, scratchPos: Float32Array, scratchCol: Float32Array) {
    let minY = Infinity;
    let maxY = -Infinity;
    for (const t of FIT_SAMPLE_TIMES) {
      this.evaluateRaw(count, t, scratchPos, scratchCol);
      for (let j = 1; j < count * 3; j += 3) {
        const y = scratchPos[j]!;
        if (!Number.isFinite(y)) continue;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
    const h = maxY - minY;
    this.fitCy = Number.isFinite(h) && h > 1e-6 ? (minY + maxY) / 2 : 0;
    this.fitInvH = Number.isFinite(h) && h > 1e-6 ? 1 / h : 1;
  }
}

export type SwarmUniforms = {
  center: [number, number];
  height: number;
  dim: number;
  brightness: number;
  tint: [number, number, number];
  tintMix: number;
};

const FALLBACK_SPEC: OrbSpec = {
  formula: "cortex-dinamico",
  placement: { center: [0.5, 0.5], height: 0.6 },
  dim: 1,
  states: {},
};

/**
 * Pure particle-swarm simulation: formula runner, section blend (stagger + bulge),
 * per-particle easing, placement springs, state controls and the landing gather.
 */
export class SwarmSim {
  readonly count: number;
  readonly positions: Float32Array;
  readonly colors: Float32Array;
  readonly uniforms: SwarmUniforms = {
    center: [0.5, 0.5],
    height: 0.6,
    dim: 1,
    brightness: 1,
    tint: [1, 0.69, 0.125],
    tintMix: 0,
  };

  private readonly runtimes = new Map<string, FormulaRuntime>();
  private specs: Record<string, OrbSpec> = {};
  private from = "";
  private to = "";
  private blend = 0;
  private mode: PresenceMode = "idle";
  private levelTarget = 0;
  private level = 0;
  private gather = 1;
  private elapsed = 0;
  reducedMotion = false;
  /** Evaluate formulas every Nth step (2 = 30 Hz sim under a 60 Hz render). */
  simEvery = 1;
  private stepIndex = 0;
  private primed = false;
  lastSimMs = 0;

  private readonly tA: Float32Array;
  private readonly cA: Float32Array;
  private readonly tB: Float32Array;
  private readonly cB: Float32Array;
  private readonly targets: Float32Array;
  readonly scatter: Float32Array;
  /** Ease factor for this frame. The GPU sim uses the same value. */
  easeK = 1;

  private readonly springs: {
    cx: SpringState;
    cy: SpringState;
    h: SpringState;
    dim: SpringState;
  };
  private brightnessBase = 1;
  private tintMixBase = 0;

  constructor(count = PARTICLE_COUNT, formulas: Record<string, OrbFormula> = FORMULAS) {
    this.count = count;
    const n = count * 3;
    this.positions = new Float32Array(n);
    this.colors = new Float32Array(n);
    this.tA = new Float32Array(n);
    this.cA = new Float32Array(n);
    this.tB = new Float32Array(n);
    this.cB = new Float32Array(n);
    this.targets = new Float32Array(n);
    this.scatter = makeScatter(count);
    this.positions.set(this.scatter);
    for (const formula of Object.values(formulas)) {
      const rt = new FormulaRuntime(formula);
      rt.fit(count, this.tA, this.cA);
      this.runtimes.set(formula.id, rt);
    }
    this.springs = {
      cx: createSpring(0.5),
      cy: createSpring(0.5),
      h: createSpring(0.6),
      dim: createSpring(1),
    };
  }

  runtime(id: string): FormulaRuntime | undefined {
    return this.runtimes.get(id);
  }

  setSpecs(specs: Record<string, OrbSpec>) {
    this.specs = specs;
    const ids = Object.keys(specs);
    if (!this.from && ids[0]) {
      this.from = ids[0];
      this.to = ids[0];
      this.snapPlacement();
    }
  }

  setOrb(from: string, to: string, blend: number) {
    const firstTime = !this.from;
    this.from = from;
    this.to = to;
    this.blend = clamp01(blend);
    if (firstTime) this.snapPlacement();
  }

  setMode(mode: PresenceMode) {
    this.mode = mode;
  }

  setLevel(value: number) {
    this.levelTarget = clamp01(value);
  }

  setGather(progress: number) {
    this.gather = clamp01(progress);
  }

  getBlend() {
    return { from: this.from, to: this.to, blend: this.blend };
  }

  private spec(id: string): OrbSpec {
    return this.specs[id] ?? FALLBACK_SPEC;
  }

  private stateFor(spec: OrbSpec): OrbStateSpec | undefined {
    return spec.states[this.mode] ?? spec.states.idle;
  }

  private placementTarget() {
    const a = this.spec(this.from);
    const b = this.spec(this.to);
    const s = smoothstep(this.blend);
    let cx = a.placement.center[0] + (b.placement.center[0] - a.placement.center[0]) * s;
    let cy = a.placement.center[1] + (b.placement.center[1] - a.placement.center[1]) * s;
    let h = a.placement.height + (b.placement.height - a.placement.height) * s;
    let dim = a.dim + (b.dim - a.dim) * s;
    if (this.mode === "hitl") {
      cx = 0.5;
      cy = 0.5;
      h = Math.max(h, HITL_MIN_HEIGHT);
      dim = 1;
    }
    return { cx, cy, h, dim };
  }

  private snapPlacement() {
    const p = this.placementTarget();
    setSpringTarget(this.springs.cx, p.cx, true);
    setSpringTarget(this.springs.cy, p.cy, true);
    setSpringTarget(this.springs.h, p.h, true);
    setSpringTarget(this.springs.dim, p.dim, true);
  }

  /** True when placement is at rest and the blend sits on a section. */
  settled(): boolean {
    const onSection = this.blend <= BLEND_EPS || this.blend >= 1 - BLEND_EPS;
    return onSection && this.gather >= 1 && Object.values(this.springs).every(springAtRest);
  }

  /** Clocks, controls, and placement. Does not move particles. */
  stepMotion(dt: number) {
    const snap = this.reducedMotion;
    this.elapsed += dt;
    const lk = snap ? 1 : 1 - Math.exp(-dt / LEVEL_TAU_S);
    this.level += (this.levelTarget - this.level) * lk;

    const specA = this.spec(this.from);
    const specB = this.spec(this.to);
    const rtA = this.runtimes.get(specA.formula);
    const rtB = this.runtimes.get(specB.formula);
    const s = smoothstep(this.blend);
    for (const rt of this.runtimes.values()) {
      const spec = rt === rtB && s >= 0.5 ? specB : rt === rtA ? specA : rt === rtB ? specB : null;
      rt.easeToward(spec ? this.stateFor(spec) : undefined, this.level, dt, snap);
      rt.advance(dt);
    }

    const p = this.placementTarget();
    setSpringTarget(this.springs.cx, p.cx, snap);
    setSpringTarget(this.springs.cy, p.cy, snap);
    setSpringTarget(this.springs.h, p.h, snap);
    setSpringTarget(this.springs.dim, p.dim, snap);
    if (!snap) {
      for (const sp of Object.values(this.springs)) stepSpring(sp, dt, PLACEMENT_SPRING);
    }

    const stA = this.stateFor(specA);
    const stB = this.stateFor(specB);
    const brightA = resolveControl(stA?.brightness, this.level, 1);
    const brightB = resolveControl(stB?.brightness, this.level, 1);
    const mixA = stA?.tintMix ?? 0;
    const mixB = stB?.tintMix ?? 0;
    const ck = snap ? 1 : 1 - Math.exp(-dt / CONTROL_TAU_S);
    this.brightnessBase += (brightA + (brightB - brightA) * s - this.brightnessBase) * ck;
    this.tintMixBase += (mixA + (mixB - mixA) * s - this.tintMixBase) * ck;
    const pulseHz = (s < 0.5 ? stA?.pulseHz : stB?.pulseHz) ?? 0;
    const pulse = pulseHz && !snap ? 1 + PULSE_AMP * Math.sin(2 * Math.PI * pulseHz * this.elapsed) : 1;
    const tint = (s < 0.5 ? stA?.tint : stB?.tint) ?? this.uniforms.tint;

    this.uniforms.center = [this.springs.cx.x, this.springs.cy.x];
    this.uniforms.height = this.springs.h.x;
    this.uniforms.dim = this.springs.dim.x;
    this.uniforms.brightness = this.brightnessBase * pulse;
    this.uniforms.tint = tint;
    this.uniforms.tintMix = this.tintMixBase;
    this.easeK = snap ? 1 : 1 - Math.pow(0.9, dt * 60);
  }

  /** CPU particle update. The live desk skips this and runs the same step on the GPU. */
  private integrateParticles() {
    const specA = this.spec(this.from);
    const specB = this.spec(this.to);
    const rtA = this.runtimes.get(specA.formula);
    const rtB = this.runtimes.get(specB.formula);
    const evaluateNow = !this.primed || this.simEvery <= 1 || this.stepIndex % this.simEvery === 0;
    this.stepIndex += 1;
    if (evaluateNow && rtA && rtB) {
      this.computeTargets(rtA, rtB);
      this.primed = true;
    }
    const k = this.easeK;
    const pos = this.positions;
    const tgt = this.targets;
    for (let j = 0; j < pos.length; j++) {
      pos[j] = pos[j]! + (tgt[j]! - pos[j]!) * k;
    }
  }

  /** Advance one frame on the CPU. `dt` in seconds. */
  step(dt: number) {
    const t0 = typeof performance !== "undefined" ? performance.now() : 0;
    this.stepMotion(dt);
    this.integrateParticles();
    this.lastSimMs = typeof performance !== "undefined" ? performance.now() - t0 : 0;
  }

  /** Uniforms for one GPU step. Call after `stepMotion`. */
  gpuFrame(): GpuFrame {
    return {
      easeK: this.easeK,
      blend: this.blend,
      gather: this.gather,
      reduced: this.reducedMotion,
      a: this.packFormula(this.from),
      b: this.packFormula(this.to),
    };
  }

  private packFormula(sectionId: string): GpuFormulaState {
    const spec = this.spec(sectionId);
    const rt = this.runtimes.get(spec.formula);
    const v = rt?.values ?? {};
    const n = (id: string, fallback: number) => {
      const value = v[id];
      return value === undefined ? fallback : value;
    };
    return {
      slot: spec.formula === "asci-system" ? 1 : spec.formula === "chat-gpt" ? 2 : 0,
      clock: rt?.clock ?? 0,
      fitCy: rt?.fitCy ?? 0,
      fitInvH: rt?.fitInvH ?? 1,
      radiusOuter: n("radiusOuter", 37.2),
      radiusInner: n("radiusInner", 18.8),
      neuroActivity: n("neuroActivity", 0),
      chaosFactor: n("chaosFactor", 0),
      pulseSpeed: n("pulseSpeed", 3.4),
      scale: n("scale", 45),
      flow: n("flow", 0.7),
      chaos: n("chaos", 0.65),
      twist: n("twist", 1.4),
    };
  }

  private computeTargets(rtA: FormulaRuntime, rtB: FormulaRuntime) {
    const count = this.count;
    const blend = this.blend;
    const tgt = this.targets;
    const col = this.colors;
    const single = rtA === rtB || blend <= BLEND_EPS || blend >= 1 - BLEND_EPS;
    if (single) {
      const rt = blend >= 1 - BLEND_EPS ? rtB : rtA;
      rt.evaluate(count, tgt, col);
    } else {
      rtA.evaluate(count, this.tA, this.cA);
      rtB.evaluate(count, this.tB, this.cB);
      const plain = this.reducedMotion;
      for (let i = 0; i < count; i++) {
        const u = i / count;
        const b = plain ? smoothstep(blend) : smoothstep((blend - STAGGER * u) / (1 - STAGGER));
        const bulge = plain ? 1 : 1 + BULGE * Math.sin(Math.PI * b);
        const j = i * 3;
        for (let c = 0; c < 3; c++) {
          const a = this.tA[j + c]!;
          tgt[j + c] = (a + (this.tB[j + c]! - a) * b) * bulge;
          const ca = this.cA[j + c]!;
          col[j + c] = ca + (this.cB[j + c]! - ca) * b;
        }
      }
    }
    if (this.gather < 1) {
      const g = this.gather;
      const sc = this.scatter;
      for (let j = 0; j < tgt.length; j++) tgt[j] = sc[j]! + (tgt[j]! - sc[j]!) * g;
    }
  }
}
