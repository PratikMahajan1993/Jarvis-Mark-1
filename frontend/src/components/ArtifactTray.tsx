import { api } from "@/lib/api";
import type { Artifact } from "@/lib/types";

export function ArtifactTray({ items }: { items: Artifact[] }) {
  if (!items.length) return null;
  return (
    <div className="flex justify-center gap-3 overflow-x-auto">
      {items.slice(0, 4).map((item) => (
        <a
          key={item.id}
          href={api.downloadUrl(item.id)}
          className="rounded-sm border border-white/10 px-3 py-1 font-mono text-xs text-white/40 transition-colors hover:border-cyan/40 hover:text-cyan"
        >
          {item.name}
        </a>
      ))}
    </div>
  );
}
