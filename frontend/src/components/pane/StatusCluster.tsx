"use client";

import type { ReactNode } from "react";
import GradientText from "@/components/react-bits/GradientText";
import { LensTabs } from "./LensTabs";
import type { HudWorkspace } from "@/components/orchestrator/hudWorkspace";
import { useLens } from "@/lib/pane/paneStore";

type StatusClusterProps = {
  workspace: HudWorkspace;
  workspacePinned: boolean;
  dimmed?: boolean;
  assistantName: string;
  focusTitle: string;
  onSelectWorkspace: (workspace: HudWorkspace) => void;
  onTogglePin: () => void;
  onOpenPrefs: () => void;
  agentsSlot?: ReactNode;
};

export function StatusCluster({
  workspace,
  workspacePinned,
  dimmed,
  assistantName,
  focusTitle,
  onSelectWorkspace,
  onTogglePin,
  onOpenPrefs,
  agentsSlot,
}: StatusClusterProps) {
  const lens = useLens();

  return (
    <header className="pointer-events-none absolute inset-x-0 top-0 z-[60] flex h-14 items-center justify-between px-4 isolation-isolate">
      <div className="pointer-events-auto flex min-w-0 items-center gap-3">
        <div
          className="relative h-12 w-12 shrink-0 rounded-full border border-[color:var(--accent)]/25 bg-black/30"
          aria-hidden
          data-pilot-light
        >
          {lens === "bench" ? (
            <span className="absolute inset-0 rounded-full bg-[color:var(--accent)]/20 shadow-[0_0_12px_color-mix(in_oklch,var(--accent)_40%,transparent)]" />
          ) : null}
        </div>
        {agentsSlot ? (
          <div className="pointer-events-auto flex items-center gap-1" data-agents-status>
            {agentsSlot}
          </div>
        ) : null}
        <div className="min-w-0">
          <p className="status-title truncate font-mono text-[10px] uppercase tracking-[0.18em] text-[color:var(--muted)]">
            <GradientText className="font-mono text-[10px] uppercase tracking-[0.18em]" animationSpeed={9}>
              {assistantName}
            </GradientText>
            <span className="mx-2 text-[color:var(--muted)]/40">·</span>
            <span className="text-[color:var(--fg)]/90">{focusTitle}</span>
          </p>
        </div>
      </div>
      <div className="pointer-events-auto flex items-center gap-2">
        <LensTabs
          workspace={workspace}
          pinned={workspacePinned}
          dimmed={dimmed}
          onSelectWorkspace={onSelectWorkspace}
          onTogglePin={onTogglePin}
        />
        <button
          type="button"
          onClick={onOpenPrefs}
          className="rounded-full border border-[color:var(--border)] bg-black/40 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)] transition hover:border-[color:var(--accent)]/40 hover:text-[color:var(--accent)]"
          title="Preferences — Connect Gmail, voice, and connectors"
        >
          Prefs
        </button>
      </div>
    </header>
  );
}
