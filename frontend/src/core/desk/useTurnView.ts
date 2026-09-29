"use client";

import type { OrchestratorMode } from "@/lib/orchestrator";
import { isBusy, type JarvisState } from "@/lib/orchestratorFsm";
import type { PendingAction } from "@/lib/types";
import { useTurn } from "@/core/stores/turnStore";

export type TurnView = {
  state: JarvisState;
  /** An Authorize / Reject approval is open (not the compose draft). */
  hitlAction: PendingAction | null;
  composeDraft: PendingAction | null;
  hitl: boolean;
  confirmListening: boolean;
  sending: boolean;
  listening: boolean;
  thinking: boolean;
  busy: boolean;
  mode: OrchestratorMode;
};

function orchestratorMode(state: JarvisState): OrchestratorMode {
  switch (state.mode) {
    case "LISTENING":
      return "listening";
    case "AWAITING_HITL":
      return "hitl";
    case "THINKING":
    case "SPEAKING":
    case "EXECUTING":
      return "busy";
    default:
      return "idle";
  }
}

export function useTurnView(): TurnView {
  const state = useTurn();
  const awaiting = state.mode === "AWAITING_HITL";
  return {
    state,
    hitlAction: awaiting && state.action.kind !== "email_compose" ? state.action : null,
    composeDraft: awaiting && state.action.kind === "email_compose" ? state.action : null,
    hitl: awaiting,
    confirmListening: awaiting && state.listening,
    sending: state.mode === "EXECUTING",
    listening: state.mode === "LISTENING",
    thinking: state.mode === "THINKING",
    busy: isBusy(state),
    mode: orchestratorMode(state),
  };
}
