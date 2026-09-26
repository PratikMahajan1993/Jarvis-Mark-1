"use client";

function relativeLabel(updatedAt?: string | null): string {
  if (!updatedAt) return "No timestamp";
  const then = Date.parse(updatedAt);
  if (Number.isNaN(then)) return "Updated time unknown";
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 1) return "Updated just now";
  if (mins < 60) return `Updated ${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `Updated ${hours} hr ago`;
  return `Updated ${Math.round(hours / 24)} days ago`;
}

export function FreshnessBadge({
  updatedAt,
  stale = false,
}: {
  updatedAt?: string | null;
  stale?: boolean;
}) {
  const label = stale ? `Stale · ${relativeLabel(updatedAt)}` : relativeLabel(updatedAt);
  let dot = "bg-[color:oklch(78%_0.16_155)]";
  if (!updatedAt) dot = "bg-[color:oklch(82%_0.14_95)]";
  if (stale) dot = "bg-[color:oklch(70%_0.18_25)]";
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[10px] text-[color:var(--muted)]" title={label}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden />
      {label}
    </span>
  );
}
