"use client";

import { useCallback, useEffect, useState } from "react";
import GradientText from "@/components/react-bits/GradientText";
import SpotlightCard from "@/components/react-bits/SpotlightCard";
import { FreshnessBadge } from "@/components/bench/FreshnessBadge";

type CandidateFact = {
  id: string;
  field: string;
  value: string;
  unit?: string;
  source_kind: string;
  source_ref?: string;
};

type CardPayload = {
  enabled: boolean;
  found?: boolean;
  facts?: CandidateFact[];
  candidates?: CandidateFact[];
  freshness?: { updated_at?: string; stale?: boolean };
  card?: { updated_at?: string };
};

function apiBase(): string {
  const fallback = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  if (typeof window === "undefined") return fallback;
  try {
    const configured = new URL(fallback, window.location.origin);
    const pageHost = window.location.hostname;
    const loopback = configured.hostname === "localhost" || configured.hostname === "127.0.0.1";
    if (loopback && pageHost !== "localhost" && pageHost !== "127.0.0.1") {
      return `${window.location.protocol}//${pageHost}:8000`;
    }
    return configured.origin;
  } catch {
    return fallback;
  }
}

function isHighValueField(field: string): boolean {
  const key = (field || "").trim().toLowerCase();
  if (!key) return false;
  if (key === "material" || key === "scope" || key === "qty" || key === "quantity") return true;
  if (key.includes("tolerance") || key.includes("heat_treat")) return true;
  return false;
}

function formatFieldLabel(field: string): string {
  const trimmed = (field || "").trim();
  if (!trimmed) return "Field";
  return trimmed.replace(/_/g, " ");
}

function formatValue(fact: CandidateFact): string {
  const value = (fact.value || "").trim();
  const unit = (fact.unit || "").trim();
  if (unit) return `${value} ${unit}`.trim();
  return value;
}

function formatSource(fact: CandidateFact): string {
  const kind = (fact.source_kind || "").trim();
  if (kind === "vision_suggestion") return "vision";
  const ref = (fact.source_ref || "").trim();
  if (kind && ref) return `${kind} · ${ref}`;
  return kind || ref || "unknown source";
}

export function FactConfirmChips({
  entityType = "",
  entityId = "",
  sessionId = "",
}: {
  entityType?: string;
  entityId?: string;
  sessionId?: string;
}) {
  const et = entityType.trim() || "part_revision";
  const [eid, setEid] = useState(entityId.trim());
  const [candidates, setCandidates] = useState<CandidateFact[]>([]);
  const [freshness, setFreshness] = useState<{ updated_at?: string; stale?: boolean } | null>(null);
  const [visible, setVisible] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    const explicit = entityId.trim();
    if (explicit) {
      setEid(explicit);
      return;
    }
    if (!sessionId.trim()) return;
    let cancelled = false;
    void fetch(`${apiBase()}/api/knowledge/drawing-identity?session_id=${encodeURIComponent(sessionId)}`)
      .then(async (res) => {
        if (!res.ok || cancelled) return;
        const body = (await res.json()) as { part_revision_id?: string | null };
        if (!cancelled && body.part_revision_id) setEid(body.part_revision_id);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [entityId, sessionId]);

  const refresh = useCallback(async () => {
    if (!et || !eid) {
      setVisible(false);
      setCandidates([]);
      setFreshness(null);
      return;
    }
    try {
      const qs = new URLSearchParams({ entity_type: et, entity_id: eid });
      const res = await fetch(`${apiBase()}/api/knowledge/card?${qs.toString()}`);
      if (!res.ok) {
        setVisible(false);
        setCandidates([]);
        return;
      }
      const data = (await res.json()) as CardPayload;
      if (!data.enabled) {
        setVisible(false);
        setCandidates([]);
        return;
      }
      setFreshness(data.freshness ?? (data.card?.updated_at ? { updated_at: data.card.updated_at } : null));
      const list = data.candidates ?? [];
      if (!list.length) {
        setVisible(false);
        setCandidates([]);
        return;
      }
      setCandidates(list);
      setVisible(true);
    } catch {
      setVisible(false);
      setCandidates([]);
    }
  }, [et, eid]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const valueFor = useCallback(
    (fact: CandidateFact) => {
      if (draftValues[fact.id] !== undefined) return draftValues[fact.id];
      return formatValue(fact);
    },
    [draftValues],
  );

  const confirmLabel = useCallback(
    (fact: CandidateFact) => {
      if (!isHighValueField(fact.field)) return "Confirm";
      const v = valueFor(fact).trim();
      if (!v) return `Confirm ${formatFieldLabel(fact.field)}`;
      return `Confirm ${v}`;
    },
    [valueFor],
  );

  const onConfirm = async (fact: CandidateFact) => {
    setBusyId(fact.id);
    try {
      const high = isHighValueField(fact.field);
      const body: { confirmed_by: string; value?: string } = { confirmed_by: "owner" };
      if (high) body.value = valueFor(fact);
      const res = await fetch(`${apiBase()}/api/knowledge/facts/${encodeURIComponent(fact.id)}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) return;
      setEditingId((id) => (id === fact.id ? null : id));
      await refresh();
    } finally {
      setBusyId(null);
    }
  };

  const onReject = async (fact: CandidateFact) => {
    setBusyId(fact.id);
    try {
      const res = await fetch(`${apiBase()}/api/knowledge/facts/${encodeURIComponent(fact.id)}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) return;
      setEditingId((id) => (id === fact.id ? null : id));
      await refresh();
    } finally {
      setBusyId(null);
    }
  };

  if (!visible || !candidates.length) return null;

  return (
    <SpotlightCard
      className="shrink-0 rounded-2xl border border-[color:var(--border)] bg-black/40 backdrop-blur-md"
      bodyClassName="p-4"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em]">
          <GradientText className="font-mono text-[10px] uppercase tracking-[0.22em]" animationSpeed={9}>
            Confirm facts
          </GradientText>
        </p>
        <FreshnessBadge updatedAt={freshness?.updated_at} stale={freshness?.stale} />
      </div>
      <ul className="space-y-2">
        {candidates.map((fact) => {
          const high = isHighValueField(fact.field);
          const displayValue = valueFor(fact);
          const editing = editingId === fact.id;
          const disabled = busyId === fact.id;
          return (
            <li
              key={fact.id}
              className="flex flex-col gap-2 rounded-xl border border-[color:var(--border)] bg-black/35 px-3 py-2.5"
            >
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--accent)]/75">
                  {formatFieldLabel(fact.field)}
                </span>
                {editing && high ? (
                  <input
                    type="text"
                    value={draftValues[fact.id] ?? formatValue(fact)}
                    onChange={(e) =>
                      setDraftValues((prev) => ({ ...prev, [fact.id]: e.target.value }))
                    }
                    className="min-w-0 flex-1 rounded-md border border-[#7dffe0]/30 bg-black/50 px-2 py-1 font-display text-sm text-[color:var(--fg)]"
                  />
                ) : (
                  <span className="font-display text-sm text-[color:var(--fg)]/95">
                    {displayValue || "—"} [{formatSource(fact)}]
                  </span>
                )}
              </div>
              <p className="font-mono text-[10px] leading-snug text-[color:var(--muted)]/80">
                {formatSource(fact)}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => void onConfirm(fact)}
                  className="shrink-0 rounded-lg border border-[#7dffe0]/35 bg-[#7dffe0]/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-[color:var(--fg)] transition hover:bg-[#7dffe0]/20 disabled:opacity-50"
                >
                  {confirmLabel(fact)}
                </button>
                {high ? (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => {
                      if (editing) {
                        setEditingId(null);
                        return;
                      }
                      setDraftValues((prev) => ({
                        ...prev,
                        [fact.id]: prev[fact.id] ?? formatValue(fact),
                      }));
                      setEditingId(fact.id);
                    }}
                    className="shrink-0 rounded-lg border border-[color:var(--border)] bg-black/40 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-[color:var(--muted)] transition hover:border-[#7dffe0]/25 hover:text-[color:var(--fg)] disabled:opacity-50"
                  >
                    {editing ? "Done" : "Edit"}
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => void onReject(fact)}
                  className="shrink-0 rounded-lg border border-red-400/25 bg-red-950/30 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-red-200/90 transition hover:bg-red-950/50 disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </SpotlightCard>
  );
}
