import { api } from "@/lib/api";
import type { Artifact } from "@/lib/types";

export function ArtifactTray({ items }: { items: Artifact[] }) {
  if (!items.length) return null;
  return (
    <div className="flex justify-center gap-6 overflow-x-auto">
      {items.slice(0, 4).map((item) => (
        <a key={item.id} href={api.downloadUrl(item.id)} className="text-sm text-white/35 hover:text-cyan">
          {item.name}
        </a>
      ))}
    </div>
  );
}
