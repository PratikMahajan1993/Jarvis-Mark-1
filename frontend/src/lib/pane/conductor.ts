import gsap from "gsap";
import { LENS_SUBSTRATE, type SubstrateIn } from "@/substrate/protocol";
import type { Lens } from "@/substrate/protocol";
import { LENS_THEME } from "./lenses";
import { DURATION, EASE } from "./springs";

export type ConductorSubstrate = {
  post(m: SubstrateIn): void;
};

export type ConductorCtx = {
  root: HTMLElement;
  field?: HTMLElement | null;
  vignette?: HTMLElement | null;
  substrate?: ConductorSubstrate;
  tl?: gsap.core.Timeline;
};

let ctx: ConductorCtx | null = null;
let activeTimeline: gsap.core.Timeline | null = null;

const absNow = () => performance.timeOrigin + performance.now();

function substratePost(msg: SubstrateIn) {
  if (ctx?.substrate) {
    ctx.substrate.post(msg);
    return;
  }
  window.__JARVIS_SUBSTRATE__?.post?.(msg);
}

function statusTitleEl(root: HTMLElement): HTMLElement | null {
  return root.querySelector<HTMLElement>(".status-title");
}

export function bindConductor(next: Partial<ConductorCtx>): void {
  if (!ctx && !next.root) return;
  const root = next.root ?? ctx?.root;
  if (!root) return;
  ctx = { ...(ctx ?? { root }), ...next, root };
}

export function snapLensTheme(root: HTMLElement, lens: Lens): void {
  const T = LENS_THEME[lens];
  const sub = LENS_SUBSTRATE[lens];
  gsap.set(root, {
    "--bg": T.bg,
    "--surface": T.surface,
    "--fg": T.fg,
    "--muted": T.muted,
    "--border": T.border,
    "--accent": T.accent,
    "--mat": T.mat,
    "--grid-opacity": T.gridOpacity,
    "--vignette-opacity": T.vignetteOpacity,
    "--substrate-dim": sub.dim,
  });
}

export function playLens(to: Lens): void {
  const root = ctx?.root;
  if (!root) return;

  activeTimeline?.kill();
  gsap.killTweensOf(root);

  // Lens gestures coalesce on the main thread — snap tokens once per target so
  // @property repaints do not run a multi-frame GSAP loop during FLIP.
  snapLensTheme(root, to);
  substratePost({ type: "lens", lens: to, t0: absNow() });

  activeTimeline = null;
  if (ctx) ctx.tl = undefined;
}

export function playOverlay(up: boolean): void {
  const root = ctx?.root;
  if (!root) return;
  gsap.to(root, {
    "--substrate-dim": up ? 0.25 : 1,
    duration: 0.35,
    ease: EASE.gsapOut,
  });
  substratePost({ type: "mode", mode: up ? "hitl" : "idle" });
}

export function playFocus(focusStage: boolean): void {
  const root = ctx?.root;
  if (!root) return;
  const dock = root.querySelector<HTMLElement>("[data-dock]");
  if (!dock) return;
  dock.dataset.focus = focusStage ? "stage" : "normal";
  /* Grid areas swap via CSS [data-focus]; motion layout FLIPs panels — no setTimeout. */
  gsap.fromTo(
    dock,
    { opacity: focusStage ? 0.92 : 0.92 },
    {
      opacity: 1,
      duration: DURATION.chrome,
      ease: EASE.gsapOut,
    },
  );
}

export const tiltTo = (dock: HTMLElement) =>
  gsap.quickTo(dock, "rotationY", { duration: 0.5, ease: "power3.out" });
