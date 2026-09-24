"use client";

import gsap from "gsap";
import { EYE_INTERNAL_SCALE } from "@/substrate/presence.frag";
import type { SubstrateIn } from "@/substrate/protocol";
import { tiltTo } from "./conductor";

const GLANCE_MS = 600;
const TILT_DEG = 0.3;
const IDLE_MS_DEFAULT = 4 * 60 * 1000;
const IDLE_MS_DEV = 2000;
const PANE_BRIGHT_IDLE = 0.7;
const PANE_BRIGHT_WAKE = 1;

function substratePost(msg: SubstrateIn) {
  window.__JARVIS_SUBSTRATE__?.post?.(msg);
}

export function idleWaitMs(): number {
  if (typeof window === "undefined") return IDLE_MS_DEFAULT;
  try {
    if (new URLSearchParams(window.location.search).get("idle") === "1") return IDLE_MS_DEV;
  } catch {
    /* ignore */
  }
  return IDLE_MS_DEFAULT;
}

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function tasksRailGlanceNorm(root: HTMLElement): { x: number; y: number } | null {
  const host = root.querySelector<HTMLElement>("[data-substrate]");
  const tasks = root.querySelector<HTMLElement>('[data-panel="tasks"]');
  if (!host || !tasks) return null;
  const h = host.getBoundingClientRect();
  const t = tasks.getBoundingClientRect();
  if (h.width < 1 || h.height < 1) return null;
  const cx = (t.left + t.width * 0.5 - h.left) / h.width;
  const cy = (t.top + t.height * 0.35 - h.top) / h.height;
  return {
    x: cx * 2 - 1,
    y: -((cy * 2 - 1)),
  };
}

let glanceQueue: string[] = [];
let glanceActive = false;
let glanceReturnTimer: ReturnType<typeof setTimeout> | null = null;

function drainGlanceQueue(root: HTMLElement) {
  if (glanceActive || glanceQueue.length === 0) return;
  const nextId = glanceQueue.shift();
  if (!nextId) return;

  const norm = tasksRailGlanceNorm(root);
  if (!norm) {
    drainGlanceQueue(root);
    return;
  }

  glanceActive = true;
  substratePost({ type: "glance", x: norm.x, y: norm.y, ms: GLANCE_MS });

  const dock = root.querySelector<HTMLElement>("[data-dock]");
  const reduced = prefersReducedMotion();
  let tilt: ReturnType<typeof tiltTo> | null = null;
  if (dock && !reduced) {
    tilt = tiltTo(dock);
    tilt(TILT_DEG);
  }

  if (glanceReturnTimer) clearTimeout(glanceReturnTimer);
  glanceReturnTimer = setTimeout(() => {
    glanceReturnTimer = null;
    if (tilt) tilt(0);
    glanceActive = false;
    drainGlanceQueue(root);
  }, GLANCE_MS);
}

/** One attention pull per finding id; never stacked. */
export function enqueueFindingGlance(root: HTMLElement, findingId: string): void {
  if (!findingId || glanceQueue.includes(findingId)) return;
  glanceQueue.push(findingId);
  drainGlanceQueue(root);
}

declare global {
  interface Window {
    __JARVIS_AMBIENT__?: { enqueueFindingGlance: (id: string) => void };
  }
}

if (typeof window !== "undefined") {
  window.__JARVIS_AMBIENT__ = {
    enqueueFindingGlance: (id: string) => {
      const root = document.querySelector<HTMLElement>("[data-pane-root]");
      if (root) enqueueFindingGlance(root, id);
    },
  };
}

export function setPaneIdleDim(root: HTMLElement, dim: boolean): void {
  root.dataset.idleDim = dim ? "1" : "0";
  if (prefersReducedMotion()) {
    gsap.set(root, { "--pane-brightness": dim ? PANE_BRIGHT_IDLE : PANE_BRIGHT_WAKE });
  } else {
    gsap.to(root, {
      "--pane-brightness": dim ? PANE_BRIGHT_IDLE : PANE_BRIGHT_WAKE,
      duration: dim ? 0.7 : 0.28,
      ease: dim ? "power2.inOut" : "power3.out",
    });
  }
  if (dim) {
    substratePost({ type: "quality", scale: EYE_INTERNAL_SCALE, fps: 30 });
  } else {
    substratePost({ type: "quality", scale: EYE_INTERNAL_SCALE, fps: 60 });
  }
}
