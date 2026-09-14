"use client";

import { useEffect, useRef } from "react";
import type { ActivityItem } from "@/lib/orchestrator";

export function ActivityStream({ items }: { items: ActivityItem[] }) {
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const latest = items[0];
  const hasItems = items.length > 0;

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && detailsRef.current?.open) {
        detailsRef.current.open = false;
      }
    }
    function onPointer(event: MouseEvent) {
      const root = detailsRef.current;
      if (!root?.open) return;
      if (!root.contains(event.target as Node)) root.open = false;
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onPointer);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onPointer);
    };
  }, []);

  return (
    <details
      ref={detailsRef}
      className="orch-activity absolute left-12 top-12 z-[2]"
    >
      <summary
        className={[
          "orch-activity-orb group relative flex h-5 w-5 list-none cursor-pointer items-center justify-center rounded-full border border-[color:var(--accent)]/50 bg-[color:var(--accent)]/20 transition marker:content-none [&::-webkit-details-marker]:hidden",
          hasItems ? "orch-activity-orb-live" : "",
          "hover:scale-110 details-open:opacity-40",
        ]
          .filter(Boolean)
          .join(" ")}
        aria-label="Activity"
        title={latest ? `${latest.agent}: ${latest.message}` : "Activity"}
      >
        <span className="orch-activity-orb-core absolute inset-1 rounded-full bg-[color:var(--accent)]" />
        <span className="orch-activity-orb-ring pointer-events-none absolute -inset-2 rounded-full border border-[color:var(--accent)]/35" />
      </summary>

      <div className="orch-activity-panel mt-4 flex max-h-[250px] w-80 flex-col gap-3 overflow-hidden font-mono text-xs text-[color:var(--muted)]">
        {hasItems ? (
          items.map((item) => (
            <div key={item.id} className="orch-activity-item flex gap-4">
              <span className="opacity-50">{item.time}</span>
              <span className="font-medium text-[color:var(--fg)]">[{item.agent}]</span>
              <span className="min-w-0 flex-1 truncate">{item.message}</span>
            </div>
          ))
        ) : (
          <div className="opacity-50">No recent activity.</div>
        )}
      </div>
    </details>
  );
}
