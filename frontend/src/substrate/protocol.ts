/** Substrate worker protocol v2 — particle swarm. See docs/overhaul/PLATFORM_DECISIONS.md P6. */

export type PresenceMode = "idle" | "listening" | "thinking" | "speaking" | "hitl";

/** Canvas the engine draws into — OffscreenCanvas in the worker, HTMLCanvasElement in the inline shim. */
export type SubstrateCanvas = OffscreenCanvas | HTMLCanvasElement;

/** A control value; `level` adds `level × speakingAmplitude` (0..1). */
export type ControlValue = number | { base: number; level: number };

export type OrbStateSpec = {
  /** Named formula controls. Speed controls become clock rates automatically. */
  controls?: Record<string, ControlValue>;
  /** Generic clock rate for formulas without speed controls. */
  rate?: ControlValue;
  brightness?: ControlValue;
  /** RGB 0..1 tint, mixed by `tintMix`. */
  tint?: [number, number, number];
  tintMix?: number;
  /** Brightness pulse frequency (Hz), ±15%. */
  pulseHz?: number;
};

export type OrbPlacement = {
  /** Screen centre, 0..1 from the top-left. */
  center: [number, number];
  /** Fitted shape height as a fraction of the viewport height. */
  height: number;
};

export type OrbSpec = {
  formula: string;
  placement: OrbPlacement;
  dim: number;
  states: Partial<Record<PresenceMode, OrbStateSpec>>;
};

export type SubstrateIn =
  | {
      type: "init";
      canvas: SubstrateCanvas;
      width: number;
      height: number;
      dpr: number;
      reducedMotion: boolean;
      /** 0 = scattered landing cloud, 1 = fully gathered. */
      gather: number;
    }
  | { type: "resize"; width: number; height: number; dpr: number }
  /** Section id → orb spec. Sent once at boot and whenever the registry changes. */
  | { type: "sections"; specs: Record<string, OrbSpec> }
  /** Scroll-resolved blend between two section ids. Posted at most once per frame. */
  | { type: "orb"; from: string; to: string; blend: number }
  | { type: "mode"; mode: PresenceMode }
  | { type: "level"; value: number }
  | { type: "route"; active: boolean }
  | { type: "gather"; progress: number }
  | { type: "pointer"; x: number; y: number }
  | { type: "visibility"; hidden: boolean }
  | { type: "reducedMotion"; on: boolean }
  | { type: "quality"; scale: number; fps: 30 | 60 };

export type SubstrateOut =
  | { type: "ready"; webgl2: boolean }
  | { type: "settled" }
  | { type: "stats"; fps: number; p95ms: number; scale: number; simMs: number }
  | { type: "contextLost" };
