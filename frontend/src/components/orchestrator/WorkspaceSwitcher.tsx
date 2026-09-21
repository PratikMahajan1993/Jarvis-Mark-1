"use client";

import type { HudWorkspace } from "./hudWorkspace";
import { WORKSPACE_LABELS } from "./hudWorkspace";

const MODES: HudWorkspace[] = ["casual", "monitor", "engineering"];

type WorkspaceSwitcherProps = {
  workspace: HudWorkspace;
  pinned: boolean;
  dimmed?: boolean;
  onSelect: (workspace: HudWorkspace) => void;
  onTogglePin: () => void;
};

function PinIcon({ pinned }: { pinned: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className="h-3 w-3"
      fill={pinned ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.4"
      aria-hidden
    >
      <path d="M8 1.5 6.2 3.3 4.5 2.8 3.8 4.5 2.1 5.2 2.6 6.9 1.5 8 2.6 9.1 2.1 10.8 3.8 11.5 4.5 13.2 6.2 12.7 8 14.5 9.8 12.7 11.5 13.2 12.2 11.5 13.9 10.8 13.4 9.1 14.5 8 13.4 6.9 13.9 5.2 12.2 4.5 11.5 2.8 9.8 3.3z" />
      <circle cx="8" cy="8" r="1.6" fill={pinned ? "var(--bg)" : "none"} />
    </svg>
  );
}

export function WorkspaceSwitcher({
  workspace,
  pinned,
  dimmed = false,
  onSelect,
  onTogglePin,
}: WorkspaceSwitcherProps) {
  return (
    <div
      className={[
        "orch-workspace-switcher pointer-events-auto absolute left-4 top-4 z-[12] flex items-center gap-1 rounded-full border border-[color:var(--border)] bg-black/40 p-1 backdrop-blur-md transition",
        dimmed ? "opacity-45" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      role="group"
      aria-label="HUD workspace"
    >
      {MODES.map((mode) => {
        const active = workspace === mode;
        return (
          <button
            key={mode}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(mode)}
            className={[
              "rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] transition",
              active
                ? "border border-[color:var(--accent)]/45 bg-[color:var(--accent)]/12 text-[color:var(--accent)]"
                : "border border-transparent text-[color:var(--muted)] hover:border-[color:var(--accent)]/25 hover:text-[color:var(--accent)]/85",
            ].join(" ")}
          >
            {WORKSPACE_LABELS[mode]}
          </button>
        );
      })}
      <span className="mx-0.5 h-4 w-px bg-[color:var(--border)]" aria-hidden />
      <button
        type="button"
        aria-pressed={pinned}
        aria-label={pinned ? "Unpin workspace" : "Pin workspace"}
        title={pinned ? "Pinned — auto-switch paused" : "Pin current workspace"}
        onClick={onTogglePin}
        className={[
          "flex h-7 w-7 items-center justify-center rounded-full border transition",
          pinned
            ? "border-[color:var(--accent)]/45 bg-[color:var(--accent)]/12 text-[color:var(--accent)]"
            : "border-transparent text-[color:var(--muted)] hover:border-[color:var(--accent)]/25 hover:text-[color:var(--accent)]/85",
        ].join(" ")}
      >
        <PinIcon pinned={pinned} />
      </button>
    </div>
  );
}
