"use client";

import {
  googleConnectSpeakLine,
  googleServicesIncomplete,
  type GoogleConnectStatus,
} from "@/components/orchestrator/ConnectGoogleModal";
import type { RailConversation } from "@/components/orchestrator/ConversationRail";
import type { SuggestedTask } from "@/components/orchestrator/SuggestedTasksPanel";
import {
  initialWorkspaceFromBootstrap,
  isHudWorkspace,
  workspaceFromCategory,
  type HudWorkspace,
} from "@/components/orchestrator/hudWorkspace";
import { postSubstrate } from "@/core/root/substrateBridge";
import { api, apiBase } from "@/lib/api";
import { readHermesEventStream, takeSentences, type HermesRunEvent } from "@/lib/hermesRun";
import { liveLog } from "@/lib/liveLog";
import {
  agentCode,
  agentForPending,
  agentIdFromTarget,
  agentsFromApi,
  formatClock,
  type AgentNode,
} from "@/lib/orchestrator";
import { failureLineForTurn, isBusy, listenAllowed, type ServerTurn } from "@/lib/orchestratorFsm";
import type { ChatResponse, Conversation, PendingAction, Preferences } from "@/lib/types";
import {
  canListen,
  classifyDecision,
  silence,
  speakText,
  startListening,
  stopListening,
  whenSpeechIdle,
} from "@/lib/voice";
import type { TurnEventPayload } from "@/components/orchestrator/TurnStageLine";
import {
  AMBIENT_SESSION,
  EMPTY_SCENE,
  IDLE_VOICE,
  MAX_OPEN_CONVERSATIONS,
  getDesk,
  sceneHasBoardContent,
  setDesk,
} from "@/core/stores/deskStore";
import { setModalProbe } from "@/core/scroll/director";
import { getSection, hydrateWorkspace, requestSection, setWorkspace } from "@/core/stores/sectionStore";
import { firstUnparked, getParkedIds, hydrateParked, markParked, unmarkParked } from "@/core/stores/taskQueueStore";
import { dispatchTurn, getTurn, onTurnEffect, setTurnLogSession } from "@/core/stores/turnStore";
import { runAutosave } from "./autosave";

const FOCUS_STORAGE_KEY = "jarvis.activeConversationId";

/** Imperative refs from the old shell. Module-level: one desk per document. */
const ctl = {
  speakGen: 0,
  liveRun: "",
  runAbort: null as AbortController | null,
  sentenceBuf: "",
  unspoken: "",
  sessionSurfaceGen: 0,
  decideInFlight: false,
  voiceEnabled: true,
  composeFields: { to: "", subject: "", body: "" },
  googlePromptSpoken: false,
  bootGen: 0,
};

function session(): string {
  return getDesk().activeSession;
}

function setSession(sessionId: string) {
  setDesk({ activeSession: sessionId });
  setTurnLogSession(sessionId);
}

function logHitlShown(action: PendingAction) {
  liveLog("hitl", { phase: "shown", action_kind: action.kind, action_id: action.id }, { sessionId: session() });
}

function mapDeskItems(rows: Conversation[], activeConversationId: string | null): RailConversation[] {
  return rows
    .filter((row) => !row.minimized)
    .slice(0, MAX_OPEN_CONVERSATIONS)
    .map((row) => ({
      id: row.id,
      sessionId: row.session_id,
      title: row.title || row.category || "Note",
      kindLabel:
        row.kind_label || (row.category === "workflow" ? "Job" : row.category === "drawing" ? "Drawing" : "Note"),
      time: row.updated_at
        ? new Date(row.updated_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
        : undefined,
      preview: row.speak || row.turns?.slice(-1)[0]?.content || "",
      active: activeConversationId === row.id,
      waiting: Boolean(row.waiting || (row.pending && row.pending.length)),
    }));
}

/* ── Section routing ─────────────────────────────────────────────────── */

/** Automatic move to a workspace's section (pin-gated). Goes through the FSM's ROUTE_HINT. */
export function routeTo(workspace: HudWorkspace, reason: string) {
  const from = getSection().active;
  liveLog("workspace", { from, to: workspace, pinned: getSection().pinned, reason }, { sessionId: session() });
  dispatchTurn({ type: "ROUTE_HINT", section: workspace, reason, from });
}

/** Server `ui` hint (X4). Engineering only yields to an explicit request. */
export function applyServerHint(ui: { section: string; reason: string } | null | undefined) {
  if (!ui || !isHudWorkspace(ui.section)) return;
  const from = getSection().active;
  if (from === "engineering" && ui.reason !== "explicit") return;
  routeTo(ui.section, `server-${ui.reason}`);
}

/** A user click on the section nav or switcher. Always runs. */
export function goToSection(section: string, reason = "nav") {
  const from = getSection().active;
  if (from === "engineering" && section !== "engineering") void runAutosave("leave-engineering");
  requestSection(section, { source: "user", reason });
}

function applyFocusWorkspace(category: string) {
  const cat = (category || "").toLowerCase();
  if (cat === "workflow" || cat === "drawing") routeTo("engineering", "auto-focus");
  else if (cat === "discussion") routeTo("casual", "auto-focus");
}

/* ── Activity, agents, voice line ────────────────────────────────────── */

export function pushLog(agent: string, message: string) {
  setDesk((s) => ({
    activity: [
      { id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, time: formatClock(), agent, message },
      ...s.activity,
    ].slice(0, 8),
  }));
}

function setAgentStates(ids: string[], state: AgentNode["state"]) {
  setDesk((s) => ({
    agents: s.agents.map((agent) => ({
      ...agent,
      state: ids.includes(agent.id) ? state : state === "active" || state === "waiting" ? "" : agent.state,
    })),
  }));
}

function clearAgents() {
  setDesk((s) => ({ agents: s.agents.map((agent) => ({ ...agent, state: "" as const })) }));
}

export function showVoice(text: string) {
  const next = (text || "").trim() || IDLE_VOICE;
  setDesk({ voiceVisible: false });
  window.setTimeout(() => setDesk({ voice: next, voiceVisible: true }), 180);
}

/** Compose modal owns the draft — clear the centre line so it does not compete. */
function clearVoice() {
  setDesk({ voiceVisible: false, voice: "" });
}

function speakLine(line: string) {
  showVoice(line);
  ctl.speakGen += 1;
  const gen = ctl.speakGen;
  const started = dispatchTurn({ type: "SPEAK_START", text: line });
  if (!started || !ctl.voiceEnabled) return;
  void speakText(line).finally(() => {
    if (gen !== ctl.speakGen) return;
    dispatchTurn({ type: "SPEAK_END" });
  });
}

export function announceGoogleConnect(status: GoogleConnectStatus) {
  const line = googleConnectSpeakLine(status);
  if (line) speakLine(line);
}

/* ── Desk, sessions, focus ───────────────────────────────────────────── */

export async function refreshDesk(focusId: string | null = getDesk().activeConversationId) {
  const payload = await api.conversations(true).catch(() => ({ items: [] as Conversation[] }));
  setDesk({ desk: mapDeskItems(payload.items || [], focusId) });
  return payload.items || [];
}

async function loadSessionSurface(sessionId: string, opts?: { announce?: boolean }) {
  const generation = ++ctl.sessionSurfaceGen;
  void api.hermesWarm(sessionId).catch(() => null);
  const [waiting, sess] = await Promise.all([
    api.pending(sessionId).catch(() => ({ items: [] as PendingAction[] })),
    api.session(sessionId).catch(() => null),
  ]);
  if (generation !== ctl.sessionSurfaceGen) return;
  const first = firstUnparked(waiting.items || []);
  // Restoring a session never auto-opens the confirm mic — it is a snapshot, not a fresh reply.
  dispatchTurn(first ? { type: "AWAIT_HITL", action: first } : { type: "RESET" });
  const composeOpen = first?.kind === "email_compose";
  if (composeOpen) {
    clearVoice();
  } else if (opts?.announce !== false && sess?.speak) {
    showVoice(sess.speak);
  } else if (opts?.announce !== false && !first) {
    const cached = await api.briefingCache().catch(() => null);
    if (generation !== ctl.sessionSurfaceGen) return;
    if (ctl.liveRun || isBusy(getTurn())) return;
    if (cached?.cached && cached.speak) showVoice(cached.speak);
    else showVoice(IDLE_VOICE);
  }
  if (first) {
    const agentId = agentForPending(first);
    setAgentStates([agentId], "waiting");
    pushLog(agentCode(agentId), "Pending authorization restored.");
  } else {
    clearAgents();
  }
}

export async function reconcileOpenTurn() {
  try {
    const sessionId = session();
    const resp = await fetch(`${apiBase()}/api/turns/open?session_id=${encodeURIComponent(sessionId)}`);
    if (!resp.ok) return;
    const data = (await resp.json()) as { enabled?: boolean; turns?: ServerTurn[] };
    if (!data.enabled) return;
    const turn = (Array.isArray(data.turns) ? data.turns : [])[0] ?? null;
    dispatchTurn({ type: "RECONCILE", turn, parkedIds: getParkedIds() });
    if (!turn) {
      setDesk({ ledgerTurnId: null });
      await loadSessionSurface(sessionId, { announce: false });
      return;
    }
    const st = String(turn.state || "").toUpperCase();
    if (st === "FAILED" || st === "ABANDONED") {
      setDesk({ ledgerTurnId: null });
      clearAgents();
      const line = failureLineForTurn(turn);
      dispatchTurn({ type: "SHOW_ERROR", message: line });
      setDesk({ error: line });
      showVoice(line);
      return;
    }
    if (st === "QUEUED" || st === "RUNNING") {
      setDesk({ ledgerTurnId: turn.id });
      showVoice("Orchestrating…");
      return;
    }
    if (st === "EXECUTING") {
      setDesk({ ledgerTurnId: turn.id });
      showVoice("Working…");
      return;
    }
    if (st === "AWAITING_HITL" && turn.pending_action && !getParkedIds().includes(turn.pending_action.id)) {
      setDesk({ ledgerTurnId: null });
      const action = turn.pending_action;
      if (action.kind === "email_compose") clearVoice();
      const agentId = agentForPending(action);
      setAgentStates([agentId], "waiting");
      pushLog(agentCode(agentId), "Pending authorization restored.");
    }
  } catch {
    /* a failed fetch leaves the current screen alone */
  }
}

function rememberFocus(id: string | null) {
  try {
    if (id) localStorage.setItem(FOCUS_STORAGE_KEY, id);
    else localStorage.removeItem(FOCUS_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export async function focusAmbient() {
  setSession(AMBIENT_SESSION);
  setDesk({ activeConversationId: null, focusTitle: "Everyday note", conversationFocus: {} });
  rememberFocus(null);
  await refreshDesk(null);
  await loadSessionSurface(AMBIENT_SESSION, { announce: true });
  showVoice("Back on the everyday note.");
}

export async function focusConversation(row: Conversation, opts?: { announce?: boolean }) {
  applyFocusWorkspace(row.category);
  setSession(row.session_id || AMBIENT_SESSION);
  setDesk({
    activeConversationId: row.id,
    focusTitle: row.title || row.kind_label || "Note",
    conversationFocus: row.focus || {},
  });
  rememberFocus(row.id);
  void api.patchConversation(row.id, { minimized: false }).catch(() => null);
  await refreshDesk(row.id);
  await loadSessionSurface(session(), { announce: false });
  if (opts?.announce !== false) showVoice(row.speak || IDLE_VOICE);
}

export async function selectConversation(id: string) {
  const rows = await refreshDesk();
  const row = rows.find((item) => item.id === id);
  if (row) await focusConversation(row, { announce: true });
}

async function applyUiAction(uiAction: Record<string, unknown> | null | undefined) {
  const action = String(uiAction?.action || "");
  if (!action || action === "noop") {
    if (action === "noop") void refreshDesk();
    return;
  }
  if (action === "hide_dock") {
    setDesk({ dockHidden: true });
    return;
  }
  if (action === "show_dock") {
    setDesk({ dockHidden: false });
    return;
  }
  const conversationId = typeof uiAction?.conversation_id === "string" ? uiAction.conversation_id : "";
  const activeId = getDesk().activeConversationId;
  const rows = await refreshDesk(activeId);
  if (action === "focus_drawing" && conversationId) {
    const row = rows.find((item) => item.id === conversationId);
    if (row) {
      setSession(row.session_id || AMBIENT_SESSION);
      setDesk({ activeConversationId: row.id, focusTitle: row.title || "Drawing", conversationFocus: row.focus || {} });
    }
    return;
  }
  if (action === "minimize") {
    if (activeId && activeId === conversationId) await focusAmbient();
    return;
  }
  if (action === "expand" && conversationId) {
    setDesk({ dockHidden: false });
    const row = rows.find((item) => item.id === conversationId);
    if (row) await focusConversation(row, { announce: false });
  }
}

/* ── Replies and HITL ────────────────────────────────────────────────── */

function presentHitl(action: PendingAction) {
  const settled = dispatchTurn({ type: "AWAIT_HITL", action });
  if (settled) {
    logHitlShown(action);
    startConfirmListen(action);
  }
}

export function applyResponse(
  result: ChatResponse,
  opts?: { fromConfirm?: boolean; approved?: boolean; alreadySpoken?: boolean },
) {
  void applyUiAction(result.ui_action);
  applyServerHint(result.ui);
  const view = result.drawing_chat;
  if (view && typeof view === "object") {
    if (view.open === false) setDesk({ drawingChat: null });
    else if (view.filename || view.local_name) {
      setDesk({ drawingChat: view });
      if (view.session_id) setSession(view.session_id);
      if (view.conversation_id) setDesk({ activeConversationId: view.conversation_id });
    }
  }

  const nextAction = firstUnparked(result.pending || []);
  const display = (result.reply || result.speak || "").trim() || IDLE_VOICE;
  const tts = (result.speak || result.reply || "").trim();
  const nextScene = sceneHasBoardContent(result.scene) ? result.scene! : EMPTY_SCENE;
  const boardOwnsHud = sceneHasBoardContent(nextScene) || nextAction?.kind === "email_compose";
  if (boardOwnsHud && getSection().workspace !== "engineering") {
    setDesk({ voiceVisible: false, voice: "On the board" });
  } else {
    showVoice(display);
  }
  setDesk({ scene: nextScene });

  if (result.activity?.length) {
    setDesk((s) => ({
      activity: [
        ...result.activity!.map((item, index) => ({
          id: item.id || `act-${Date.now()}-${index}`,
          time: item.time || formatClock(),
          agent: item.agent || "SYS",
          message: item.message || "",
        })),
        ...s.activity,
      ].slice(0, 8),
    }));
  }

  if (result.agents?.length) {
    setDesk({ agents: agentsFromApi(result.agents) });
  } else if (result.target_agent) {
    const agentId = agentIdFromTarget(result.target_agent);
    if (agentId) {
      clearAgents();
      setAgentStates([agentId], nextAction ? "waiting" : "active");
      if (!nextAction) window.setTimeout(clearAgents, 2400);
    }
  } else if (nextAction) {
    const agentId = agentForPending(nextAction);
    clearAgents();
    setAgentStates([agentId], "waiting");
    pushLog(agentCode(agentId), "Awaiting human clearance…");
  } else if (opts?.fromConfirm) {
    if (opts.approved) {
      setAgentStates(["ops"], "active");
      pushLog("OPS.04", "Executing authorized action…");
      window.setTimeout(clearAgents, 2400);
    } else {
      clearAgents();
      pushLog("SYS", "Operator rejected sequence.");
    }
  }

  if (sceneHasBoardContent(result.scene) && result.scene?.title) pushLog("SYS", result.scene.title);

  ctl.speakGen += 1;
  const gen = ctl.speakGen;

  const settle = () => {
    if (gen !== ctl.speakGen) return;
    if (nextAction && nextAction.kind !== "hermes_approval") {
      presentHitl(nextAction);
      return;
    }
    const mode = getTurn().mode;
    if (mode === "THINKING" || mode === "SPEAKING") dispatchTurn({ type: "RESET" });
  };

  if (opts?.alreadySpoken) {
    whenSpeechIdle(settle);
    return;
  }

  if (ctl.voiceEnabled && tts) {
    dispatchTurn({ type: "SPEAK_START", text: tts });
    void speakText(tts).finally(() => {
      if (gen !== ctl.speakGen) return;
      const settled = dispatchTurn({ type: "SPEAK_END" });
      if (settled === null) return;
      if (nextAction && nextAction.kind !== "hermes_approval") presentHitl(nextAction);
    });
    return;
  }
  if (nextAction) presentHitl(nextAction);
  else dispatchTurn({ type: "RESET" });
}

/** Auto-opens the confirm mic right after a HITL panel is freshly presented. */
export function startConfirmListen(action: PendingAction) {
  if (!canListen()) return;
  const missing = action.payload?.missing;
  const needsFill = action.kind === "email_compose" && Array.isArray(missing) && missing.length > 0;
  stopListening();
  if (!dispatchTurn({ type: "HITL_LISTEN_START" })) return;
  const logStop = () =>
    liveLog("hitl", { phase: "listen-stop", action_kind: action.kind, action_id: action.id }, { sessionId: session() });
  liveLog("hitl", { phase: "listen-start", action_kind: action.kind, action_id: action.id }, { sessionId: session() });
  void startListening({
    onFinal: (text) => {
      const cur = getTurn();
      if (cur.mode !== "AWAITING_HITL" || cur.action.id !== action.id) return;
      const decision = classifyDecision(text);
      const words = text.trim().split(/\s+/).filter(Boolean).length;
      // Short authorize/reject phrases always win; otherwise body dictation goes to chat.
      if (decision && words <= 5) {
        dispatchTurn({ type: "HITL_LISTEN_STOP" });
        void decide(action.id, decision === "yes");
        return;
      }
      if (needsFill) {
        dispatchTurn({ type: "HITL_LISTEN_STOP" });
        void send(text);
      }
    },
    onEnd: () => {
      dispatchTurn({ type: "HITL_LISTEN_STOP" });
      logStop();
    },
    onError: () => {
      dispatchTurn({ type: "HITL_LISTEN_STOP" });
      logStop();
    },
  });
}

export function setComposeFields(fields: { to: string; subject: string; body: string }) {
  ctl.composeFields = fields;
}

export async function decide(id: string, approved: boolean, fields?: { to: string; subject: string; body: string }) {
  const current = getTurn();
  if (current.mode !== "AWAITING_HITL" || current.action.id !== id || current.resolving) return;
  const action = current.action;
  stopListening();
  silence();
  const next = dispatchTurn(approved ? { type: "DECIDE_APPROVE", actionId: id } : { type: "DECIDE_REJECT", actionId: id });
  if (!next) return;
  unmarkParked(id);
  liveLog(
    "hitl",
    { phase: approved ? "authorize" : "reject", action_kind: action.kind, action_id: id },
    { sessionId: session() },
  );

  if (action.kind === "hermes_approval") {
    const runId = String(action.payload?.run_id || ctl.liveRun || "");
    const requestId = String(action.payload?.request_id || "");
    try {
      if (approved) {
        await api.approveHermesRun(runId, "once", requestId);
        dispatchTurn({ type: "RESUME_THINKING" });
      } else {
        await api.stopHermesRun(runId);
        silence();
        dispatchTurn({ type: "RESET" });
        showVoice(IDLE_VOICE);
      }
    } catch (err) {
      setDesk({ error: err instanceof Error ? err.message : "Approval failed" });
      showVoice("That did not go through. Awaiting instruction.");
      dispatchTurn({ type: "AWAIT_HITL", action });
    }
    return;
  }

  const syncFields = fields || (action.kind === "email_compose" ? ctl.composeFields : undefined);
  if (approved) {
    showVoice(
      action.kind === "email_compose" || action.kind === "email_send" || action.kind === "quote_send"
        ? "Sending…"
        : "Working…",
    );
    setAgentStates(["ops"], "active");
    pushLog("OPS.04", "Executing authorized action…");
  }
  try {
    if (approved && syncFields && action.kind === "email_compose") {
      await api.updatePending(id, syncFields, session());
    }
    const result = await api.confirm(id, approved, session());
    applyResponse(result, { fromConfirm: true, approved });
    void refreshDesk();
  } catch (err) {
    // Restore pending from the server so the HUD never strands without Authorize.
    try {
      const waiting = await api.pending(session());
      const restored = firstUnparked(waiting.items || []);
      dispatchTurn(restored ? { type: "AWAIT_HITL", action: restored } : { type: "RESET" });
    } catch {
      dispatchTurn({ type: "RESET" });
    }
    const msg = err instanceof Error ? err.message : "Confirm failed";
    setDesk({ error: msg });
    liveLog("error", { message: msg }, { sessionId: session() });
    pushLog("SYS", "Confirm failed.");
    showVoice("That did not go through. Awaiting instruction.");
  }
}

/** Later: park the open approval in the task dock. Chat and mic work again. */
export function parkHitl(): PendingAction | null {
  const cur = getTurn();
  if (cur.mode !== "AWAITING_HITL" || cur.resolving) return null;
  const action = cur.action;
  stopListening();
  if (!dispatchTurn({ type: "HITL_PARK", actionId: action.id })) return null;
  markParked(action.id);
  liveLog("hitl", { phase: "park", action_kind: action.kind, action_id: action.id }, { sessionId: session() });
  showVoice(IDLE_VOICE);
  return action;
}

/** Reopen a parked approval as the full Authorize / Reject modal. */
export function resumeHitl(action: PendingAction): boolean {
  if (!dispatchTurn({ type: "HITL_RESUME", action })) return false;
  unmarkParked(action.id);
  liveLog("hitl", { phase: "resume", action_kind: action.kind, action_id: action.id }, { sessionId: session() });
  return true;
}

/* ── Sending ─────────────────────────────────────────────────────────── */

export async function send(message: string) {
  const text = message.trim();
  if (!text) return;
  const current = getTurn();

  // A short "yes"/"no" while a HITL panel is open resolves it instead of chatting.
  const decision = current.mode === "AWAITING_HITL" ? classifyDecision(text) : null;
  const words = text.split(/\s+/).filter(Boolean).length;
  if (decision && current.mode === "AWAITING_HITL" && words <= 5) {
    if (ctl.decideInFlight) return;
    ctl.decideInFlight = true;
    try {
      await decide(current.action.id, decision === "yes");
    } finally {
      ctl.decideInFlight = false;
    }
    setDesk({ compose: "" });
    return;
  }

  const workspace = getSection().workspace;
  liveLog(
    "send",
    { text: text.length > 500 ? `${text.slice(0, 500)}…` : text, workspace },
    { sessionId: session() },
  );

  if (!dispatchTurn({ type: "SEND", text })) return;

  setDesk({ compose: "", error: "", runStatus: "" });
  stopListening();
  pushLog("SYS", text.length > 72 ? `${text.slice(0, 72)}…` : text);
  showVoice("Orchestrating…");

  const abort = new AbortController();
  ctl.runAbort = abort;
  ctl.liveRun = "";
  ctl.sentenceBuf = "";
  ctl.unspoken = "";
  try {
    const started = await api.startHermesRun(text, session(), getSection().active);
    if (abort.signal.aborted) return;
    ctl.liveRun = started.run_id;
    applyServerHint(started.ui);
    const stream = await api.hermesRunEvents(started.run_id, abort.signal);
    if (!stream.ok || !stream.body) throw new Error(`Run stream failed (${stream.status})`);
    await readHermesEventStream(stream, (event: HermesRunEvent) => {
      if (abort.signal.aborted) return;
      const name = String(event.event || "");
      if (name === "tool.started" || name === "tool.completed") {
        const line = String(event.message || "working");
        if (name === "tool.started") setDesk({ runStatus: line });
        setDesk((s) => ({
          activity: [
            { id: `tool-${Date.now()}-${s.activity.length}`, time: formatClock(), agent: "SYS", message: line },
            ...s.activity,
          ].slice(0, 8),
        }));
        return;
      }
      if (name === "message.delta") {
        const delta = String(event.delta || "");
        ctl.sentenceBuf += delta;
        showVoice(ctl.sentenceBuf);
        const taken = takeSentences(ctl.unspoken + delta);
        ctl.unspoken = taken.rest;
        if (ctl.voiceEnabled) for (const sentence of taken.ready) void speakText(sentence);
        return;
      }
      if (name === "approval.request" && event.pending?.id) {
        dispatchTurn({ type: "AWAIT_HITL", action: event.pending });
        logHitlShown(event.pending);
        return;
      }
      if (name === "jarvis.done" && event.response) {
        setDesk({ runStatus: "" });
        const streamed = ctl.sentenceBuf;
        const rest = ctl.unspoken.trim();
        ctl.unspoken = "";
        ctl.sentenceBuf = "";
        let spoke = Boolean(streamed.trim());
        if (ctl.voiceEnabled && rest) {
          void speakText(rest);
          spoke = true;
        } else if (ctl.voiceEnabled && !streamed.trim()) {
          const finalText = String(event.response.speak || event.response.reply || "").trim();
          if (finalText) {
            void speakText(finalText);
            spoke = true;
          }
        }
        setDesk({ ledgerTurnId: null });
        applyResponse(event.response, { alreadySpoken: spoke });
        void refreshDesk();
        return;
      }
      if (name === "run.failed") {
        setDesk({ runStatus: "", error: String(event.error || "Run failed") });
        showVoice("Connection fault. Awaiting instruction.");
        pushLog("SYS", "Request failed.");
        dispatchTurn({ type: "RESET" });
      }
    });
  } catch (err) {
    if (abort.signal.aborted) return;
    clearAgents();
    const msg = err instanceof Error ? err.message : "Request failed";
    setDesk({ runStatus: "", error: msg, ledgerTurnId: null });
    liveLog("error", { message: msg }, { sessionId: session() });
    showVoice("Connection fault. Awaiting instruction.");
    pushLog("SYS", "Request failed.");
    dispatchTurn({ type: "RESET" });
  }
}

export function onLedgerTurnComplete(output: ChatResponse) {
  setDesk({ ledgerTurnId: null });
  applyResponse(output);
  void refreshDesk();
}

export function onLedgerTurnFailed(info: { error?: string; stage?: string; state?: string }) {
  const line = failureLineForTurn({
    id: "turn",
    state: info.state === "ABANDONED" ? "ABANDONED" : "FAILED",
    stage: info.stage,
    error: info.error,
  });
  dispatchTurn({ type: "SHOW_ERROR", message: line });
  setDesk({ ledgerTurnId: null, error: line });
  clearAgents();
  showVoice(line);
  pushLog("SYS", "Turn failed.");
}

export function onLedgerReconcile(turnId: string, payload: TurnEventPayload) {
  const st = String(payload.state || "").toUpperCase();
  if (!st || st === "DONE" || st === "FAILED" || st === "ABANDONED") return;
  if (st === "AWAITING_HITL" || st === "EXECUTING") {
    void reconcileOpenTurn();
    return;
  }
  dispatchTurn({
    type: "RECONCILE",
    turn: { id: turnId, state: st, stage: payload.stage, error: payload.error },
    parkedIds: getParkedIds(),
  });
}

export async function cancelRun() {
  const runId = ctl.liveRun;
  ctl.runAbort?.abort();
  silence();
  ctl.liveRun = "";
  if (runId) {
    try {
      await api.stopHermesRun(runId);
    } catch {
      /* the run may already have finished */
    }
  }
  clearAgents();
  setDesk({ runStatus: "" });
  dispatchTurn({ type: "RESET" });
  showVoice(IDLE_VOICE);
}

export async function extractDocument(file: File) {
  try {
    const result = await api.extractText(file);
    const text = result.ok ? result.text || "" : result.message || "Could not read that file.";
    setDesk({ extractCard: { title: file.name || "Document", text } });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Could not read that file.";
    setDesk({ extractCard: { title: file.name || "Document", text: msg } });
  }
}

export async function startMic() {
  if (!canListen()) return;
  const current = getTurn();
  if (current.mode === "AWAITING_HITL") {
    // Compose fill-in reuses the confirm mic instead of opening a second recognizer.
    if (!listenAllowed(current)) return;
    startConfirmListen(current.action);
    return;
  }
  if (!dispatchTurn({ type: "LISTEN_START" })) return;
  stopListening();
  try {
    await startListening({
      onPartial: (text) => setDesk({ compose: text }),
      onFinal: (text) => {
        dispatchTurn({ type: "LISTEN_STOP" });
        setDesk({ compose: "" });
        void send(text);
      },
      onEnd: () => dispatchTurn({ type: "LISTEN_STOP" }),
      onError: (message) => {
        dispatchTurn({ type: "LISTEN_STOP" });
        setDesk({ error: message });
      },
    });
  } catch (err) {
    dispatchTurn({ type: "LISTEN_STOP" });
    setDesk({ error: err instanceof Error ? err.message : "Microphone unavailable" });
  }
}

export async function startNewDiscussion() {
  if (isBusy(getTurn())) return;
  try {
    routeTo("casual", "auto-focus");
    if (getDesk().desk.length >= MAX_OPEN_CONVERSATIONS) {
      pushLog("SYS", `Max ${MAX_OPEN_CONVERSATIONS} open notes — oldest will be parked.`);
    }
    const row = await api.startDiscussion("");
    await focusConversation(row, { announce: true });
    pushLog("SYS", `Opened note: ${row.title}`);
    void refreshDesk(row.id);
  } catch (err) {
    setDesk({ error: err instanceof Error ? err.message : "Could not open note" });
  }
}

async function openWorkflowFromTask(task: SuggestedTask) {
  if (isBusy(getTurn())) return;
  try {
    routeTo("engineering", "auto-focus");
    const resumeKey = `task:${task.id}`;
    const title = task.kind === "rfq" ? `RFQ · ${task.title}`.slice(0, 80) : task.title.slice(0, 80) || "Job";
    const row = await api.startOrResumeWorkflow(
      title,
      {
        task_id: task.id,
        source_id: task.source_id || "",
        kind: task.kind,
        resume_key: resumeKey,
        meta: task.meta || {},
      },
      resumeKey,
    );
    await focusConversation(row, { announce: true });
    pushLog("SYS", `Job focus: ${row.title}`);
    void send(
      `Continue the engineering review and quote for this job. Task: ${task.title}. Detail: ${task.detail || "none"}`,
    );
  } catch (err) {
    setDesk({ error: err instanceof Error ? err.message : "Could not open job" });
  }
}

export function taskDismiss(id: string) {
  void api.setSuggestedTaskStatus(id, "dismissed").catch(() => null);
  setDesk((s) => ({ suggested: s.suggested.filter((t) => t.id !== id) }));
}

export function taskAction(task: SuggestedTask, actionId: string) {
  if (task.kind === "rfq" && actionId === "engineering") {
    void openWorkflowFromTask(task);
  } else if (actionId === "calendar" || actionId === "meeting") {
    void send(`Create a calendar event for: ${task.title}`);
  } else if (actionId === "chat" || actionId === "review") {
    void (async () => {
      routeTo("casual", "task");
      const row = await api.startDiscussion(task.title.slice(0, 80));
      await focusConversation(row, { announce: true });
      void send(`Let's discuss: ${task.title}. ${task.detail || ""}`);
    })();
  } else {
    void send(`${actionId} for suggested task: ${task.title}`);
  }
}

export async function dropDrawing(file: File) {
  setDesk({ error: "" });
  showVoice("Looking at the drawing…");
  try {
    const result = await api.dropDrawing(file);
    applyResponse(result);
    void refreshDesk(result.drawing_chat?.conversation_id || getDesk().activeConversationId);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Could not open that drawing";
    setDesk({ error: msg });
    showVoice(msg);
  }
}

export function closeDrawing() {
  const chat = getDesk().drawingChat;
  const sessionId = chat?.session_id || session();
  setDesk({ drawingChat: null });
  speakLine("Drawing closed.");
  void api.closeDrawing(sessionId).catch(() => null);
}

export async function savePreferences(next: Partial<Preferences>) {
  const saved = await api.updatePreferences(next);
  setDesk({ prefs: saved });
  ctl.voiceEnabled = saved.voice_enabled !== false;
}

export function maybeAnnounceGoogle() {
  const { googleConnectOpen, googleStatus } = getDesk();
  if (!googleConnectOpen || !googleStatus || !googleServicesIncomplete(googleStatus)) return;
  if (ctl.googlePromptSpoken) return;
  ctl.googlePromptSpoken = true;
  announceGoogleConnect(googleStatus);
}

/* ── Boot ────────────────────────────────────────────────────────────── */

/** Screenshot / verify override: ?lens=monitor|casual|engineering */
export function workspaceFromLensQuery(): HudWorkspace | null {
  if (typeof window === "undefined") return null;
  try {
    const v = new URLSearchParams(window.location.search).get("lens");
    return isHudWorkspace(v) ? v : null;
  } catch {
    return null;
  }
}

/** Target section for boot / landing exit (X1): pinned → saved; else restored category; else Monitor. */
export function bootTargetSection(restoredCategory?: string | null): HudWorkspace {
  const lens = workspaceFromLensQuery();
  if (lens) return lens;
  const { workspace, pinned } = getSection();
  return initialWorkspaceFromBootstrap({ restoredCategory, pinned, stored: workspace });
}

function normalizeTasks(raw: unknown[]): SuggestedTask[] {
  return raw
    .map((r) => {
      const t = r as SuggestedTask;
      return {
        ...t,
        actions: Array.isArray(t.actions) ? t.actions : [],
        detail: typeof t.detail === "string" ? t.detail : "",
        title: typeof t.title === "string" ? t.title : "Task",
        kind: typeof t.kind === "string" ? t.kind : "task",
        id: typeof t.id === "string" ? t.id : "",
      };
    })
    .filter((t) => t.id);
}

/** Register effect runners and load the desk. Returns cleanup (StrictMode-safe). */
export function initDesk(): () => void {
  setModalProbe(() => {
    const d = getDesk();
    return getTurn().mode === "AWAITING_HITL" || d.prefsOpen || d.googleConnectOpen;
  });
  const gen = ++ctl.bootGen;
  const offMode = onTurnEffect("orb-mode", (e) => postSubstrate({ type: "mode", mode: e.mode }));
  const offScroll = onTurnEffect("scroll", (e) => {
    requestSection(e.section, { source: "auto", reason: e.reason });
  });
  const offAutosave = onTurnEffect("autosave", (e) => void runAutosave(e.reason));
  hydrateParked();
  hydrateWorkspace();
  setDesk({ voiceVisible: true });

  void (async () => {
    try {
      let storedId: string | null = null;
      try {
        storedId = localStorage.getItem(FOCUS_STORAGE_KEY);
      } catch {
        storedId = null;
      }
      const [preferences, deskRows, tasks, google] = await Promise.all([
        api.preferences().catch(() => null),
        api.conversations(true).catch(() => ({ items: [] as Conversation[] })),
        api.suggestedTasks(false, AMBIENT_SESSION).catch(() => ({ items: [], weather: undefined })),
        api.googleStatus().catch(() => null),
        api.hermesWarm(AMBIENT_SESSION).catch(() => null),
      ]);
      if (gen !== ctl.bootGen) return;
      if (preferences) {
        setDesk({ prefs: preferences });
        ctl.voiceEnabled = preferences.voice_enabled !== false;
      }
      const params = new URLSearchParams(window.location.search);
      const oauthReturn = params.get("gmail") === "1";
      if (oauthReturn) {
        setDesk({ prefsOpen: true });
        params.delete("gmail");
        window.history.replaceState({}, "", `${window.location.pathname}${params.toString() ? `?${params}` : ""}`);
      }
      if (google) {
        setDesk({ googleStatus: google });
        if (googleServicesIncomplete(google) && !oauthReturn) setDesk({ googleConnectOpen: true });
      }
      const skipAmbientAnnounce = Boolean(google && googleServicesIncomplete(google) && !oauthReturn);
      const rows = deskRows.items || [];
      const restored = storedId ? rows.find((row) => row.id === storedId) : null;
      const target = bootTargetSection(restored?.category);
      setWorkspace(target, "boot");
      requestSection(target, { source: "user", reason: "boot", immediate: true });
      liveLog("hud_boot", { workspace: target, pinned: getSection().pinned, session: session() }, { sessionId: session() });
      setDesk({ desk: mapDeskItems(rows, restored?.id || null) });
      if (restored) {
        setSession(restored.session_id || AMBIENT_SESSION);
        setDesk({
          activeConversationId: restored.id,
          focusTitle: restored.title || "Note",
          conversationFocus: restored.focus || {},
        });
        void api.patchConversation(restored.id, { minimized: false }).catch(() => null);
        await loadSessionSurface(session(), { announce: !skipAmbientAnnounce });
      } else {
        setSession(AMBIENT_SESSION);
        setDesk({ activeConversationId: null, focusTitle: "Everyday note" });
        await loadSessionSurface(AMBIENT_SESSION, { announce: !skipAmbientAnnounce });
      }
      if (gen !== ctl.bootGen) return;
      setDesk({ suggested: normalizeTasks(tasks.items || []) });
      setDesk({ weatherLine: (tasks.weather as { speak?: string } | undefined)?.speak || "" });
      void api
        .officeRefresh(AMBIENT_SESSION)
        .then((payload) => {
          if (gen !== ctl.bootGen) return;
          const refreshed = normalizeTasks((payload.tasks as unknown[]) || []);
          if (refreshed.length) setDesk({ suggested: refreshed });
          const w = (payload.weather as { speak?: string } | undefined)?.speak;
          if (w) setDesk({ weatherLine: w });
        })
        .catch(() => null);
      await reconcileOpenTurn();
    } catch {
      /* an offline bootstrap is fine for the UI shell */
    } finally {
      if (gen === ctl.bootGen) setDesk({ booted: true });
    }
  })();

  return () => {
    offMode();
    offScroll();
    offAutosave();
    stopListening();
    silence();
  };
}

/** Global keys: Y/N on an open approval, Space to listen, Escape to stop. */
export function handleDeskKey(event: KeyboardEvent) {
  const typing = event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement;
  const current = getTurn();
  if (current.mode === "AWAITING_HITL" && !current.resolving && !typing) {
    if (event.key === "y" || event.key === "Y") {
      event.preventDefault();
      void decide(current.action.id, true);
      return;
    }
    if (event.key === "n" || event.key === "N") {
      event.preventDefault();
      void decide(current.action.id, false);
      return;
    }
  }
  if (event.code === "Space" && !typing && listenAllowed(current) && !event.shiftKey) {
    event.preventDefault();
    void startMic();
    return;
  }
  if (event.key === "Escape") {
    stopListening();
    if (current.mode === "LISTENING") dispatchTurn({ type: "RESET" });
    else if (current.mode === "AWAITING_HITL" && current.listening) dispatchTurn({ type: "HITL_LISTEN_STOP" });
  }
}

export { workspaceFromCategory };
