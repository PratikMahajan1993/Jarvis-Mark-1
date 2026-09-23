"use client";

import { useCallback, useEffect } from "react";
import type { HudWorkspace } from "@/components/orchestrator/hudWorkspace";
import { WORKSPACE_LABELS } from "@/components/orchestrator/hudWorkspace";
import { lensForWorkspace, workspaceForLens } from "@/lib/pane/lenses";
import { getPaneState, setLens, useLens } from "@/lib/pane/paneStore";
import type { Lens } from "@/substrate/protocol";

const LENS_ORDER: Lens[] = ["watch", "converse", "bench"];
const LENS_TO_WORKSPACE: Record<Lens, HudWorkspace> = {
  watch: "monitor",
  converse: "casual",
  bench: "engineering",
};

type LensTabsProps = {
  workspace: HudWorkspace;
  pinned: boolean;
  dimmed?: boolean;
  onSelectWorkspace: (workspace: HudWorkspace) => void;
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

export function LensTabs({
  workspace,
  pinned,
  dimmed = false,
  onSelectWorkspace,
  onTogglePin,
}: LensTabsProps) {
  const lens = useLens();

  const selectLens = useCallback(
    (next: Lens) => {
      setLens(next);
      onSelectWorkspace(LENS_TO_WORKSPACE[next]);
    },
    [onSelectWorkspace],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.altKey || e.shiftKey || e.ctrlKey || e.metaKey) return;
      const idx = Number(e.key);
      if (idx >= 1 && idx <= 3) {
        e.preventDefault();
        selectLens(LENS_ORDER[idx - 1]!);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectLens]);

  return (
    <div
      className={[
        "flex items-center gap-1 rounded-full border border-[color:var(--border)] bg-black/40 p-1",
        dimmed ? "opacity-45" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      role="tablist"
      aria-label="HUD lens"
    >
      {LENS_ORDER.map((mode) => {
        const ws = workspaceForLens(mode);
        const active = lens === mode;
        return (
          <button
            key={mode}
            type="button"
            role="tab"
            aria-selected={active}
            id={`lens-tab-${mode}`}
            onClick={() => selectLens(mode)}
            className={[
              "rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] transition",
              active
                ? "border border-[color:var(--accent)]/45 bg-[color:var(--accent)]/12 text-[color:var(--accent)]"
                : "border border-transparent text-[color:var(--muted)] hover:border-[color:var(--accent)]/25 hover:text-[color:var(--accent)]/85",
            ].join(" ")}
          >
            {WORKSPACE_LABELS[ws]}
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

/** Keep lens in sync when workspace changes from shell (voice routing, focus) without shell subscribing to lens. */
export function useSyncWorkspaceLens(workspace: HudWorkspace): void {
  useEffect(() => {
    const target = lensForWorkspace(workspace);
    if (getPaneState().lens !== target) setLens(target);
  }, [workspace]);
}
