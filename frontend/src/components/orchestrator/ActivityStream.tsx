import type { ActivityItem } from "@/lib/orchestrator";

export function ActivityStream({ items }: { items: ActivityItem[] }) {
  return (
    <div className="orch-activity absolute left-12 top-12 z-[2] flex h-[250px] w-80 flex-col gap-3 overflow-hidden font-mono text-xs text-[color:var(--muted)]">
      {items.map((item) => (
        <div key={item.id} className="orch-activity-item flex gap-4">
          <span className="opacity-50">{item.time}</span>
          <span className="font-medium text-[color:var(--fg)]">[{item.agent}]</span>
          <span className="min-w-0 flex-1 truncate">{item.message}</span>
        </div>
      ))}
    </div>
  );
}
