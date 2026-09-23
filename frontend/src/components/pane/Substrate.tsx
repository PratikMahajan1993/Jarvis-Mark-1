"use client";

import { useEffect, useRef } from "react";
import { createSubstrate, type SubstrateHandle } from "@/substrate/createSubstrate";
import { lensFor, type Lens, type SubstrateIn, type SubstrateOut } from "@/substrate/protocol";
import type { HudWorkspace } from "@/components/orchestrator/hudWorkspace";

export type JarvisSubstrateGlobal = {
  ready: Extract<SubstrateOut, { type: "ready" }> | null;
  stats: Extract<SubstrateOut, { type: "stats" }> | null;
  settled: Extract<SubstrateOut, { type: "settled" }> | null;
  contextLost: boolean;
  latest: SubstrateOut | null;
  mode: "worker" | "inline";
  /** Forward SubstrateIn (e.g. quality override) from console / headless. */
  post?: (msg: SubstrateIn) => void;
};

declare global {
  interface Window {
    __JARVIS_SUBSTRATE__?: JarvisSubstrateGlobal;
  }
}

function publishOut(msg: SubstrateOut, mode: "worker" | "inline") {
  if (typeof window === "undefined") return;
  const prev = window.__JARVIS_SUBSTRATE__;
  const next: JarvisSubstrateGlobal = {
    ready: prev?.ready ?? null,
    stats: prev?.stats ?? null,
    settled: prev?.settled ?? null,
    contextLost: prev?.contextLost ?? false,
    latest: msg,
    mode,
    post: prev?.post,
  };
  if (msg.type === "ready") {
    next.ready = msg;
    next.contextLost = false;
  }
  if (msg.type === "stats") next.stats = msg;
  if (msg.type === "settled") next.settled = msg;
  if (msg.type === "contextLost") next.contextLost = true;
  window.__JARVIS_SUBSTRATE__ = next;
}

function isInlineForced(): boolean {
  try {
    return new URLSearchParams(window.location.search).get("substrate") === "inline";
  } catch {
    return false;
  }
}

function qualityFromQuery(): { scale: number; fps: 30 | 60 } | null {
  try {
    const raw = new URLSearchParams(window.location.search).get("quality");
    if (raw == null || raw === "") return null;
    const scale = Number(raw);
    if (!Number.isFinite(scale) || scale <= 0) return null;
    const fps: 30 | 60 = scale < 0.55 ? 30 : 60;
    return { scale, fps };
  } catch {
    return null;
  }
}

/**
 * Single full-pane canvas → one WebGL context (worker OffscreenCanvas or inline shim).
 * Forwards ?quality= and posts {type:"quality"} for adaptive override / recovery.
 */
export function Substrate({ workspace }: { workspace: HudWorkspace }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<SubstrateHandle | null>(null);
  const workspaceRef = useRef(workspace);
  workspaceRef.current = workspace;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const canvas = document.createElement("canvas");
    canvas.className = "absolute inset-0 h-full w-full";
    canvas.setAttribute("aria-hidden", "true");
    host.appendChild(canvas);

    const mode: "worker" | "inline" =
      isInlineForced() ||
      typeof OffscreenCanvas === "undefined" ||
      typeof canvas.transferControlToOffscreen !== "function"
        ? "inline"
        : "worker";

    window.__JARVIS_SUBSTRATE__ = {
      ready: null,
      stats: null,
      settled: null,
      contextLost: false,
      latest: null,
      mode,
    };

    const handle = createSubstrate(canvas, (msg) => {
      publishOut(msg, mode);
      if (msg.type === "ready") {
        const q = qualityFromQuery();
        if (q) handle.post({ type: "quality", scale: q.scale, fps: q.fps });
      }
    });
    handleRef.current = handle;
    // Dev/headless: post {type:"quality"} via window.__JARVIS_SUBSTRATE__.post(...)
    window.__JARVIS_SUBSTRATE__.post = (msg) => handle.post(msg);

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const rect = host.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    handle.post({
      type: "init",
      canvas,
      width: Math.max(1, rect.width || host.clientWidth || 1),
      height: Math.max(1, rect.height || host.clientHeight || 1),
      dpr,
      lens: lensFor(workspaceRef.current),
      reducedMotion,
    });

    let resizeRaf = 0;
    const ro = new ResizeObserver(() => {
      if (resizeRaf) cancelAnimationFrame(resizeRaf);
      resizeRaf = requestAnimationFrame(() => {
        const r = host.getBoundingClientRect();
        handle.post({
          type: "resize",
          width: Math.max(1, r.width || 1),
          height: Math.max(1, r.height || 1),
          dpr: Math.min(window.devicePixelRatio || 1, 2),
        });
      });
    });
    ro.observe(host);

    let pointerRaf = 0;
    let pending: { x: number; y: number } | null = null;
    const onPointer = (e: PointerEvent) => {
      const r = host.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return;
      pending = {
        x: ((e.clientX - r.left) / r.width) * 2 - 1,
        y: -(((e.clientY - r.top) / r.height) * 2 - 1),
      };
      if (pointerRaf) return;
      pointerRaf = requestAnimationFrame(() => {
        pointerRaf = 0;
        if (!pending) return;
        handle.post({ type: "pointer", x: pending.x, y: pending.y });
        pending = null;
      });
    };
    window.addEventListener("pointermove", onPointer, { passive: true });

    const onVisibility = () => {
      handle.post({ type: "visibility", hidden: document.hidden });
    };
    document.addEventListener("visibilitychange", onVisibility);

    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onMq = () => {
      handle.post({ type: "reducedMotion", on: mq.matches });
    };
    mq.addEventListener("change", onMq);

    return () => {
      ro.disconnect();
      if (resizeRaf) cancelAnimationFrame(resizeRaf);
      if (pointerRaf) cancelAnimationFrame(pointerRaf);
      window.removeEventListener("pointermove", onPointer);
      document.removeEventListener("visibilitychange", onVisibility);
      mq.removeEventListener("change", onMq);
      handle.dispose();
      handleRef.current = null;
      if (canvas.parentNode === host) host.removeChild(canvas);
    };
  }, []);

  useEffect(() => {
    const handle = handleRef.current;
    if (!handle) return;
    handle.post({
      type: "lens",
      lens: lensFor(workspace),
      t0: performance.timeOrigin + performance.now(),
    });
  }, [workspace]);

  return (
    <div
      ref={hostRef}
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden"
      aria-hidden
      data-substrate
    />
  );
}

export type { Lens };
