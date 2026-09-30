"use client";

import SpotlightCard from "@/components/react-bits/SpotlightCard";
import { api, useFeatureQuery } from "@/sdk";

type SheetLine = {
  id: string;
  display_name: string;
  account_label?: string;
  last_read_at?: string | null;
  stale?: boolean;
  line?: string;
};

type StatusPayload = {
  ok?: boolean;
  today?: string;
  sheets?: SheetLine[];
  conflicts?: Array<Record<string, unknown>>;
};

function shortTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function SheetListenCard() {
  const { data, isLoading, refetch, isFetching } = useFeatureQuery<StatusPayload>(
    ["sheet-listen", "status"],
    () => api.sheetListenStatus(),
    { topics: ["sheet-listen.changed"], interval: 60_000 },
  );

  const sheets = data?.sheets || [];
  if (!isLoading && sheets.length === 0) return null;

  return (
    <SpotlightCard className="shrink-0 rounded-lg border border-[color:var(--border)] bg-black/40 backdrop-blur-md">
      <div className="px-4 py-3 text-sm text-[color:var(--muted)]">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-[color:var(--accent)]">
            Shop logs
          </div>
          <button
            type="button"
            className="font-mono text-[0.6rem] uppercase tracking-[0.1em] text-[color:var(--accent)]/80 hover:text-[color:var(--accent)]"
            onClick={() => {
              void api.sheetListenRefresh().then(() => refetch());
            }}
            disabled={isFetching}
          >
            {isFetching ? "Reading…" : "Refresh"}
          </button>
        </div>
        {isLoading ? (
          <p>Loading listened sheets…</p>
        ) : (
          <ul className="space-y-2">
            {sheets.map((sheet) => (
              <li key={sheet.id} className="border-t border-[color:var(--border)]/60 pt-2 first:border-0 first:pt-0">
                <div className="text-[color:var(--fg)]">
                  {sheet.display_name}
                  {sheet.stale ? (
                    <span className="ml-2 font-mono text-[0.6rem] uppercase tracking-[0.1em] text-amber-300">
                      stale
                    </span>
                  ) : null}
                </div>
                <div className="mt-0.5 font-mono text-[0.65rem] text-[color:var(--muted)]">
                  {(sheet.account_label || "shop") + " · " + shortTime(sheet.last_read_at)}
                </div>
                <div className="mt-1 text-[color:var(--muted)]">{sheet.line || "—"}</div>
              </li>
            ))}
          </ul>
        )}
        {(data?.conflicts || []).length ? (
          <p className="mt-2 font-mono text-[0.65rem] text-amber-200/90">
            Conflicts on {(data?.conflicts || []).length} figure
            {(data?.conflicts || []).length === 1 ? "" : "s"} — both values kept.
          </p>
        ) : null}
      </div>
    </SpotlightCard>
  );
}
