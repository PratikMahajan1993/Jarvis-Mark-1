"use client";

import type { PendingAction } from "@/lib/types";
import { shallICopy } from "@/lib/orchestrator";
import ElectricBorder from "@/components/react-bits/ElectricBorder";
import GlareHover from "@/components/react-bits/GlareHover";
import { useEffect, useRef } from "react";

export function HitlModal({
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
  onDecide: (id: string, approved: boolean) => void;
}) {
  const authRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (visible && authRef.current) {
      authRef.current.focus();
    }
  }, [visible]);

  if (!action) return null;
  const copy = shallICopy(action);
  return (
    <div
      className={[
        "orch-hitl absolute inset-0 z-20 flex items-center justify-center transition-opacity duration-[600ms]",
        visible ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
      ].join(" ")}
      role="dialog"
      aria-modal="true"
      aria-labelledby="hitl-title"
    >
      <ElectricBorder
        color="#7dffe0"
        speed={0.65}
        chaos={0.07}
        borderRadius={14}
        className={[
          "w-[520px] max-w-[calc(100vw-2rem)] transition-all duration-[600ms]",
          visible ? "translate-y-0 scale-100" : "translate-y-5 scale-95",
        ].join(" ")}
      >
        <div
          className="orch-hitl-modal flex w-full flex-col items-center rounded-xl border border-[color:var(--border)] px-12 py-12 text-center shadow-[0_40px_80px_rgba(0,0,0,0.8)] backdrop-blur-[20px]"
          style={{ background: "rgba(14, 14, 16, 0.78)" }}
        >
          <div className="mb-6 font-mono text-[0.7rem] uppercase tracking-[0.05em] text-[color:var(--accent)]">
            {copy.meta}
          </div>
          <h2 id="hitl-title" className="mb-4 font-display text-2xl font-normal text-[color:var(--fg)]">{copy.title}</h2>
          <p className="mb-4 text-[0.95rem] leading-relaxed text-[color:var(--muted)]">{copy.summary}</p>
          <p className="mb-10 max-w-md text-left text-[0.85rem] leading-relaxed text-[color:var(--fg)]/80">
            <span className="font-mono text-[0.65rem] uppercase tracking-[0.08em] text-[color:var(--accent)]">
              Impact — {copy.irreversibility}/5
            </span>
            <br />
            {copy.consequence}
          </p>
          <div className="flex w-full gap-4">
            <button
              type="button"
              disabled={busy}
              className="flex-1 rounded-md border border-[color:var(--border)] bg-transparent py-3 text-[0.9rem] font-medium text-[color:var(--fg)] transition hover:border-[color:var(--muted)] hover:bg-[color:var(--surface)] disabled:opacity-40"
              onClick={() => onDecide(action.id, false)}
            >
              Reject
            </button>
            <GlareHover className="flex-1 rounded-md" glareColor="#ffffff" glareOpacity={0.4}>
              <button
                ref={authRef}
                type="button"
                disabled={busy}
                className="relative z-[2] w-full rounded-md border border-[color:var(--fg)] bg-[color:var(--fg)] py-3 text-[0.9rem] font-medium text-black transition hover:bg-transparent hover:text-[color:var(--fg)] disabled:opacity-40"
                onClick={() => onDecide(action.id, true)}
              >
                Authorize
              </button>
            </GlareHover>
          </div>
          <p className="mt-5 font-mono text-[11px] uppercase tracking-[0.18em] text-white/25">
            {listening ? "Listening…" : "or say yes / no · press Y / N"}
          </p>
        </div>
      </ElectricBorder>
    </div>
  );
}
