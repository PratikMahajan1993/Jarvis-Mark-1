"use client";

import SpotlightCard from "@/components/react-bits/SpotlightCard";

/** Compact weather chip — sits above the scrollable suggested-tasks stack. */
export function WeatherCard({ line }: { line?: string }) {
  if (!line) return null;
  return (
    <SpotlightCard className="shrink-0 rounded-lg border border-[color:var(--border)] bg-black/40 backdrop-blur-md">
      <div className="px-4 py-3 text-sm text-[color:var(--muted)]">
        <div className="mb-1 font-mono text-[0.65rem] uppercase tracking-[0.12em] text-[color:var(--accent)]">
          Weather
        </div>
        {line}
      </div>
    </SpotlightCard>
  );
}
