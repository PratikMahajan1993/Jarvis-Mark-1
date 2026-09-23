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
let webglContextCount = 0;
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

function installWebGLContextCounter() {
  if (webglHookInstalled || typeof HTMLCanvasElement === "undefined") return;
  webglHookInstalled = true;

  const proto = HTMLCanvasElement.prototype;
  const original = proto.getContext;

  const patched = function getContextPatched(
    this: HTMLCanvasElement,
    contextId: string,
    options?: unknown,
  ) {
    const ctx = original.call(this, contextId as never, options as never);
    if (
      ctx &&
      (contextId === "webgl" || contextId === "webgl2" || contextId === "experimental-webgl")
    ) {
      webglContextCount += 1;
    }
    return ctx;
  };
  proto.getContext = patched as typeof proto.getContext;
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
