"use client";

import { useEffect, useRef } from "react";
import { createSubstrate } from "@/substrate/createSubstrate";
import {
  attachSubstrate,
  detachSubstrate,
  lastPosted,
  postSubstrate,
  receiveSubstrate,
} from "./substrateBridge";

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
    return { scale, fps: scale < 0.55 ? 30 : 60 };
  } catch {
    return null;
  }
}

/**
 * L1: the one full-viewport canvas and the one WebGL context (worker
 * OffscreenCanvas, or the inline shim at 30 fps). Mounted once by JarvisRoot.
 */
export function SubstrateCanvas({ active }: { active: boolean }) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const canvas = document.createElement("canvas");
    canvas.className = "absolute inset-0 h-full w-full";
    canvas.setAttribute("aria-hidden", "true");
    host.appendChild(canvas);

    const transport: "worker" | "inline" =
      isInlineForced() ||
      typeof OffscreenCanvas === "undefined" ||
      typeof canvas.transferControlToOffscreen !== "function"
        ? "inline"
        : "worker";

    const handle = createSubstrate(canvas, (msg) => {
      receiveSubstrate(msg);
      if (msg.type === "ready") {
        const q = qualityFromQuery();
        if (q) postSubstrate({ type: "quality", scale: q.scale, fps: q.fps });
      }
    });

    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const width = Math.max(1, window.innerWidth);
    const height = Math.max(1, window.innerHeight);
    handle.post({
      type: "init",
      canvas,
      width,
      height,
      dpr: Math.min(window.devicePixelRatio || 1, 2),
      reducedMotion: mq.matches,
      gather: lastPosted("gather")?.progress ?? 1,
    });
    attachSubstrate(handle, transport);

    let resizeRaf = 0;
    const onResize = () => {
      if (resizeRaf) cancelAnimationFrame(resizeRaf);
      resizeRaf = requestAnimationFrame(() => {
        resizeRaf = 0;
        handle.post({
          type: "resize",
          width: Math.max(1, window.innerWidth),
          height: Math.max(1, window.innerHeight),
          dpr: Math.min(window.devicePixelRatio || 1, 2),
        });
      });
    };
    window.addEventListener("resize", onResize);

    const onVisibility = () => postSubstrate({ type: "visibility", hidden: document.hidden });
    document.addEventListener("visibilitychange", onVisibility);
    const onMq = () => postSubstrate({ type: "reducedMotion", on: mq.matches });
    mq.addEventListener("change", onMq);

    return () => {
      window.removeEventListener("resize", onResize);
      if (resizeRaf) cancelAnimationFrame(resizeRaf);
      document.removeEventListener("visibilitychange", onVisibility);
      mq.removeEventListener("change", onMq);
      detachSubstrate(handle);
      handle.dispose();
      if (canvas.parentNode === host) host.removeChild(canvas);
    };
  }, []);

  useEffect(() => {
    postSubstrate({ type: "route", active });
  }, [active]);

  return (
    <div
      ref={hostRef}
      className="pointer-events-none fixed inset-0 z-substrate overflow-hidden transition-opacity duration-300"
      style={{ opacity: active ? 1 : 0 }}
      aria-hidden
      data-substrate
    />
  );
}
