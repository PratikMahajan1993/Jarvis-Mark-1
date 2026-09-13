"use client";

import { useEffect, useState } from "react";
import type { PendingAction } from "@/lib/types";

function fieldValue(payload: Record<string, unknown> | undefined, key: string): string {
  const raw = payload?.[key];
  return typeof raw === "string" ? raw : "";
}

function missingSet(payload: Record<string, unknown> | undefined): Set<string> {
  const raw = payload?.missing;
  if (!Array.isArray(raw)) return new Set();
  return new Set(raw.filter((item): item is string => typeof item === "string"));
}

export function DraftComposeModal({
  action,
  visible,
  listening = false,
  busy = false,
  onDecide,
}: {
  action: PendingAction | null;
  visible: boolean;
  listening?: boolean;
  busy?: boolean;
  onDecide: (id: string, approved: boolean, fields: { to: string; subject: string; body: string }) => void;
}) {
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    if (!action) return;
    setTo(fieldValue(action.payload, "to"));
    setSubject(fieldValue(action.payload, "subject"));
    setBody(fieldValue(action.payload, "body"));
  }, [action?.id, action?.payload]);

  useEffect(() => {
    if (!visible) {
      setSettled(false);
      return;
    }
    const timer = window.setTimeout(() => setSettled(true), 280);
    return () => window.clearTimeout(timer);
  }, [visible, action?.id]);

  if (!action) return null;
  const missing = missingSet(action.payload);

  const inputClass = (key: string) =>
    [
      "w-full rounded-md border bg-black/30 px-3 py-2 text-left text-[0.9rem] text-[color:var(--fg)] outline-none transition",
      missing.has(key) || !(key === "to" ? to : key === "subject" ? subject : body).trim()
        ? "border-[color:var(--accent)]/70"
        : "border-[color:var(--border)]",
    ].join(" ");

  return (
    <div
      className={[
        "orch-compose absolute inset-0 z-20 flex items-center justify-center transition-opacity duration-[500ms]",
        visible ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
      ].join(" ")}
    >
      <div
        className={[
          "orch-compose-glow pointer-events-none absolute left-1/2 top-1/2 h-[420px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full",
          visible ? "orch-compose-glow-on" : "",
          settled ? "orch-compose-glow-shift" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        aria-hidden
      />

      <div
        className={[
          "orch-compose-modal relative flex w-[560px] max-w-[calc(100vw-2rem)] flex-col rounded-xl border border-[color:var(--border)] px-10 py-10 backdrop-blur-[20px]",
          visible ? "orch-compose-modal-in" : "orch-compose-modal-out",
          settled ? "orch-compose-modal-shift" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <div className="mb-5 text-center font-mono text-[0.7rem] uppercase tracking-[0.05em] text-[color:var(--accent)]">
          Draft · OPS.04
        </div>
        <h2 className="mb-6 text-center font-display text-2xl font-normal text-[color:var(--fg)]">Review email</h2>

        <label className="mb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">To</label>
        <input
          className={`mb-4 ${inputClass("to")}`}
          value={to}
          onChange={(event) => setTo(event.target.value)}
          placeholder="recipient@example.com"
          disabled={busy}
        />

        <label className="mb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
          Subject
        </label>
        <input
          className={`mb-4 ${inputClass("subject")}`}
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          placeholder="Subject"
          disabled={busy}
        />

        <label className="mb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">Body</label>
        <textarea
          className={`mb-8 min-h-[140px] resize-y ${inputClass("body")}`}
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Message body"
          disabled={busy}
        />

        <div className="flex w-full gap-4">
          <button
            type="button"
            disabled={busy}
            className="flex-1 rounded-md border border-[color:var(--border)] bg-transparent py-3 text-[0.9rem] font-medium text-[color:var(--fg)] transition hover:border-[color:var(--muted)] hover:bg-[color:var(--surface)] disabled:opacity-40"
            onClick={() => onDecide(action.id, false, { to, subject, body })}
          >
            Reject
          </button>
          <button
            type="button"
            disabled={busy}
            className="flex-1 rounded-md border border-[color:var(--fg)] bg-[color:var(--fg)] py-3 text-[0.9rem] font-medium text-black transition hover:bg-transparent hover:text-[color:var(--fg)] disabled:opacity-40"
            onClick={() => onDecide(action.id, true, { to, subject, body })}
          >
            Authorize
          </button>
        </div>
        <p className="mt-5 text-center font-mono text-[11px] uppercase tracking-[0.18em] text-white/25">
          {listening ? "Listening…" : "or say authorize / reject"}
        </p>
      </div>
    </div>
  );
}
