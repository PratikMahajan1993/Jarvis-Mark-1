import type { PendingAction } from "@/lib/types";
import { HudButton, Panel } from "./hud/Hud";

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
  return (
    <div className="fixed inset-0 z-30 grid place-items-center bg-black/60 backdrop-blur-sm">
      <Panel accent="amber" eyebrow="Confirmation required" className="w-full max-w-lg" bodyClassName="px-8 py-7 text-center">
        <p className="font-display text-3xl text-white">Shall I?</p>
        <p className="mt-3 text-lg text-white/70">{action.title}</p>
        <p className="mt-1 text-sm text-white/40">{action.summary}</p>
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
