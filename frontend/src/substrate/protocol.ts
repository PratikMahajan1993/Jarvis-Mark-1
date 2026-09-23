/** Substrate worker protocol — Phase 1b (eye + orb + particles + rays). See work/SONNET_UI_VISION.md §2.2. */

export type Lens = "watch" | "converse" | "bench";
export type PresenceMode = "idle" | "listening" | "thinking" | "speaking" | "hitl";

/** Canvas the engine draws into — OffscreenCanvas in the worker, HTMLCanvasElement in the inline shim. */
export type SubstrateCanvas = OffscreenCanvas | HTMLCanvasElement;

export type SubstrateIn =
  | {
      type: "init";
      canvas: SubstrateCanvas;
      width: number;
      height: number;
      dpr: number;
      lens: Lens;
      reducedMotion: boolean;
    }
  | { type: "resize"; width: number; height: number; dpr: number }
  | { type: "lens"; lens: Lens; t0: number }
  | { type: "mode"; mode: PresenceMode }
  | { type: "pointer"; x: number; y: number }
  | { type: "glance"; x: number; y: number; ms: number }
  | { type: "visibility"; hidden: boolean }
  | { type: "reducedMotion"; on: boolean }
  | { type: "quality"; scale: number; fps: 30 | 60 };

export type SubstrateOut =
  | { type: "ready"; webgl2: boolean }
  | { type: "settled"; lens: Lens }
  | { type: "stats"; fps: number; p95ms: number; scale: number }
  | { type: "contextLost" };

export const LENS_SUBSTRATE: Record<
  Lens,
  {
    eye: number;
    orb: number;
    center: [number, number];
    scale: number;
    accent: [number, number, number];
    dim: number;
  }
> = {
  watch: { eye: 1, orb: 0, center: [0.5, 0.5], scale: 1, accent: [1.0, 0.435, 0.216], dim: 1 },
  converse: { eye: 0, orb: 1, center: [0.5, 0.5], scale: 1, accent: [0.49, 1.0, 0.878], dim: 1 },
  bench: {
    eye: 0,
    orb: 1,
    center: [0.045, 0.075],
    scale: 0.07,
    accent: [0.49, 1.0, 0.878],
    dim: 0.35,
  },
};

/** Map HudWorkspace → Lens. Do not invent a fourth workspace. */
export function lensFor(workspace: "casual" | "monitor" | "engineering"): Lens {
  if (workspace === "monitor") return "watch";
  if (workspace === "casual") return "converse";
  return "bench";
}
