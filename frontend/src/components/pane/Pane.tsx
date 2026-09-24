"use client";

import { LayoutGroup, MotionConfig } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";
import type { HudWorkspace } from "@/components/orchestrator/hudWorkspace";
import type { OrchestratorMode } from "@/lib/orchestrator";
import { lensForWorkspace } from "@/lib/pane/lenses";
import { bindConductor, snapLensTheme } from "@/lib/pane/conductor";
import {
  getPaneState,
  initLensFromWorkspace,
  setLens,
  setPresenceMode,
  subscribePane,
  useDisplayLens,
  useLens,
} from "@/lib/pane/paneStore";
import { CommandBaton } from "@/components/orchestrator/CommandBaton";
import { Dock } from "./Dock";
import { Field } from "./Field";
import { PanePanel } from "./PanePanel";
import { StatusCluster } from "./StatusCluster";
import { Substrate } from "./Substrate";
import { useSyncWorkspaceLens } from "./LensTabs";
import { Vignette } from "./Vignette";
import { usePaneIdleDim } from "./usePaneIdleDim";

export type PanePanels = {
  voice: ReactNode;
  notes: ReactNode;
  weather: ReactNode;
  tasks: ReactNode;
  agents: ReactNode;
  agentsStatus?: ReactNode;
  activity: ReactNode;
  stage: ReactNode;
  sheet: ReactNode;
};

export type PaneProps = {
  workspace: HudWorkspace;
  workspacePinned: boolean;
  orchestratorMode: OrchestratorMode;
  assistantName: string;
  focusTitle: string;
  dimmed?: boolean;
  batonHidden?: boolean;
  batonDisabled?: boolean;
  compose: string;
  listening: boolean;
  onComposeChange: (value: string) => void;
  onComposeSubmit: (value: string) => void;
  onMic: () => void;
  onSelectWorkspace: (workspace: HudWorkspace) => void;
  onTogglePin: () => void;
  onOpenPrefs: () => void;
  panels: PanePanels;
  className?: string;
  sparkWrapper?: (children: ReactNode) => ReactNode;
};

function modeToPresence(mode: OrchestratorMode): "idle" | "listening" | "thinking" | "speaking" | "hitl" {
  switch (mode) {
    case "listening":
      return "listening";
    case "hitl":
      return "hitl";
    case "busy":
      return "thinking";
    default:
      return "idle";
  }
}

export function Pane({
  workspace,
  workspacePinned,
  orchestratorMode,
  assistantName,
  focusTitle,
  dimmed,
  batonHidden,
  batonDisabled,
  compose,
  listening,
  onComposeChange,
  onComposeSubmit,
  onMic,
  onSelectWorkspace,
  onTogglePin,
  onOpenPrefs,
  panels,
  className = "",
  sparkWrapper,
}: PaneProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const displayLens = useDisplayLens();
  const initialized = useRef(false);

  usePaneIdleDim(rootRef, orchestratorMode, listening);
  useSyncWorkspaceLens(workspace);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    bindConductor({ root });
    const syncPhase = () => {
      root.dataset.phase = getPaneState().phase;
    };
    syncPhase();
    return subscribePane(syncPhase);
  }, []);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const boot = lensForWorkspace(workspace);
    initLensFromWorkspace(boot);
    setLens(boot);
    const root = rootRef.current;
    if (root) snapLensTheme(root, getPaneState().lens);
  }, [workspace]);

  useEffect(() => {
    setPresenceMode(modeToPresence(orchestratorMode));
    const post = window.__JARVIS_SUBSTRATE__?.post;
    post?.({ type: "mode", mode: modeToPresence(orchestratorMode) });
  }, [orchestratorMode]);

  const bench = displayLens === "bench";

  const inner = (
    <div
      ref={rootRef}
      className={["orch-root relative flex h-full min-h-0 flex-1 flex-col overflow-hidden", className]
        .filter(Boolean)
        .join(" ")}
      data-pane-root
    >
      <Substrate />
      <Field />
      <MotionConfig reducedMotion="user">
        <LayoutGroup id="pane">
          <Dock>
            <PanePanel id="voice">{panels.voice}</PanePanel>
            <PanePanel id="notes">{panels.notes}</PanePanel>
            <PanePanel id="weather">{panels.weather}</PanePanel>
            <PanePanel id="tasks">{panels.tasks}</PanePanel>
            <PanePanel id="agents">{panels.agents}</PanePanel>
            <PanePanel id="activity">{panels.activity}</PanePanel>
            <PanePanel id="stage">{panels.stage}</PanePanel>
            <PanePanel id="sheet">{panels.sheet}</PanePanel>
          </Dock>
        </LayoutGroup>
      </MotionConfig>
      <Vignette />
      <StatusCluster
        workspace={workspace}
        workspacePinned={workspacePinned}
        dimmed={dimmed}
        assistantName={assistantName}
        focusTitle={focusTitle}
        onSelectWorkspace={onSelectWorkspace}
        onTogglePin={onTogglePin}
        onOpenPrefs={onOpenPrefs}
        agentsSlot={panels.agentsStatus}
      />
      {!bench ? (
        <div
          className="pointer-events-none absolute inset-x-[calc(var(--inset,16px)+(100%-2*var(--inset,16px))*3/12+var(--gutter,12px))] bottom-[calc(var(--strip,72px)*0.18)] z-20 flex justify-center"
          aria-hidden={batonHidden}
        >
          <div className="pointer-events-auto">
            <CommandBaton
              value={compose}
              onChange={onComposeChange}
              onSubmit={onComposeSubmit}
              onMic={onMic}
              listening={listening}
              disabled={batonDisabled}
              hidden={batonHidden}
              absolute={false}
            />
          </div>
        </div>
      ) : null}
    </div>
  );

  const wrapped = sparkWrapper ? sparkWrapper(inner) : inner;
  return wrapped;
}

export { useLens as usePaneLens, useDisplayLens };
