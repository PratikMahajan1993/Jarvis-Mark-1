import type { PendingAction } from "@/lib/types";

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
      <div className="max-w-lg px-8 text-center">
        <p className="font-display text-4xl text-white">Shall I?</p>
        <p className="mt-3 text-lg text-white/70">{action.title}</p>
        <p className="mt-1 text-sm text-white/40">{action.summary}</p>
        <div className="mt-8 flex justify-center gap-8">
          <button type="button" onClick={() => onDecide(action.id, false)} className="text-white/50 hover:text-white">
            No
          </button>
          <button type="button" onClick={() => onDecide(action.id, true)} className="text-amber hover:text-white">
            Yes
          </button>
        </div>
        <p className="mt-6 text-sm text-white/25">{listening ? "Listening…" : "or say yes"}</p>
      </div>
    </div>
  );
}
