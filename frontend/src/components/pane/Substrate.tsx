"use client";

import { useEffect, useRef } from "react";
import { createSubstrate, type SubstrateHandle } from "@/substrate/createSubstrate";
import { lensFor, type SubstrateOut } from "@/substrate/protocol";
import type { HudWorkspace } from "@/components/orchestrator/hudWorkspace";

export type JarvisSubstrateGlobal = {
  ready: Extract<SubstrateOut, { type: "ready" }> | null;
  stats: Extract<SubstrateOut, { type: "stats" }> | null;
  latest: SubstrateOut | null;
  mode: "worker" | "inline";
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
    latest: msg,
    mode,
  };
  if (msg.type === "ready") next.ready = msg;
  if (msg.type === "stats") next.stats = msg;
  window.__JARVIS_SUBSTRATE__ = next;
}

function isInlineForced(): boolean {
  try {
    return new URLSearchParams(window.location.search).get("substrate") === "inline";
  } catch {
    return false;
  }
}

/**
 * Single full-pane canvas → one WebGL context (worker OffscreenCanvas or inline shim).
 * Lens follows the current HudWorkspace; no paneStore in Phase 1a.
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
      latest: null,
      mode,
    };

    const handle = createSubstrate(canvas, (msg) => publishOut(msg, mode));
    handleRef.current = handle;

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
    // ≤30 Hz via rAF coalesce (one post per frame max).
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
