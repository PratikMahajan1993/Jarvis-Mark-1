"use client";

import { LayoutGroup, MotionConfig } from "motion/react";
import gsap from "gsap";
import { useEffect, useRef, type ReactNode } from "react";
import type { HudWorkspace } from "@/components/orchestrator/hudWorkspace";
import type { OrchestratorMode } from "@/lib/orchestrator";
import { LENS_THEME, lensForWorkspace } from "@/lib/pane/lenses";
import {
  getPaneState,
  initLensFromWorkspace,
  markPaneSettled,
  registerLensSideEffect,
  setLens,
  setPresenceMode,
  useLens,
} from "@/lib/pane/paneStore";
import { DURATION, EASE } from "@/lib/pane/springs";
import type { Lens } from "@/substrate/protocol";
import { CommandBaton } from "@/components/orchestrator/CommandBaton";
import { Dock } from "./Dock";
import { Field } from "./Field";
import { PanePanel } from "./PanePanel";
import { StatusCluster } from "./StatusCluster";
import { Substrate } from "./Substrate";
import { useSyncWorkspaceLens } from "./LensTabs";
import { Vignette } from "./Vignette";

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

function applyLensTheme(root: HTMLElement, to: Lens) {
  const T = LENS_THEME[to];
  gsap.killTweensOf(root);
  gsap.to(root, {
    "--bg": T.bg,
    "--surface": T.surface,
    "--fg": T.fg,
    "--muted": T.muted,
    "--border": T.border,
    "--accent": T.accent,
    "--mat": T.mat,
    "--grid-opacity": T.gridOpacity,
    "--vignette-opacity": T.vignetteOpacity,
    duration: DURATION.theme,
    ease: EASE.gsapOut,
    onComplete: () => markPaneSettled(),
  });
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
  const lens = useLens();
  const initialized = useRef(false);

  useSyncWorkspaceLens(workspace);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const boot = lensForWorkspace(workspace);
    initLensFromWorkspace(boot);
    setLens(boot);
    const root = rootRef.current;
    if (root) {
      const T = LENS_THEME[getPaneState().lens];
      gsap.set(root, {
        "--bg": T.bg,
        "--surface": T.surface,
        "--fg": T.fg,
        "--muted": T.muted,
        "--border": T.border,
        "--accent": T.accent,
        "--mat": T.mat,
        "--grid-opacity": T.gridOpacity,
        "--vignette-opacity": T.vignetteOpacity,
      });
    }
  }, [workspace]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    return registerLensSideEffect((to) => {
      applyLensTheme(root, to);
    });
  }, []);

  useEffect(() => {
    setPresenceMode(modeToPresence(orchestratorMode));
    const post = window.__JARVIS_SUBSTRATE__?.post;
    post?.({ type: "mode", mode: modeToPresence(orchestratorMode) });
  }, [orchestratorMode]);

  const bench = lens === "bench";

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
        <CommandBaton
          value={compose}
          onChange={onComposeChange}
          onSubmit={onComposeSubmit}
          onMic={onMic}
          listening={listening}
          disabled={batonDisabled}
          hidden={batonHidden}
        />
      ) : null}
    </div>
  );

  const wrapped = sparkWrapper ? sparkWrapper(inner) : inner;
  return wrapped;
}

export { useLens as usePaneLens };
