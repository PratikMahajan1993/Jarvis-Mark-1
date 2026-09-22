"use client";

import { useCallback, useState } from "react";
import GradientText from "@/components/react-bits/GradientText";
import SpotlightCard from "@/components/react-bits/SpotlightCard";
import { api } from "@/lib/api";

const PLACEHOLDER =
  "changed the insert on the turning cell, two forty pieces, edge chipped";

type CaptureResult = Record<string, unknown>;

function resultLines(result: CaptureResult): string[] {
  if (result.ask === true) {
    const reason = typeof result.reason === "string" ? result.reason.trim() : "";
    return [reason ? `Not recorded — ${reason}` : "Not recorded."];
  }
  const lines: string[] = [];
  if (typeof result.reason === "string" && result.reason.trim()) {
    lines.push(result.reason.trim());
  }
  if (result.pieces_made !== undefined && result.pieces_made !== null && result.pieces_made !== "") {
    lines.push(`Pieces made: ${String(result.pieces_made)}`);
  }
  if (typeof result.alert === "string" && result.alert.trim()) {
    lines.push(result.alert.trim());
  }
  return lines;
}

export function ToolChangeField({
  openJobMachine = "",
  toolInstanceId = "",
}: {
  openJobMachine?: string;
  toolInstanceId?: string;
}) {
  const [utterance, setUtterance] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string[] | null>(null);

  const submit = useCallback(async () => {
    const text = utterance.trim();
    if (!text || busy) return;
    setBusy(true);
    setFeedback(null);
    try {
      const result = await api.toolwatchCapture({
        utterance: text,
        open_job_machine: openJobMachine.trim(),
        tool_instance_id: toolInstanceId.trim(),
      });
      setFeedback(resultLines(result));
      if (result.ask !== true) {
        setUtterance("");
      }
    } catch {
      setFeedback(["Capture failed — try again."]);
    } finally {
      setBusy(false);
    }
  }, [utterance, busy, openJobMachine, toolInstanceId]);

  return (
    <SpotlightCard
      className="shrink-0 rounded-2xl border border-[color:var(--border)] bg-black/40 backdrop-blur-md"
      bodyClassName="p-4"
    >
      <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em]">
        <GradientText className="font-mono text-[10px] uppercase tracking-[0.22em]" animationSpeed={9}>
          Tool change
        </GradientText>
      </p>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <input
          type="text"
          value={utterance}
          onChange={(e) => setUtterance(e.target.value)}
          placeholder={PLACEHOLDER}
          disabled={busy}
          className="min-w-0 flex-1 rounded-lg border border-[color:var(--border)] bg-black/50 px-3 py-2 text-sm text-[color:var(--fg)] placeholder:text-[color:var(--muted)]/50 focus:border-[#7dffe0]/40 focus:outline-none"
          aria-label="Tool change utterance"
        />
        <button
          type="submit"
          disabled={busy || !utterance.trim()}
          className="shrink-0 rounded-lg border border-[#7dffe0]/35 bg-[#7dffe0]/10 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--accent)] transition-opacity disabled:opacity-40"
        >
          {busy ? "…" : "Log"}
        </button>
      </form>
      {feedback?.length ? (
        <ul className="mt-2 space-y-1 text-xs text-[color:var(--fg)]/85">
          {feedback.map((line, i) => (
            <li key={`${i}-${line.slice(0, 24)}`}>{line}</li>
          ))}
        </ul>
      ) : null}
    </SpotlightCard>
  );
}
