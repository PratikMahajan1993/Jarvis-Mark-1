"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RecallPayload } from "@/lib/pane/knowledge";
import { FreshnessBadge } from "./FreshnessBadge";

export function KnowledgeSummary({
  sessionId = "default",
  entityId = "",
}: {
  sessionId?: string;
  entityId?: string;
}) {
  const [body, setBody] = useState<RecallPayload | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await api.recallDrawing(sessionId, entityId);
      setBody(next.enabled === false ? null : next);
    } catch {
      setBody(null);
    }
  }, [sessionId, entityId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!body || !body.summary) {
    return (
      <p className="font-mono text-[11px] text-[color:var(--muted)]" data-knowledge-summary>
        No drawing card loaded yet.
      </p>
    );
  }

  const lat = body.latencies_ms;
  const showLatency = process.env.NODE_ENV === "development" && lat;

  return (
    <section className="space-y-2" data-knowledge-summary>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.18em] text-[color:var(--muted)]">
          Drawing recall
        </h3>
        <FreshnessBadge updatedAt={body.updated_at} stale={body.stale} />
      </div>
      <p className="font-display text-sm leading-relaxed text-[color:var(--fg)]">{body.summary}</p>
      {body.confirmed?.length ? (
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">Confirmed facts</p>
          <ul className="mt-1 space-y-0.5">
            {body.confirmed.map((row) => (
              <li key={row.field} className="font-mono text-[11px]">
                {row.label}: {row.value}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {body.gaps?.length ? (
        <p className="font-mono text-[11px] text-[color:oklch(82%_0.12_25)]">Gaps: {body.gaps.join(", ")}</p>
      ) : null}
      {showLatency ? (
        <p className="font-mono text-[10px] text-[color:var(--muted)]" data-latency-badge>
          SQL: {lat.sql ?? "—"}ms, Card: {lat.card ?? "—"}ms, Corpus: {lat.corpus ?? "—"}ms
        </p>
      ) : null}
    </section>
  );
}
