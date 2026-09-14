"use client";

export type SuggestedTask = {
  id: string;
  kind: string;
  title: string;
  detail: string;
  actions: { id: string; label: string }[];
  status?: string;
  source_id?: string;
  meta?: Record<string, unknown>;
};

export function SuggestedTasksPanel({
  tasks,
  weather,
  onAction,
  onDismiss,
}: {
  tasks: SuggestedTask[];
  weather?: string;
  onAction: (task: SuggestedTask, actionId: string) => void;
  onDismiss: (taskId: string) => void;
}) {
  if (!tasks.length && !weather) return null;
  return (
    <aside className="pointer-events-auto absolute right-4 top-24 z-10 flex w-[min(360px,92vw)] flex-col gap-3">
      {weather ? (
        <div className="rounded-lg border border-[color:var(--border)] bg-black/40 px-4 py-3 text-sm text-[color:var(--muted)] backdrop-blur-md">
          <div className="mb-1 font-mono text-[0.65rem] uppercase tracking-[0.12em] text-[color:var(--accent)]">
            Weather
          </div>
          {weather}
        </div>
      ) : null}
      {tasks.map((task) => (
        <div
          key={task.id}
          className="rounded-lg border border-[color:var(--border)] bg-black/50 px-4 py-4 shadow-[0_20px_40px_rgba(0,0,0,0.45)] backdrop-blur-md"
        >
          <div className="mb-2 flex items-start justify-between gap-2">
            <div className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-[color:var(--accent)]">
              {task.kind}
            </div>
            <button
              type="button"
              className="text-[0.7rem] text-white/35 hover:text-white/70"
              onClick={() => onDismiss(task.id)}
            >
              Dismiss
            </button>
          </div>
          <h3 className="mb-2 font-display text-lg leading-snug text-[color:var(--fg)]">{task.title}</h3>
          <p className="mb-4 text-[0.8rem] leading-relaxed text-[color:var(--muted)] line-clamp-4">
            {task.detail}
          </p>
          <div className="flex flex-col gap-2">
            {(task.actions || []).map((action) => (
              <button
                key={action.id}
                type="button"
                className="rounded-md border border-[color:var(--border)] px-3 py-2 text-left text-[0.8rem] text-[color:var(--fg)] transition hover:border-[color:var(--accent)] hover:bg-white/5"
                onClick={() => onAction(task, action.id)}
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>
      ))}
    </aside>
  );
}
