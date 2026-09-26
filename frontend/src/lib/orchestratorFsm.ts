import type { PendingAction } from "./types";

/**
 * OrchestratorShell's macro-state. Exactly one of these is ever true — no
 * independent `busy`/`listening`/`sending`/`confirmListening` booleans that
 * could combine into a contradictory reading (e.g. "listening" while
 * "speaking"). `AWAITING_HITL` carries two extra booleans scoped to itself
 * (not top-level flags) because a single HITL panel legitimately has two
 * sub-conditions of its own:
 *   - `listening`: the confirm-mic is open, listening for a spoken yes/no
 *     (or, for an `email_compose` draft with missing fields, dictation of
 *     the missing text).
 *   - `resolving`: a decide()/fill-in network call is in flight for this
 *     same action. Reject and compose-fill-in both keep the panel open
 *     (unlike approve, which moves straight to `EXECUTING` and hides it).
 */
export type JarvisState =
  | { mode: "IDLE"; error?: string }
  | { mode: "LISTENING" }
  | { mode: "THINKING"; message: string; stage?: string }
  | { mode: "SPEAKING"; text: string }
  | { mode: "AWAITING_HITL"; action: PendingAction; listening: boolean; resolving: boolean }
  | { mode: "EXECUTING"; actionId: string };

export type ServerTurn = {
  id: string;
  state: string;
  stage?: string;
  input?: string;
  error?: string;
  pending_action_id?: string | null;
  pending_action?: PendingAction | null;
  pending_status?: string | null;
  output?: {
    speak?: string;
    reply?: string;
    pending?: PendingAction[];
  } | null;
};

export type JarvisEvent =
  | { type: "SEND"; text: string }
  | { type: "LISTEN_START" }
  | { type: "LISTEN_STOP" }
  | { type: "SPEAK_START"; text: string }
  | { type: "SPEAK_END" }
  | { type: "AWAIT_HITL"; action: PendingAction }
  | { type: "HITL_LISTEN_START" }
  | { type: "HITL_LISTEN_STOP" }
  | { type: "DECIDE_APPROVE"; actionId: string }
  | { type: "DECIDE_REJECT"; actionId: string }
  | { type: "RESUME_THINKING" }
  | { type: "RESET" }
  | { type: "SHOW_ERROR"; message: string }
  | { type: "RECONCILE"; turn: ServerTurn | null };

export const INITIAL_JARVIS_STATE: JarvisState = { mode: "IDLE" };

function needsDictatedFill(action: PendingAction): boolean {
  const missing = action.payload?.missing;
  return action.kind === "email_compose" && Array.isArray(missing) && missing.length > 0;
}

function pendingStillOpen(turn: ServerTurn): boolean {
  const status = String(
    turn.pending_status || (turn.pending_action as { status?: string } | undefined)?.status || "pending",
  ).toLowerCase();
  return status === "pending";
}

function stageFromTurn(turn: ServerTurn): string {
  return String(turn.stage || "").trim();
}

/** User-visible failure copy for FAILED / ABANDONED ledger rows (names the stage). */
export function failureLineForTurn(turn: ServerTurn): string {
  const stage = stageFromTurn(turn);
  if (stage) {
    return `The brain dropped that at ${stage}. Retry?`;
  }
  const err = String(turn.error || "");
  const match = err.match(/FAILED\(([^)]+)\)/i);
  const fromErr = match?.[1]?.trim();
  if (fromErr) {
    return `The brain dropped that at ${fromErr}. Retry?`;
  }
  return "The brain dropped that. Retry?";
}

function withoutIdleError(state: JarvisState): JarvisState {
  if (state.mode === "IDLE" && !state.error) return state;
  return { mode: "IDLE" };
}

/** IDLE plus the failure line. Same reference when that line is already showing. */
function idleWithError(state: JarvisState, message: string): JarvisState {
  const text = message.trim() || "The brain dropped that. Retry?";
  if (state.mode === "IDLE" && state.error === text) return state;
  return { mode: "IDLE", error: text };
}

/** Pure ledger snapshot → event (nominal mapping from IDLE; duplicated in backend tests). */
export function hydrate(turn: ServerTurn | null): JarvisEvent {
  if (!turn) return { type: "RESET" };
  const st = String(turn.state || "").toUpperCase();
  if (st === "QUEUED" || st === "RUNNING") {
    const text = String(turn.input || "").trim() || "Working…";
    return { type: "SEND", text };
  }
  if (st === "AWAITING_HITL") {
    const action = turn.pending_action;
    if (action && pendingStillOpen(turn)) {
      return { type: "AWAIT_HITL", action };
    }
    return { type: "RESET" };
  }
  if (st === "EXECUTING") {
    const actionId = String(turn.pending_action_id || turn.pending_action?.id || "").trim();
    if (actionId) {
      return { type: "RECONCILE", turn: { ...turn, state: "EXECUTING", pending_action_id: actionId } };
    }
    return { type: "RESET" };
  }
  if (st === "FAILED" || st === "ABANDONED") {
    return { type: "SHOW_ERROR", message: failureLineForTurn(turn) };
  }
  if (st === "DONE") {
    return { type: "RESET" };
  }
  return { type: "RESET" };
}

function applyHydrateToState(_state: JarvisState, event: JarvisEvent): JarvisState {
  switch (event.type) {
    case "RESET":
      return { mode: "IDLE" };
    case "SHOW_ERROR":
      return idleWithError({ mode: "IDLE" }, event.message);
    case "SEND": {
      const text = event.text.trim();
      if (!text) return { mode: "IDLE" };
      return { mode: "THINKING", message: text };
    }
    case "AWAIT_HITL":
      return { mode: "AWAITING_HITL", action: event.action, listening: false, resolving: false };
    case "RECONCILE": {
      if (!event.turn) return { mode: "IDLE" };
      const execId = String(event.turn.pending_action_id || "").trim();
      if (String(event.turn.state || "").toUpperCase() === "EXECUTING" && execId) {
        return { mode: "EXECUTING", actionId: execId };
      }
      return { mode: "IDLE" };
    }
    default:
      return { mode: "IDLE" };
  }
}

function reconcileLedgerState(state: JarvisState, turn: ServerTurn | null): JarvisState {
  if (!turn) {
    return withoutIdleError(state);
  }

  const st = String(turn.state || "").toUpperCase();
  const stage = stageFromTurn(turn);

  if (st === "AWAITING_HITL") {
    const action = turn.pending_action;
    if (!action || !pendingStillOpen(turn)) {
      return withoutIdleError(state);
    }
    if (
      state.mode === "AWAITING_HITL" &&
      state.action.id === action.id &&
      !state.listening &&
      !state.resolving
    ) {
      return state;
    }
    return { mode: "AWAITING_HITL", action, listening: false, resolving: false };
  }

  if (st === "EXECUTING") {
    const actionId = String(turn.pending_action_id || turn.pending_action?.id || "").trim();
    if (!actionId) {
      return withoutIdleError(state);
    }
    if (state.mode === "EXECUTING" && state.actionId === actionId) return state;
    return { mode: "EXECUTING", actionId };
  }

  if (st === "QUEUED" || st === "RUNNING") {
    const fromTurn = String(turn.input || "").trim();
    const message =
      (state.mode === "THINKING" ? state.message : fromTurn) || fromTurn || "Working…";
    if (state.mode === "THINKING") {
      if (state.message === message && state.stage === stage) return state;
      return { mode: "THINKING", message, stage: stage || state.stage };
    }
    return { mode: "THINKING", message, stage };
  }

  if (st === "FAILED" || st === "ABANDONED") {
    return idleWithError(state, failureLineForTurn(turn));
  }

  if (st === "DONE") {
    return withoutIdleError(state);
  }

  return state;
}

/**
 * Pure transition table. Returns the SAME `state` reference (never a new
 * object) whenever an event is refused, so callers can use `next === state`
 * as a cheap "was this a no-op" guard. See the PR description for the full
 * table this function implements — every (mode, event) pair below has a
 * corresponding row there.
 */
export function transition(state: JarvisState, event: JarvisEvent): JarvisState {
  switch (event.type) {
    case "RECONCILE":
      return reconcileLedgerState(state, event.turn);

    case "RESET":
      return withoutIdleError(state);

    case "SHOW_ERROR":
      return idleWithError(state, event.message);

    case "SEND": {
      const text = event.text.trim();
      if (!text) return state;
      if (state.mode === "THINKING" || state.mode === "EXECUTING") return state; // already busy
      if (state.mode === "AWAITING_HITL") {
        // Only a dictated/typed fill-in for an incomplete compose draft may
        // "send" while a HITL panel is open; every other pending kind must
        // go through Authorize/Reject. The panel stays visible (unlike
        // approve) because the reply is going to update this same draft.
        if (state.resolving || !needsDictatedFill(state.action)) return state;
        return { ...state, listening: false, resolving: true };
      }
      // IDLE | LISTENING | SPEAKING: entering THINKING happens immediately,
      // synchronously, before the backend replies — the HUD must never go
      // blank waiting on the network.
      return { mode: "THINKING", message: text };
    }

    case "LISTEN_START":
      if (state.mode === "IDLE" || state.mode === "LISTENING") return { mode: "LISTENING" };
      // SPEAKING / THINKING / EXECUTING / AWAITING_HITL: refused. This is
      // what makes "mic live while Jarvis is speaking" structurally
      // impossible rather than merely guarded — there is no transition
      // out of SPEAKING that produces a listening-capable state.
      return state;

    case "LISTEN_STOP":
      return state.mode === "LISTENING" ? { mode: "IDLE" } : state;

    case "SPEAK_START":
      // A reply is ready to be voiced. Authoritative: whichever in-flight
      // mode we were in (THINKING, EXECUTING, or a resolving AWAITING_HITL)
      // is superseded, same as the old code's speakToken bump superseding
      // whatever the previous turn was doing.
      return { mode: "SPEAKING", text: event.text };

    case "SPEAK_END":
      // Only leaves SPEAKING; never enters it. A late/stale completion
      // (the voice bridge's late-clip case) that fires after some other
      // event has already moved the mode on is therefore a guaranteed
      // no-op here — it cannot resurrect SPEAKING or anything else.
      return state.mode === "SPEAKING" ? { mode: "IDLE" } : state;

    case "AWAIT_HITL":
      // A reply carried a pending action with nothing to speak — skip
      // SPEAKING entirely and present the HITL panel directly.
      return { mode: "AWAITING_HITL", action: event.action, listening: false, resolving: false };

    case "HITL_LISTEN_START":
      if (state.mode !== "AWAITING_HITL" || state.resolving || state.listening) return state;
      return { ...state, listening: true };

    case "HITL_LISTEN_STOP":
      if (state.mode !== "AWAITING_HITL" || !state.listening) return state;
      return { ...state, listening: false };

    case "DECIDE_APPROVE":
      if (state.mode !== "AWAITING_HITL" || state.resolving || state.action.id !== event.actionId) {
        return state;
      }
      return { mode: "EXECUTING", actionId: event.actionId };

    case "DECIDE_REJECT":
      if (state.mode !== "AWAITING_HITL" || state.resolving || state.action.id !== event.actionId) {
        return state;
      }
      return { ...state, listening: false, resolving: true };

    case "RESUME_THINKING":
      if (state.mode === "EXECUTING") return { mode: "THINKING", message: "Working…" };
      return state;

    default:
      return state;
  }
}

/** Apply hydrate() as if the client started from IDLE (used by tests and tooling). */
export function stateFromHydrate(turn: ServerTurn | null): JarvisState {
  return applyHydrateToState(INITIAL_JARVIS_STATE, hydrate(turn));
}

export function jarvisReducer(state: JarvisState, event: JarvisEvent): JarvisState {
  return transition(state, event);
}

/** Whether a listen request (mic button / spacebar) is currently valid. */
export function listenAllowed(state: JarvisState): boolean {
  if (state.mode === "IDLE" || state.mode === "LISTENING") return true;
  if (state.mode === "AWAITING_HITL") return !state.resolving && needsDictatedFill(state.action);
  return false;
}

/** True while a network round trip is in flight — THINKING, EXECUTING, or a
 * resolving (reject / compose fill-in) AWAITING_HITL. Equivalent to the old
 * `busyRef.current` guard used to block re-entrant sends, decisions, and
 * "start a new discussion" actions. */
export function isBusy(state: JarvisState): boolean {
  return state.mode === "THINKING" || state.mode === "EXECUTING" || (state.mode === "AWAITING_HITL" && state.resolving);
}
