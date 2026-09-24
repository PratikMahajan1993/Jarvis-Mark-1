"use client";

import { useEffect, useState } from "react";
import { isJarvisPerfMode, readPerfSnapshot, type PerfSnapshot } from "@/lib/pane/perf";

function formatHistogram(h: PerfSnapshot["rafHistogram"]) {
  return RAF_LABELS.map((label) => `${label}:${h[label] ?? 0}`).join(" · ");
}

const RAF_LABELS = ["0-8", "8-16", "16-20", "20-33", "33+"];

export function PerfOverlay() {
  const [snap, setSnap] = useState<PerfSnapshot | null>(null);

  useEffect(() => {
    if (!isJarvisPerfMode()) return;

    let frame = 0;
    const tick = () => {
      setSnap(readPerfSnapshot());
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  if (!isJarvisPerfMode() || !snap) return null;

  const longOver50 = snap.longTasks.filter((t) => t.duration > 50).length;

  return (
    <div
      className="pointer-events-none fixed bottom-16 right-4 z-[200] w-max max-w-[min(480px,calc(100vw-2rem))] rounded-lg border border-[color:var(--accent)]/35 bg-black/85 px-4 py-2.5 font-mono text-[10px] leading-relaxed text-[color:var(--accent)] shadow-lg backdrop-blur-sm"
      aria-live="polite"
      data-testid="jarvis-perf-overlay"
    >
      <p className="mb-1 whitespace-nowrap uppercase tracking-[0.14em] text-[color:var(--muted)]">
        Perf (?perf=1)
      </p>
      <p className="whitespace-nowrap">
        rAF p95: <span className="tabular-nums text-white">{snap.rafP95Ms.toFixed(1)}</span> ms
      </p>
      <p className="whitespace-normal break-words text-[color:var(--muted)]">
        {formatHistogram(snap.rafHistogram)}
      </p>
      <p className="whitespace-nowrap">
        long tasks:{" "}
        <span className="tabular-nums text-white">{snap.longTasks.length}</span>
        {longOver50 > 0 ? (
          <span className="text-amber-300/90"> ({longOver50} &gt;50ms)</span>
        ) : null}
      </p>
      <p className="whitespace-nowrap">
        WebGL contexts: <span className="tabular-nums text-white">{snap.webglContextCount}</span>
      </p>
      <p className="whitespace-nowrap">
        OrchestratorShell commits:{" "}
        <span className="tabular-nums text-white">{snap.orchestratorShellCommits}</span>
      </p>
    </div>
  );
}
