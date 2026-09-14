import type { PendingAction } from "@/lib/types";
import { HudButton, Panel } from "./hud/Hud";

const CNC_PROMOTE_SUMMARY =
  "This is a draft program, not proven. It is not for the machine until you say Yes.";
const SHEETS_WRITE_SUMMARY =
  "This overwrites production numbers in the bound Google Sheet. Google will autosave.";

export function shallICopy(action: PendingAction): {
  title: string;
  summary: string;
  consequence?: string;
  irreversibility?: number;
} {
  const score = Math.min(5, Math.max(1, Number(action.irreversibility) || 2));
  const consequence =
    (action.consequence || "").trim() || "Queued action — review before authorizing.";
  if (action.kind === "cnc_promote") {
    const title = (action.title || "").trim() || "Shall I promote a draft NC?";
    return { title, summary: CNC_PROMOTE_SUMMARY, consequence, irreversibility: score };
  }
  if (action.kind === "sheets_write") {
    const title = (action.title || "").trim() || "Overwrite production numbers?";
    return { title, summary: SHEETS_WRITE_SUMMARY, consequence, irreversibility: score };
  }
  return {
    title: action.title,
    summary: action.summary,
    consequence,
    irreversibility: score,
  };
}

export function ConfirmBar({
  actions,
  onDecide,
  listening = false,
}: {
  actions: PendingAction[];
  onDecide: (id: string, approved: boolean) => void;
  listening?: boolean;
}) {
  const action = actions[0];
  if (!action) return null;
  const copy = shallICopy(action);
  return (
    <div className="fixed inset-0 z-30 grid place-items-center bg-black/60 backdrop-blur-sm">
      <Panel accent="amber" eyebrow="Confirmation required" className="w-full max-w-lg" bodyClassName="px-8 py-7 text-center">
        <p className="font-display text-3xl text-white">Shall I?</p>
        <p className="mt-3 text-lg text-white/70">{copy.title}</p>
        <p className="mt-1 text-sm text-white/40">{copy.summary}</p>
        {copy.consequence ? (
          <p className="mt-3 text-left text-sm text-amber-200/80">
            <span className="font-mono text-[10px] uppercase tracking-wider text-amber-400/90">
              Blast radius · {copy.irreversibility ?? 2}/5
            </span>
            <br />
            {copy.consequence}
          </p>
        ) : null}
        <div className="mt-7 flex justify-center gap-4">
          <HudButton variant="ghost" onClick={() => onDecide(action.id, false)}>
            No
          </HudButton>
          <HudButton variant="primary" className="border-amber/50 text-amber hover:border-amber hover:bg-amber/15 hover:shadow-glow-amber" onClick={() => onDecide(action.id, true)}>
            Yes
          </HudButton>
        </div>
        <p className="mt-5 font-mono text-[11px] uppercase tracking-[0.18em] text-white/25">
          {listening ? "Listening…" : "or say yes"}
        </p>
      </Panel>
    </div>
  );
}
