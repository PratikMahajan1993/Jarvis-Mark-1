import type { PendingAction } from "@/lib/types";
import { shallICopy } from "@/lib/orchestrator";

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
  if (!action) return null;
  const copy = shallICopy(action);
  return (
    <div
      className={[
        "orch-hitl absolute inset-0 z-20 flex items-center justify-center transition-opacity duration-[600ms]",
        visible ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
      ].join(" ")}
    >
      <div
        className={[
          "orch-hitl-modal flex w-[520px] max-w-[calc(100vw-2rem)] flex-col items-center rounded-xl border border-[color:var(--border)] px-12 py-12 text-center shadow-[0_40px_80px_rgba(0,0,0,0.8)] backdrop-blur-[20px] transition-all duration-[600ms]",
          visible ? "translate-y-0 scale-100" : "translate-y-5 scale-95",
        ].join(" ")}
        style={{ background: "rgba(14, 14, 16, 0.7)" }}
      >
        <div className="mb-6 font-mono text-[0.7rem] uppercase tracking-[0.05em] text-[color:var(--accent)]">
          {copy.meta}
        </div>
        <h2 className="mb-4 font-display text-2xl font-normal text-[color:var(--fg)]">{copy.title}</h2>
        <p className="mb-10 text-[0.95rem] leading-relaxed text-[color:var(--muted)]">{copy.summary}</p>
        <div className="flex w-full gap-4">
          <button
            type="button"
            disabled={busy}
            className="flex-1 rounded-md border border-[color:var(--border)] bg-transparent py-3 text-[0.9rem] font-medium text-[color:var(--fg)] transition hover:border-[color:var(--muted)] hover:bg-[color:var(--surface)] disabled:opacity-40"
            onClick={() => onDecide(action.id, false)}
          >
            Reject
          </button>
          <button
            type="button"
            disabled={busy}
            className="flex-1 rounded-md border border-[color:var(--fg)] bg-[color:var(--fg)] py-3 text-[0.9rem] font-medium text-black transition hover:bg-transparent hover:text-[color:var(--fg)] disabled:opacity-40"
            onClick={() => onDecide(action.id, true)}
          >
            Authorize
          </button>
        </div>
        <p className="mt-5 font-mono text-[11px] uppercase tracking-[0.18em] text-white/25">
          {listening ? "Listening…" : "or say yes / no"}
        </p>
      </div>
    </div>
  );
}
