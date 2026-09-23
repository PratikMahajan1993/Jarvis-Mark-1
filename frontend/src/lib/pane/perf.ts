"use client";

/** Dev-only HUD performance instrumentation (?perf=1). */

export type RafHistogram = Record<string, number>;

export type LongTaskEntry = {
  duration: number;
  startTime: number;
  name?: string;
};

export type PerfSnapshot = {
  rafHistogram: RafHistogram;
  rafP95Ms: number;
  longTasks: LongTaskEntry[];
  /** Live WebGL contexts (create +, webglcontextlost / worker dispose −). */
  webglContextCount: number;
  orchestratorShellCommits: number;
  switchCount?: number;
};

export type JarvisPerfGlobal = {
  snapshot: () => PerfSnapshot;
  resetCounters: () => void;
  noteShellCommit: () => void;
};

declare global {
  interface Window {
    __JARVIS_PERF__?: JarvisPerfGlobal;
  }
}

const RAF_BUCKETS: { label: string; max: number }[] = [
  { label: "0-8", max: 8 },
  { label: "8-16", max: 16 },
  { label: "16-20", max: 20 },
  { label: "20-33", max: 33 },
  { label: "33+", max: Infinity },
];

let orchestratorShellCommits = 0;
/** Live count — not cumulative creations. */
let webglContextCount = 0;
const liveWebglCanvases = new WeakSet<object>();
/** Handles that have already credited a worker OffscreenCanvas context. */
const workerCredits = new WeakSet<object>();

const longTasks: LongTaskEntry[] = [];
const rafDeltas: number[] = [];
const rafHistogram: RafHistogram = Object.fromEntries(RAF_BUCKETS.map((b) => [b.label, 0]));

let longTaskObserver: PerformanceObserver | null = null;
let rafHandle = 0;
let lastRafTs = 0;
let webglHookInstalled = false;
let started = false;

export function isJarvisPerfMode(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("perf") === "1";
}

function bucketRafDelta(ms: number) {
  for (const b of RAF_BUCKETS) {
    if (ms <= b.max) {
      rafHistogram[b.label] = (rafHistogram[b.label] ?? 0) + 1;
      return;
    }
  }
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[Math.max(0, idx)] ?? 0;
}

function isWebGLContextId(contextId: string): boolean {
  return contextId === "webgl" || contextId === "webgl2" || contextId === "experimental-webgl";
}

function trackLiveContext(canvas: object) {
  if (liveWebglCanvases.has(canvas)) return;
  liveWebglCanvases.add(canvas);
  webglContextCount += 1;

  const target = canvas as EventTarget;
  if (typeof target.addEventListener !== "function") return;

  const onLost = () => {
    target.removeEventListener("webglcontextlost", onLost);
    if (!liveWebglCanvases.has(canvas)) return;
    liveWebglCanvases.delete(canvas);
    webglContextCount = Math.max(0, webglContextCount - 1);
  };
  target.addEventListener("webglcontextlost", onLost);
}

function patchGetContext(proto: { getContext: (contextId: string, options?: unknown) => unknown }) {
  const original = proto.getContext;
  proto.getContext = function getContextPatched(
    this: object,
    contextId: string,
    options?: unknown,
  ) {
    const ctx = original.call(this, contextId as never, options as never);
    if (ctx && isWebGLContextId(contextId)) {
      trackLiveContext(this);
    }
    return ctx;
  };
}

function installWebGLContextCounter() {
  if (webglHookInstalled) return;
  webglHookInstalled = true;

  if (typeof HTMLCanvasElement !== "undefined") {
    patchGetContext(HTMLCanvasElement.prototype as never);
  }
  // Main-thread OffscreenCanvas only. Worker-realm getContext is credited via
  // noteWorkerWebGLContext (separate JS realm — prototype hooks do not apply).
  if (typeof OffscreenCanvas !== "undefined") {
    patchGetContext(OffscreenCanvas.prototype as never);
  }
}

/**
 * Credit / release a WebGL context that lives inside a substrate worker.
 * `handle` is a stable object (the SubstrateHandle) so Strict Mode remounts
 * credit and release independently without double-counting.
 */
export function noteWorkerWebGLContext(handle: object, live: boolean) {
  if (typeof window === "undefined" || !isJarvisPerfMode()) return;
  ensureJarvisPerf();

  if (live) {
    if (workerCredits.has(handle)) return;
    workerCredits.add(handle);
    webglContextCount += 1;
    return;
  }

  if (!workerCredits.has(handle)) return;
  workerCredits.delete(handle);
  webglContextCount = Math.max(0, webglContextCount - 1);
}

function startLongTaskObserver() {
  if (longTaskObserver || typeof PerformanceObserver === "undefined") return;
  try {
    longTaskObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        longTasks.push({
          duration: entry.duration,
          startTime: entry.startTime,
          name: entry.name,
        });
      }
    });
    longTaskObserver.observe({ type: "longtask", buffered: true });
  } catch {
    /* longtask unsupported */
  }
}

function rafLoop(ts: number) {
  if (lastRafTs > 0) {
    const delta = ts - lastRafTs;
    rafDeltas.push(delta);
    bucketRafDelta(delta);
  }
  lastRafTs = ts;
  rafHandle = requestAnimationFrame(rafLoop);
}

function startRafHistogram() {
  if (rafHandle) return;
  lastRafTs = 0;
  rafHandle = requestAnimationFrame(rafLoop);
}

function resetCounters() {
  orchestratorShellCommits = 0;
  longTasks.length = 0;
  rafDeltas.length = 0;
  for (const b of RAF_BUCKETS) {
    rafHistogram[b.label] = 0;
  }
  lastRafTs = 0;
}

function buildSnapshot(switchCount?: number): PerfSnapshot {
  return {
    rafHistogram: { ...rafHistogram },
    rafP95Ms: percentile(rafDeltas, 95),
    longTasks: longTasks.map((t) => ({ ...t })),
    webglContextCount,
    orchestratorShellCommits,
    ...(switchCount !== undefined ? { switchCount } : {}),
  };
}

function publishGlobal() {
  window.__JARVIS_PERF__ = {
    snapshot: () => buildSnapshot(),
    resetCounters,
    noteShellCommit: () => {
      orchestratorShellCommits += 1;
    },
  };
}

/** Install observers and expose `window.__JARVIS_PERF__` when ?perf=1. */
export function ensureJarvisPerf(): boolean {
  if (typeof window === "undefined" || !isJarvisPerfMode()) return false;
  if (!started) {
    started = true;
    installWebGLContextCounter();
    startLongTaskObserver();
    startRafHistogram();
    publishGlobal();
  }
  return true;
}

export function recordOrchestratorShellCommit() {
  if (!isJarvisPerfMode()) return;
  orchestratorShellCommits += 1;
}

export function readPerfSnapshot(): PerfSnapshot | null {
  if (typeof window === "undefined") return null;
  return window.__JARVIS_PERF__?.snapshot() ?? null;
}

if (typeof window !== "undefined") {
  ensureJarvisPerf();
}
