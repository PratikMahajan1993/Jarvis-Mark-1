"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DrawingIdentity } from "@/lib/pane/knowledge";

function ackKey(identity: DrawingIdentity): string {
  return `jarvis-revision-ack:${identity.prior_part_revision_id || ""}:${identity.part_revision_id || ""}`;
}

export function RevisionDiffBanner({ sessionId = "default" }: { sessionId?: string }) {
  const [identity, setIdentity] = useState<DrawingIdentity | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const body = await api.drawingIdentity(sessionId);
      if (body.kind !== "revision_change") {
        setIdentity(null);
        return;
      }
      setIdentity(body);
      const stored = window.sessionStorage.getItem(ackKey(body));
      setDismissed(stored === "1");
    } catch {
      setIdentity(null);
    }
  }, [sessionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!identity || identity.kind !== "revision_change" || dismissed) return null;

  const details = identity.change_details || [];
  const names = (identity.changed_fields || []).join(", ") || "none yet";

  return (
    <div
      className="rounded-xl border border-[color:oklch(78%_0.16_25)]/50 bg-[color:oklch(30%_0.06_25)]/40 px-3 py-2"
      data-revision-diff
    >
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[color:oklch(82%_0.12_25)]">
        {identity.banner || `This is a new revision — confirmed fields changed: ${names}`}
      </p>
      {details.length ? (
        <ul className="mt-2 space-y-1">
          {details.map((row) => (
            <li key={row.field} className="font-mono text-[11px] text-[color:var(--fg)]">
              {row.field}: {row.prior_value || "—"} → {row.current_value || "—"}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          className="rounded border border-[color:var(--border)] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em]"
          onClick={() => {
            window.sessionStorage.setItem(ackKey(identity), "1");
            setDismissed(true);
          }}
        >
          Acknowledge
        </button>
        <button
          type="button"
          className="rounded border border-[color:var(--border)] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)]"
          onClick={() => setDismissed(true)}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
