"use client";

import { useEffect, useRef, useState } from "react";
import { api, apiBase } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";

type TurnStageLineProps = {
  turnId: string | null;
  onComplete: (output: ChatResponse) => void;
  onFailed?: (info: { error?: string; stage?: string; state?: string }) => void;
  /** Non-terminal frames from the existing turn SSE stream (and its poll fallback). */
  onReconcile?: (turnId: string, payload: TurnEventPayload) => void;
};

export type TurnEventPayload = {
  state?: string;
  stage?: string;
  output?: ChatResponse;
  error?: string;
};

function isTerminal(state: string | undefined): boolean {
  return state === "DONE" || state === "FAILED" || state === "ABANDONED";
}

export function TurnStageLine({ turnId, onComplete, onFailed, onReconcile }: TurnStageLineProps) {
  const [stage, setStage] = useState("");
  const finishedRef = useRef(false);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (!turnId) {
      setStage("");
      finishedRef.current = false;
      return;
    }

    finishedRef.current = false;
    setStage("");

    const finishFromPoll = async () => {
      if (finishedRef.current) return;
      try {
        const row = await api.getTurn(turnId);
        const st = String(row.stage || "").trim();
        if (st) setStage(st);
        const state = String(row.state || "");
        const payload: TurnEventPayload = {
          state,
          stage: st,
          error: row.error,
          output: row.output ?? undefined,
        };
        if (!isTerminal(state)) {
          onReconcile?.(turnId, payload);
          return;
        }
        finishedRef.current = true;
        if (state === "DONE" && row.output) {
          onComplete(row.output as ChatResponse);
        } else if (state === "FAILED" || state === "ABANDONED") {
          onFailed?.({ error: String(row.error || "Turn failed"), stage: st, state });
        }
      } catch {
        /* polling fallback only */
      }
    };

    const startPoll = () => {
      if (pollRef.current !== null) return;
      void finishFromPoll();
      pollRef.current = window.setInterval(() => void finishFromPoll(), 1000);
    };

    const url = `${apiBase()}/api/turns/${encodeURIComponent(turnId)}/events`;
    const es = new EventSource(url);

    const handlePayload = (payload: TurnEventPayload) => {
      const nextStage = (payload.stage || "").trim();
      if (nextStage) setStage(nextStage);
      if (!isTerminal(payload.state)) {
        onReconcile?.(turnId, payload);
        return;
      }
      if (finishedRef.current) return;
      finishedRef.current = true;
      es.close();
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      if (payload.state === "DONE" && payload.output) {
        onComplete(payload.output);
        return;
      }
      if (payload.state === "FAILED" || payload.state === "ABANDONED") {
        onFailed?.({ error: payload.error || "Turn failed", stage: payload.stage, state: payload.state });
        return;
      }
      void finishFromPoll();
    };

    es.addEventListener("turn", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data) as TurnEventPayload;
        handlePayload(data);
      } catch {
        /* ignore malformed frames */
      }
    });

    es.onerror = () => {
      es.close();
      startPoll();
    };

    return () => {
      es.close();
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [turnId, onComplete, onFailed, onReconcile]);

  if (!turnId) return null;

  const label = stage.trim() || "Queued…";

  return (
    <p
      className="mt-3 font-mono text-[10px] uppercase tracking-[0.22em] text-[color:var(--muted)]"
      aria-live="polite"
      data-turn-id={turnId}
    >
      {label}
    </p>
  );
}
