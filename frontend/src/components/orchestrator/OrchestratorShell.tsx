"use client";

import { Profiler, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { PerfOverlay } from "@/components/pane/PerfOverlay";
import { isJarvisPerfMode, recordOrchestratorShellCommit } from "@/lib/pane/perf";
import "@/lib/pane/perf";
import { api, apiBase } from "@/lib/api";
import { liveLog } from "@/lib/liveLog";
import type { ChatResponse, Conversation, PendingAction, Preferences, Scene } from "@/lib/types";
import {
  DEFAULT_AGENTS,
  agentCode,
  agentForPending,
  agentIdFromTarget,
  agentsFromApi,
  formatClock,
  type ActivityItem,
  type AgentNode,
  type OrchestratorMode,
} from "@/lib/orchestrator";
import {
  INITIAL_JARVIS_STATE,
  failureLineForTurn,
  isBusy,
  jarvisReducer,
  listenAllowed,
  type JarvisEvent,
  type JarvisState,
  type ServerTurn,
} from "@/lib/orchestratorFsm";
import {
  canListen,
  classifyDecision,
  silence,
  speak,
  startListening,
  stopListening,
} from "@/lib/voice";
import { SceneBoard } from "../SceneBoard";
import ClickSpark from "@/components/react-bits/ClickSpark";
import SpotlightCard from "@/components/react-bits/SpotlightCard";
import { ConverseStrip } from "@/components/bench/ConverseStrip";
import { DrawingStage } from "@/components/bench/DrawingStage";
import { QuoteSheet, quoteSheetRowsForScene } from "@/components/bench/QuoteSheet";
import { ActivityStream } from "./ActivityStream";
import { CommandBaton } from "./CommandBaton";
import { ConversationRail, type RailConversation } from "./ConversationRail";
import { DraftComposeModal } from "./DraftComposeModal";
import { JarvisCore } from "./JarvisCore";
import { HitlModal } from "./HitlModal";
import { AgentOrbit } from "./monitor/AgentOrbit";
import { Orchestra } from "./Orchestra";
import { SuggestedTasksPanel, type SuggestedTask } from "./SuggestedTasksPanel";
import {
  ConnectGoogleModal,
  googleConnectSpeakLine,
  googleServicesIncomplete,
  type GoogleConnectStatus,
} from "./ConnectGoogleModal";
import { PreferencesPanel } from "./PreferencesPanel";
import { WeatherCard } from "./WeatherCard";
import {
  initialWorkspaceFromBootstrap,
  isHudWorkspace,
  loadStoredWorkspace,
  loadStoredWorkspacePinned,
  persistWorkspace,
  persistWorkspacePinned,
  talkJumpWorkspace,
  type HudWorkspace,
} from "./hudWorkspace";
import { TurnStageLine } from "./TurnStageLine";
import { Pane } from "@/components/pane/Pane";
import { useDisplayLens, useLens, usePane } from "@/lib/pane/paneStore";
import { useWatchFindingsGlance } from "@/components/pane/useWatchFindingsGlance";
import { useValueWhenSettled } from "@/lib/pane/useLensSettled";

const AMBIENT_SESSION = "default";

/** Screenshot / verify override: ?lens=monitor|casual|engineering */
function workspaceFromLensQuery(): HudWorkspace | null {
  if (typeof window === "undefined") return null;
  try {
    const v = new URLSearchParams(window.location.search).get("lens");
    return isHudWorkspace(v) ? v : null;
  } catch {
    return null;
  }
}
const FOCUS_STORAGE_KEY = "jarvis.activeConversationId";
const IDLE_VOICE = "Awaiting instruction.";
const EMPTY_SCENE: Scene = { title: "", widgets: [] };
const MAX_OPEN_CONVERSATIONS = 3;

/** Mail / HITL / tool boards keep widgets; speak-only chat shells do not. */
function sceneHasBoardContent(scene: Scene | null | undefined): boolean {
  if (!scene) return false;
  const widgets = scene.widgets || [];
  const title = (scene.title || "").trim();
  const decorativeTitle = !title || /^jarvis$/i.test(title);

  if (widgets.length === 0) {
    // Title-only shells like "Draft email" still show; empty/Jarvis do not
    return Boolean(title) && !/^jarvis$/i.test(title);
  }

  // Quote-only + empty/Jarvis title duplicates the VoiceLine reply
  const onlyQuotes = widgets.every((w) => w.type === "quote");
  if (onlyQuotes && decorativeTitle) return false;

  return true;
}

function mapDeskItems(
  rows: Conversation[],
  activeConversationId: string | null,
): RailConversation[] {
  return rows
    .filter((row) => !row.minimized)
    .slice(0, MAX_OPEN_CONVERSATIONS)
    .map((row) => ({
    id: row.id,
    sessionId: row.session_id,
    title: row.title || row.category || "Conversation",
    kindLabel: row.kind_label || (row.category === "workflow" ? "Job" : row.category === "drawing" ? "Drawing" : "Discussion"),
    time: row.updated_at
      ? new Date(row.updated_at).toLocaleTimeString("en-US", {
          hour: "numeric",
          minute: "2-digit",
        })
      : undefined,
    preview: row.speak || row.turns?.slice(-1)[0]?.content || "",
    active: activeConversationId === row.id,
    waiting: Boolean(row.waiting || (row.pending && row.pending.length)),
  }));
}

function LensSparkShell({ children }: { children: React.ReactNode }) {
  const lens = useLens();
  const sparkColor = lens === "watch" ? "#FF6F37" : "#7dffe0";
  return (
    <ClickSpark className="relative flex h-screen flex-col overflow-hidden" sparkColor={sparkColor}>
      {children}
    </ClickSpark>
  );
}

function BenchStagePanel({
  scene,
  focus,
}: {
  scene: Scene;
  focus: Record<string, unknown>;
}) {
  const gatedScene = useValueWhenSettled(scene);
  const pinRows = quoteSheetRowsForScene(gatedScene);
  return (
    <DrawingStage scene={gatedScene} focus={focus} pinRows={pinRows} />
  );
}

function BenchQuotePanel({ scene }: { scene: Scene }) {
  const gatedScene = useValueWhenSettled(scene);
  return <QuoteSheet scene={gatedScene} />;
}

function BenchAgentDots({ agents }: { agents: AgentNode[] }) {
  return (
    <div className="flex items-center gap-1.5">
      {agents.slice(0, 4).map((agent) => (
        <span
          key={agent.id}
          className={[
            "h-1.5 w-1.5 rounded-full bg-[color:var(--muted)]",
            agent.state ? "bg-[color:var(--accent)] shadow-[0_0_6px_color-mix(in_oklch,var(--accent)_50%,transparent)]" : "",
          ].join(" ")}
          title={agent.code}
        />
      ))}
    </div>
  );
}

function TasksDockPanel({
  tasks,
  hitl,
  onDismiss,
  onAction,
}: {
  tasks: SuggestedTask[];
  hitl: boolean;
  onDismiss: (id: string) => void;
  onAction: (task: SuggestedTask, actionId: string) => void;
}) {
  const displayLens = useDisplayLens();
  const watchFindings = displayLens === "watch" && !hitl;
  useWatchFindingsGlance(tasks, watchFindings);
  if (hitl) {
    return <div className="h-full min-h-[120px]" aria-hidden />;
  }
  return (
    <div className="flex h-full max-h-full min-h-0 flex-col overflow-hidden p-2">
      <SuggestedTasksPanel
        variant={displayLens === "watch" ? "findings" : "suggested"}
        tasks={tasks}
        onDismiss={onDismiss}
        onAction={onAction}
      />
    </div>
  );
}

function AgentsDockPanel({
  agents,
  activity,
  hitl,
}: {
  agents: AgentNode[];
  activity: ActivityItem[];
  hitl: boolean;
}) {
  const displayLens = useDisplayLens();
  const presenceMode = usePane((s) => s.mode);
  if (displayLens === "watch") {
    return (
      <div className="flex h-full items-end justify-center pb-3">
        <AgentOrbit
          agents={agents}
          activity={activity}
          dimmed={hitl}
          idlePresence={!hitl && presenceMode === "idle"}
        />
      </div>
    );
  }
  if (displayLens === "converse") {
    return (
      <div className="flex h-full w-full items-end justify-center pb-2">
        <Orchestra agents={agents} dimmed={hitl} />
      </div>
    );
  }
  return null;
}

function VoiceDockPanel({
  voice,
  voiceVisible,
  showCenterVoice,
  hitlAction,
  scene,
  sending,
  ledgerTurnId,
  error,
  focusTitle,
  prefsName,
  orchestratorMode,
  onLedgerTurnComplete,
  onLedgerTurnFailed,
  compose,
  listening,
  batonDisabled,
  batonHidden,
  onComposeChange,
  onComposeSubmit,
  onMic,
}: {
  voice: string;
  voiceVisible: boolean;
  showCenterVoice: boolean;
  hitlAction: PendingAction | null;
  scene: Scene;
  sending: boolean;
  ledgerTurnId: string | null;
  error: string;
  focusTitle: string;
  prefsName: string;
  orchestratorMode: OrchestratorMode;
  onLedgerTurnComplete: (output: ChatResponse) => void;
  onLedgerTurnFailed: (message: string) => void;
  compose: string;
  listening: boolean;
  batonDisabled?: boolean;
  batonHidden?: boolean;
  onComposeChange: (value: string) => void;
  onComposeSubmit: (value: string) => void;
  onMic: () => void;
}) {
  const activeLens = useDisplayLens();
  const gatedScene = useValueWhenSettled(scene);

  if (activeLens === "watch") {
    const line = (voiceVisible && voice ? voice : focusTitle).slice(0, 120);
    return (
      <div className="flex h-full min-h-0 items-end justify-center pb-1">
        <p className="max-w-[min(520px,90%)] px-3 text-center font-display text-base leading-snug text-[color:var(--fg)]/90 [text-shadow:0_1px_10px_rgba(0,0,0,0.55)]">
          {line}
        </p>
      </div>
    );
  }

  if (activeLens === "bench") {
    const line = voiceVisible ? voice : focusTitle;
    return (
      <ConverseStrip
        line={line}
        baton={
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
        }
      />
    );
  }

  /* Converse: open center — substrate orb + DOM rings; always a short idle line. */
  const line = (showCenterVoice && voice ? voice : IDLE_VOICE).trim() || IDLE_VOICE;
  const shortLine = line.length > 96 || line.includes("\n") ? `${line.slice(0, 96).trim()}…` : line;
  return (
    <div className="pointer-events-none relative flex h-full min-h-0 w-full items-center justify-center overflow-visible">
      <JarvisCore mode={orchestratorMode} />
      <div className="pointer-events-none relative z-[2] max-w-[min(420px,70%)] px-4 text-center">
        <p
          className={[
            "font-display text-[1.35rem] leading-snug tracking-[-0.01em] text-[color:var(--fg)] [text-shadow:0_1px_12px_rgba(0,0,0,0.65)]",
            hitlAction ? "opacity-20 blur-[2px]" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          {shortLine}
        </p>
      </div>
      {sceneHasBoardContent(gatedScene) ? (
        <div className="pointer-events-auto absolute inset-x-4 bottom-2 z-[3] max-h-[28%] overflow-hidden">
          <SpotlightCard
            className="orch-board w-full rounded-2xl border border-[color:var(--border)] bg-black/35"
            bodyClassName="max-h-[22vh] overflow-y-auto p-3"
          >
            <SceneBoard scene={gatedScene} compact />
          </SpotlightCard>
        </div>
      ) : null}
      {sending ? (
        <div className="pointer-events-none absolute bottom-6 z-[3] flex flex-col items-center gap-2" aria-live="polite">
          <div className="orch-sending-ring" />
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[color:var(--accent)]/80">
            Transmitting…
          </p>
        </div>
      ) : null}
      <div className="pointer-events-none absolute bottom-2 left-1/2 z-[3] -translate-x-1/2">
        <TurnStageLine
          turnId={ledgerTurnId}
          onComplete={onLedgerTurnComplete}
          onFailed={onLedgerTurnFailed}
        />
      </div>
      {error ? (
        <p className="pointer-events-none absolute bottom-10 z-[3] max-w-md px-4 text-center font-mono text-xs text-red-300/80">
          {error}
        </p>
      ) : null}
      <span className="sr-only">
        {prefsName} · {focusTitle}
      </span>
    </div>
  );
}

function modeToOrchestratorMode(state: JarvisState): OrchestratorMode {
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

export function OrchestratorShell() {
  const [voice, setVoice] = useState(IDLE_VOICE);
  const [voiceVisible, setVoiceVisible] = useState(false);
  const [scene, setScene] = useState<Scene>(EMPTY_SCENE);
  const [compose, setCompose] = useState("");
  const [state, dispatch] = useReducer(jarvisReducer, INITIAL_JARVIS_STATE);
  const [agents, setAgents] = useState<AgentNode[]>(DEFAULT_AGENTS);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [desk, setDesk] = useState<RailConversation[]>([]);
  const [activeSession, setActiveSession] = useState(AMBIENT_SESSION);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [focusTitle, setFocusTitle] = useState("Everyday desk");
  const [conversationFocus, setConversationFocus] = useState<Record<string, unknown>>({});
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [error, setError] = useState("");
  const [suggested, setSuggested] = useState<SuggestedTask[]>([]);
  const [weatherLine, setWeatherLine] = useState("");
  const [dockHidden, setDockHidden] = useState(false);
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [googleStatus, setGoogleStatus] = useState<GoogleConnectStatus | null>(null);
  const [googleConnectOpen, setGoogleConnectOpen] = useState(false);
  const [workspace, setWorkspaceState] = useState<HudWorkspace>(
    () => workspaceFromLensQuery() ?? "monitor",
  );
  const [workspacePinned, setWorkspacePinned] = useState(false);
  const [ledgerTurnId, setLedgerTurnId] = useState<string | null>(null);

  // Mirrors `state` synchronously (a render behind `state` itself) so
  // imperative callbacks can guard re-entrancy (e.g. a second send() firing
  // before React has committed the first transition) without waiting on a
  // render. `applyEvent` keeps both in lockstep on every dispatch.
  const stateRef = useRef<JarvisState>(state);
  const speakGenRef = useRef(0);
  const sessionRef = useRef(AMBIENT_SESSION);
  const voiceEnabledRef = useRef(true);
  const composeFieldsRef = useRef({ to: "", subject: "", body: "" });
  const decideRef = useRef<(id: string, approved: boolean, fields?: { to: string; subject: string; body: string }) => Promise<void>>(
    async () => undefined,
  );
  const confirmListenRef = useRef<(action: PendingAction) => void>(() => undefined);
  const sendRef = useRef<(message: string) => Promise<void>>(async () => undefined);
  const googlePromptSpokenRef = useRef(false);
  const workspaceRef = useRef<HudWorkspace>("monitor");
  const workspacePinnedRef = useRef(false);

  const setWorkspaceExplicit = useCallback(
    (next: HudWorkspace, reason?: "switcher" | "pin" | "auto-focus" | "talk-jump" | "ambient") => {
      const from = workspaceRef.current;
      if (from !== next && reason) {
        liveLog(
          "workspace",
          { from, to: next, pinned: workspacePinnedRef.current, reason },
          { sessionId: sessionRef.current },
        );
      }
      workspaceRef.current = next;
      setWorkspaceState(next);
      persistWorkspace(next);
    },
    [],
  );

  const applyFocusWorkspace = useCallback(
    (category: string) => {
      const cat = (category || "").toLowerCase();
      if (cat === "workflow" || cat === "drawing") {
        setWorkspaceExplicit("engineering", "auto-focus");
        return;
      }
      if (cat === "discussion" && !workspacePinnedRef.current) {
        setWorkspaceExplicit("casual", "auto-focus");
      }
    },
    [setWorkspaceExplicit],
  );

  const persistWorkspaceIntent = useCallback((next: HudWorkspace) => {
    const from = workspaceRef.current;
    if (from === next) return;
    workspaceRef.current = next;
    persistWorkspace(next);
    liveLog(
      "workspace",
      { from, to: next, pinned: workspacePinnedRef.current, reason: "switcher" },
      { sessionId: sessionRef.current },
    );
  }, []);

  const toggleWorkspacePin = useCallback(() => {
    setWorkspacePinned((prev) => {
      const next = !prev;
      workspacePinnedRef.current = next;
      persistWorkspacePinned(next);
      liveLog(
        "workspace",
        { from: workspaceRef.current, to: workspaceRef.current, pinned: next, reason: "pin" },
        { sessionId: sessionRef.current },
      );
      return next;
    });
  }, []);

  /** Applies a transition. Returns the new state if it took effect, or null
   * if the event was refused (no-op) — e.g. LISTEN_START while SPEAKING. */
  const applyEvent = useCallback((event: JarvisEvent) => {
    const prev = stateRef.current;
    const next = jarvisReducer(prev, event);
    if (next === prev) return null;
    if (prev.mode !== next.mode) {
      liveLog(
        "fsm",
        { event: event.type, from_mode: prev.mode, to_mode: next.mode, refused: false },
        { sessionId: sessionRef.current },
      );
    }
    stateRef.current = next;
    dispatch(event);
    return next;
  }, []);

  const hitlAction: PendingAction | null =
    state.mode === "AWAITING_HITL" && state.action.kind !== "email_compose" ? state.action : null;
  const composeDraft: PendingAction | null =
    state.mode === "AWAITING_HITL" && state.action.kind === "email_compose" ? state.action : null;
  const hitl = state.mode === "AWAITING_HITL";
  const confirmListening = state.mode === "AWAITING_HITL" && state.listening;
  const sending = state.mode === "EXECUTING";
  const listening = state.mode === "LISTENING";
  const busy = isBusy(state);
  const mode: OrchestratorMode = modeToOrchestratorMode(state);
  /** Mail board / compose modal owns the center — hide VoiceLine so text is not duplicated. */
  const boardOwnsCenter = sceneHasBoardContent(scene) || Boolean(composeDraft);
  const showCenterVoice = voiceVisible && !boardOwnsCenter;

  const pushLog = useCallback((agent: string, message: string) => {
    setActivity((prev) =>
      [
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          time: formatClock(),
          agent,
          message,
        },
        ...prev,
      ].slice(0, 8),
    );
  }, []);

  const setAgentStates = useCallback((ids: string[], state: AgentNode["state"]) => {
    setAgents((prev) =>
      prev.map((agent) => ({
        ...agent,
        state: ids.includes(agent.id) ? state : state === "active" || state === "waiting" ? "" : agent.state,
      })),
    );
  }, []);

  const clearAgents = useCallback(() => {
    setAgents((prev) => prev.map((agent) => ({ ...agent, state: "" })));
  }, []);

  const showVoice = useCallback((text: string) => {
    const next = (text || "").trim() || IDLE_VOICE;
    setVoiceVisible(false);
    window.setTimeout(() => {
      setVoice(next);
      setVoiceVisible(true);
    }, 180);
  }, []);

  /** Compose modal owns the draft — clear center HUD text so it does not compete. */
  const clearVoice = useCallback(() => {
    setVoiceVisible(false);
    setVoice("");
  }, []);

  const announceGoogleConnect = useCallback(
    (status: GoogleConnectStatus, opts?: { force?: boolean }) => {
      const line = googleConnectSpeakLine(status);
      if (!line) return;
      showVoice(line);
      speakGenRef.current += 1;
      const gen = speakGenRef.current;
      const started = applyEvent({ type: "SPEAK_START", text: line });
      if (!started) return;
      speak(
        line,
        voiceEnabledRef.current !== false,
        () => {
          if (gen !== speakGenRef.current) return;
          applyEvent({ type: "SPEAK_END" });
        },
        { force: opts?.force ?? true },
      );
    },
    [applyEvent, showVoice],
  );

  const refreshDesk = useCallback(async (focusId: string | null = activeConversationId) => {
    const payload = await api.conversations(true).catch(() => ({ items: [] as Conversation[] }));
    setDesk(mapDeskItems(payload.items || [], focusId));
    return payload.items || [];
  }, [activeConversationId]);

  const loadSessionSurface = useCallback(
    async (sessionId: string, opts?: { announce?: boolean }) => {
      void api.hermesWarm(sessionId).catch(() => null);
      const [waiting, session] = await Promise.all([
        api.pending(sessionId).catch(() => ({ items: [] as PendingAction[] })),
        api.session(sessionId).catch(() => null),
      ]);
      const items = waiting.items || [];
      const first = items[0] || null;
      // Restoring/switching sessions never auto-opens the confirm mic — only
      // a fresh reply (send/decide) does that. This is a plain state
      // snapshot, not an "awaiting a spoken answer" moment.
      applyEvent(first ? { type: "AWAIT_HITL", action: first } : { type: "RESET" });
      const composeOpen = first?.kind === "email_compose";
      if (composeOpen) {
        clearVoice();
      } else if (opts?.announce !== false && session?.speak) {
        showVoice(session.speak);
      } else if (opts?.announce !== false && !first) {
        showVoice(IDLE_VOICE);
      }
      if (first) {
        const agentId = agentForPending(first);
        setAgentStates([agentId], "waiting");
        pushLog(agentCode(agentId), "Pending authorization restored.");
      } else {
        clearAgents();
      }
    },
    [applyEvent, clearAgents, clearVoice, pushLog, setAgentStates, showVoice],
  );

  const reconcileOpenTurn = useCallback(async () => {
    try {
      const sessionId = sessionRef.current;
      const resp = await fetch(
        `${apiBase()}/api/turns/open?session_id=${encodeURIComponent(sessionId)}`,
      );
      if (!resp.ok) return;
      const data = (await resp.json()) as { enabled?: boolean; turns?: ServerTurn[] };
      if (!data.enabled) return;
      const turn = (Array.isArray(data.turns) ? data.turns : [])[0] ?? null;
      applyEvent({ type: "RECONCILE", turn });
      if (!turn) {
        setLedgerTurnId(null);
        await loadSessionSurface(sessionId, { announce: false });
        return;
      }
      const st = String(turn.state || "").toUpperCase();
      if (st === "FAILED" || st === "ABANDONED") {
        setLedgerTurnId(null);
        clearAgents();
        const line = failureLineForTurn(turn);
        setError(line);
        showVoice(line);
        return;
      }
      if (st === "QUEUED" || st === "RUNNING") {
        setLedgerTurnId(turn.id);
        showVoice("Orchestrating…");
        return;
      }
      if (st === "EXECUTING") {
        setLedgerTurnId(turn.id);
        showVoice("Working…");
        return;
      }
      if (st === "AWAITING_HITL" && turn.pending_action) {
        setLedgerTurnId(null);
        const action = turn.pending_action;
        if (action.kind === "email_compose") clearVoice();
        const agentId = agentForPending(action);
        setAgentStates([agentId], "waiting");
        pushLog(agentCode(agentId), "Pending authorization restored.");
      }
    } catch {
      /* failed fetch leaves the current screen alone */
    }
  }, [applyEvent, clearAgents, clearVoice, loadSessionSurface, pushLog, setAgentStates, showVoice]);

  const focusAmbient = useCallback(async () => {
    sessionRef.current = AMBIENT_SESSION;
    setActiveSession(AMBIENT_SESSION);
    setActiveConversationId(null);
    setFocusTitle("Everyday desk");
    setConversationFocus({});
    if (!workspacePinnedRef.current) {
      setWorkspaceExplicit("monitor", "ambient");
    }
    try {
      localStorage.removeItem(FOCUS_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    await refreshDesk(null);
    await loadSessionSurface(AMBIENT_SESSION, { announce: true });
    showVoice("Back on the everyday desk.");
  }, [loadSessionSurface, refreshDesk, setWorkspaceExplicit, showVoice]);

  const focusConversation = useCallback(
    async (row: Conversation, opts?: { announce?: boolean }) => {
      applyFocusWorkspace(row.category);
      const sessionId = row.session_id || AMBIENT_SESSION;
      sessionRef.current = sessionId;
      setActiveSession(sessionId);
      setActiveConversationId(row.id);
      setFocusTitle(row.title || row.kind_label || "Conversation");
      setConversationFocus(row.focus || {});
      try {
        localStorage.setItem(FOCUS_STORAGE_KEY, row.id);
      } catch {
        /* ignore */
      }
      void api.patchConversation(row.id, { minimized: false }).catch(() => null);
      await refreshDesk(row.id);
      await loadSessionSurface(sessionId, { announce: false });
      if (opts?.announce !== false) {
        if (row.speak) showVoice(row.speak);
        else showVoice(IDLE_VOICE);
      }
    },
    [applyFocusWorkspace, loadSessionSurface, refreshDesk, showVoice],
  );

  const applyUiAction = useCallback(
    async (uiAction: Record<string, unknown> | null | undefined) => {
      const action = String(uiAction?.action || "");
      if (!action || action === "noop") {
        if (action === "noop") void refreshDesk(activeConversationId);
        return;
      }
      if (action === "hide_dock") {
        setDockHidden(true);
        return;
      }
      if (action === "show_dock") {
        setDockHidden(false);
        return;
      }
      const conversationId = typeof uiAction?.conversation_id === "string" ? uiAction.conversation_id : "";
      const rows = await refreshDesk(activeConversationId);
      if (action === "minimize") {
        if (activeConversationId && activeConversationId === conversationId) {
          await focusAmbient();
        }
        return;
      }
      if (action === "expand" && conversationId) {
        setDockHidden(false);
        const row = rows.find((item) => item.id === conversationId);
        if (row) await focusConversation(row, { announce: false });
      }
    },
    [activeConversationId, focusAmbient, focusConversation, refreshDesk],
  );

  const applyResponse = useCallback(
    (result: ChatResponse, opts?: { fromConfirm?: boolean; approved?: boolean }) => {
      void applyUiAction(result.ui_action);

      const waiting = result.pending || [];
      const nextAction = waiting[0] || null;

      // Prefer reply for on-screen HUD text; speak stays short for TTS.
      // When a board/modal owns the content (mail read, compose draft, etc.), clear
      // center VoiceLine so it does not duplicate the board.
      const display = (result.reply || result.speak || "").trim() || IDLE_VOICE;
      const tts = (result.speak || result.reply || "").trim();
      const nextScene = sceneHasBoardContent(result.scene) ? result.scene! : EMPTY_SCENE;
      const boardOwnsHud =
        sceneHasBoardContent(nextScene) || nextAction?.kind === "email_compose";
      if (boardOwnsHud && workspaceRef.current !== "engineering") clearVoice();
      else showVoice(display);
      setScene(nextScene);

      if (result.activity?.length) {
        setActivity((prev) => {
          const mapped = result.activity!.map((item, index) => ({
            id: item.id || `act-${Date.now()}-${index}`,
            time: item.time || formatClock(),
            agent: item.agent || "SYS",
            message: item.message || "",
          }));
          return [...mapped, ...prev].slice(0, 8);
        });
      }

      if (result.agents?.length) {
        setAgents(agentsFromApi(result.agents));
      } else if (result.target_agent) {
        const agentId = agentIdFromTarget(result.target_agent);
        if (agentId) {
          clearAgents();
          setAgentStates([agentId], nextAction ? "waiting" : "active");
          if (!nextAction) window.setTimeout(() => clearAgents(), 2400);
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
          window.setTimeout(() => clearAgents(), 2400);
        } else {
          clearAgents();
          pushLog("SYS", "Operator rejected sequence.");
        }
      }

      if (sceneHasBoardContent(result.scene) && result.scene?.title) {
        pushLog("SYS", result.scene.title);
      }

      speakGenRef.current += 1;
      const gen = speakGenRef.current;

      if (voiceEnabledRef.current && tts) {
        applyEvent({ type: "SPEAK_START", text: tts });
        speak(tts, true, () => {
          // A late-arriving clip's onEnd must not resurrect SPEAKING or
          // start a confirm-listen for a turn that's no longer current.
          if (gen !== speakGenRef.current) return;
          // If some other event already moved the mode on (e.g. a new
          // send() interrupted this speech), SPEAK_END is refused and
          // `nextAction` — already superseded — must not be re-presented.
          const settled = applyEvent({ type: "SPEAK_END" });
          if (settled === null) return;
          if (nextAction) {
            applyEvent({ type: "AWAIT_HITL", action: nextAction });
            liveLog(
              "hitl",
              { phase: "shown", action_kind: nextAction.kind, action_id: nextAction.id },
              { sessionId: sessionRef.current },
            );
            confirmListenRef.current(nextAction);
          }
        });
      } else if (nextAction) {
        const settled = applyEvent({ type: "AWAIT_HITL", action: nextAction });
        if (settled) {
          liveLog(
            "hitl",
            { phase: "shown", action_kind: nextAction.kind, action_id: nextAction.id },
            { sessionId: sessionRef.current },
          );
          confirmListenRef.current(nextAction);
        }
      } else {
        applyEvent({ type: "RESET" });
      }
    },
    [applyEvent, applyUiAction, clearAgents, clearVoice, pushLog, setAgentStates, showVoice],
  );

  /** Auto-opens the confirm mic right after a HITL panel is freshly presented
   * (mirrors the old listenForConfirm, now keyed off the FSM instead of a ref). */
  const startConfirmListen = useCallback((action: PendingAction) => {
    if (!canListen()) return;
    const missing = action.payload?.missing;
    const needsFill = action.kind === "email_compose" && Array.isArray(missing) && missing.length > 0;
    stopListening();
    const started = applyEvent({ type: "HITL_LISTEN_START" });
    if (!started) return;
    liveLog(
      "hitl",
      { phase: "listen-start", action_kind: action.kind, action_id: action.id },
      { sessionId: sessionRef.current },
    );
    void startListening({
      onFinal: (text) => {
        if (stateRef.current.mode !== "AWAITING_HITL" || stateRef.current.action.id !== action.id) return;
        const decision = classifyDecision(text);
        const words = text.trim().split(/\s+/).filter(Boolean).length;
        // Short authorize/reject phrases always win; otherwise body dictation goes to chat.
        if (decision && words <= 5) {
          applyEvent({ type: "HITL_LISTEN_STOP" });
          void decideRef.current(action.id, decision === "yes");
          return;
        }
        if (needsFill) {
          applyEvent({ type: "HITL_LISTEN_STOP" });
          void sendRef.current(text);
        }
      },
      onEnd: () => {
        applyEvent({ type: "HITL_LISTEN_STOP" });
        liveLog(
          "hitl",
          { phase: "listen-stop", action_kind: action.kind, action_id: action.id },
          { sessionId: sessionRef.current },
        );
      },
      onError: () => {
        applyEvent({ type: "HITL_LISTEN_STOP" });
        liveLog(
          "hitl",
          { phase: "listen-stop", action_kind: action.kind, action_id: action.id },
          { sessionId: sessionRef.current },
        );
      },
    });
  }, [applyEvent]);

  const decide = useCallback(
    async (id: string, approved: boolean, fields?: { to: string; subject: string; body: string }) => {
      const current = stateRef.current;
      if (current.mode !== "AWAITING_HITL" || current.action.id !== id || current.resolving) return;
      const action = current.action;

      stopListening();
      silence();

      const next = applyEvent(
        approved ? { type: "DECIDE_APPROVE", actionId: id } : { type: "DECIDE_REJECT", actionId: id },
      );
      if (!next) return;
      liveLog(
        "hitl",
        {
          phase: approved ? "authorize" : "reject",
          action_kind: action.kind,
          action_id: id,
        },
        { sessionId: sessionRef.current },
      );

      const syncFields = fields || (action.kind === "email_compose" ? composeFieldsRef.current : undefined);
      if (approved) {
        showVoice(action.kind === "email_compose" || action.kind === "email_send" || action.kind === "quote_send" ? "Sending…" : "Working…");
        setAgentStates(["ops"], "active");
        pushLog("OPS.04", "Executing authorized action…");
      }
      try {
        if (approved && syncFields && action.kind === "email_compose") {
          await api.updatePending(id, syncFields, sessionRef.current);
        }
        const result = await api.confirm(id, approved, sessionRef.current);
        applyResponse(result, { fromConfirm: true, approved });
        void refreshDesk(activeConversationId);
      } catch (err) {
        // Restore pending from server so HUD doesn't strand without Authorize
        try {
          const waiting = await api.pending(sessionRef.current);
          const restored = waiting.items?.[0] || null;
          applyEvent(restored ? { type: "AWAIT_HITL", action: restored } : { type: "RESET" });
        } catch {
          applyEvent({ type: "RESET" });
        }
        const msg = err instanceof Error ? err.message : "Confirm failed";
        setError(msg);
        liveLog("error", { message: msg }, { sessionId: sessionRef.current });
        pushLog("SYS", "Confirm failed.");
        showVoice("That did not go through. Awaiting instruction.");
      }
    },
    [activeConversationId, applyEvent, applyResponse, pushLog, refreshDesk, setAgentStates, showVoice],
  );

  useEffect(() => {
    decideRef.current = decide;
  }, [decide]);

  useEffect(() => {
    confirmListenRef.current = startConfirmListen;
  }, [startConfirmListen]);

  const send = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text) return;
      const current = stateRef.current;

      // A short "yes"/"no" while a HITL panel is open resolves it instead of chatting.
      const decision = current.mode === "AWAITING_HITL" ? classifyDecision(text) : null;
      const words = text.trim().split(/\s+/).filter(Boolean).length;
      if (decision && current.mode === "AWAITING_HITL" && words <= 5) {
        await decide(current.action.id, decision === "yes");
        setCompose("");
        return;
      }

      const jump = talkJumpWorkspace(text, workspaceRef.current);
      if (jump) setWorkspaceExplicit(jump, "talk-jump");
      liveLog(
        "send",
        {
          text: text.length > 500 ? `${text.slice(0, 500)}…` : text,
          workspace: workspaceRef.current,
          talk_jump: jump ?? null,
        },
        { sessionId: sessionRef.current },
      );

      const next = applyEvent({ type: "SEND", text });
      if (!next) return;

      setCompose("");
      setError("");
      stopListening();

      pushLog("SYS", text.length > 72 ? `${text.slice(0, 72)}…` : text);
      showVoice("Orchestrating…");

      try {
        const result = await api.chat(text, sessionRef.current);
        if (
          result &&
          typeof result === "object" &&
          "turn_id" in result &&
          typeof (result as { turn_id?: string }).turn_id === "string" &&
          !("speak" in result)
        ) {
          setLedgerTurnId((result as { turn_id: string }).turn_id);
          return;
        }
        setLedgerTurnId(null);
        applyResponse(result as ChatResponse);
        void refreshDesk(activeConversationId);
      } catch (err) {
        clearAgents();
        const msg = err instanceof Error ? err.message : "Request failed";
        setError(msg);
        liveLog("error", { message: msg }, { sessionId: sessionRef.current });
        showVoice("Connection fault. Awaiting instruction.");
        pushLog("SYS", "Request failed.");
        setLedgerTurnId(null);
        applyEvent({ type: "RESET" });
      }
    },
    [activeConversationId, applyEvent, applyResponse, clearAgents, decide, pushLog, refreshDesk, setWorkspaceExplicit, showVoice],
  );

  const onLedgerTurnComplete = useCallback(
    (output: ChatResponse) => {
      setLedgerTurnId(null);
      applyResponse(output);
      void refreshDesk(activeConversationId);
    },
    [activeConversationId, applyResponse, refreshDesk],
  );

  const onLedgerTurnFailed = useCallback(
    (message: string) => {
      setLedgerTurnId(null);
      clearAgents();
      setError(message);
      showVoice("Connection fault. Awaiting instruction.");
      pushLog("SYS", "Turn failed.");
      applyEvent({ type: "RESET" });
    },
    [applyEvent, clearAgents, pushLog, showVoice],
  );

  useEffect(() => {
    sendRef.current = send;
  }, [send]);

  const startMic = useCallback(async () => {
    if (!canListen()) return;
    const current = stateRef.current;

    if (current.mode === "AWAITING_HITL") {
      // Compose fill-in: reuse the same confirm-mic instead of opening a
      // second, independent recognizer session over it.
      if (!listenAllowed(current)) return;
      confirmListenRef.current(current.action);
      return;
    }

    const next = applyEvent({ type: "LISTEN_START" });
    if (!next) return;
    stopListening();
    try {
      await startListening({
        onPartial: (text) => setCompose(text),
        onFinal: (text) => {
          applyEvent({ type: "LISTEN_STOP" });
          setCompose("");
          void send(text);
        },
        onEnd: () => applyEvent({ type: "LISTEN_STOP" }),
        onError: (message) => {
          applyEvent({ type: "LISTEN_STOP" });
          setError(message);
        },
      });
    } catch (err) {
      applyEvent({ type: "LISTEN_STOP" });
      setError(err instanceof Error ? err.message : "Microphone unavailable");
    }
  }, [applyEvent, send]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("gmail") === "1") {
      setPrefsOpen(true);
      params.delete("gmail");
      const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
      window.history.replaceState({}, "", next);
    }
  }, []);

  useEffect(() => {
    if (!googleConnectOpen || !googleStatus || !googleServicesIncomplete(googleStatus)) return;
    // Defer past bootstrap silence()/session restore so the line is not swallowed.
    const timer = window.setTimeout(() => {
      if (googlePromptSpokenRef.current) return;
      googlePromptSpokenRef.current = true;
      announceGoogleConnect(googleStatus);
    }, 450);
    return () => window.clearTimeout(timer);
  }, [announceGoogleConnect, googleConnectOpen, googleStatus]);

  useEffect(() => {
    setVoiceVisible(true);
    let cancelled = false;
    (async () => {
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
        if (cancelled) return;
        if (preferences) {
          setPrefs(preferences);
          voiceEnabledRef.current = preferences.voice_enabled !== false;
        }
        const oauthReturn = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("gmail") === "1";
        if (google) {
          setGoogleStatus(google);
          if (googleServicesIncomplete(google) && !oauthReturn) {
            setGoogleConnectOpen(true);
          }
        }
        const skipAmbientAnnounce = Boolean(google && googleServicesIncomplete(google) && !oauthReturn);
        const rows = deskRows.items || [];
        const restored = storedId ? rows.find((row) => row.id === storedId) : null;
        const focusId = restored?.id || null;
        const pinned = loadStoredWorkspacePinned();
        const stored = loadStoredWorkspace();
        workspacePinnedRef.current = pinned;
        setWorkspacePinned(pinned);
        const lensWs = workspaceFromLensQuery();
        const initialWs =
          lensWs ??
          initialWorkspaceFromBootstrap({
            restoredCategory: restored?.category,
            pinned,
            stored,
          });
        setWorkspaceState(initialWs);
        workspaceRef.current = initialWs;
        persistWorkspace(initialWs);
        liveLog(
          "hud_boot",
          { workspace: initialWs, pinned, session: sessionRef.current },
          { sessionId: sessionRef.current },
        );
        setDesk(mapDeskItems(rows, focusId));
        if (restored) {
          sessionRef.current = restored.session_id || AMBIENT_SESSION;
          setActiveSession(sessionRef.current);
          setActiveConversationId(restored.id);
          setFocusTitle(restored.title || "Conversation");
          setConversationFocus(restored.focus || {});
          void api.patchConversation(restored.id, { minimized: false }).catch(() => null);
          await loadSessionSurface(sessionRef.current, { announce: !skipAmbientAnnounce });
        } else {
          sessionRef.current = AMBIENT_SESSION;
          setActiveSession(AMBIENT_SESSION);
          setActiveConversationId(null);
          setFocusTitle("Everyday desk");
          await loadSessionSurface(AMBIENT_SESSION, { announce: !skipAmbientAnnounce });
        }
        const taskItems = (tasks.items || [])
          .map((raw) => {
            const t = raw as SuggestedTask;
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
        setSuggested(taskItems);
        const speakWeather = (tasks.weather as { speak?: string } | undefined)?.speak || "";
        setWeatherLine(speakWeather);
        void api
          .officeRefresh(AMBIENT_SESSION)
          .then((payload) => {
            if (cancelled) return;
            const refreshed = ((payload.tasks as SuggestedTask[]) || []).map((t) => ({
              ...t,
              actions: Array.isArray(t.actions) ? t.actions : [],
            }));
            if (refreshed.length) setSuggested(refreshed);
            const w = (payload.weather as { speak?: string } | undefined)?.speak;
            if (w) setWeatherLine(w);
          })
          .catch(() => null);
        await reconcileOpenTurn();
      } catch {
        /* offline bootstrap is fine for UI shell */
      }
    })();
    return () => {
      cancelled = true;
      stopListening();
      silence();
    };
  }, [loadSessionSurface, reconcileOpenTurn]);

  useEffect(() => {
    const onFocus = () => {
      void reconcileOpenTurn();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [reconcileOpenTurn]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const typing =
        event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement;
      const current = stateRef.current;
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
      if (event.code === "Space" && !typing && listenAllowed(current)) {
        event.preventDefault();
        void startMic();
      }
      if (event.key === "Escape") {
        stopListening();
        if (current.mode === "LISTENING") applyEvent({ type: "RESET" });
        else if (current.mode === "AWAITING_HITL" && current.listening) {
          applyEvent({ type: "HITL_LISTEN_STOP" });
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [applyEvent, decide, startMic]);

  const startNewDiscussion = useCallback(async () => {
    if (isBusy(stateRef.current)) return;
    try {
      setWorkspaceExplicit("casual", "auto-focus");
      if (desk.length >= MAX_OPEN_CONVERSATIONS) {
        pushLog("SYS", `Max ${MAX_OPEN_CONVERSATIONS} open notes — oldest will be parked.`);
      }
      const row = await api.startDiscussion("");
      await focusConversation(row, { announce: true });
      pushLog("SYS", `Opened discussion: ${row.title}`);
      void refreshDesk(row.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open discussion");
    }
  }, [desk.length, focusConversation, pushLog, refreshDesk, setWorkspaceExplicit]);

  const openWorkflowFromTask = useCallback(
    async (task: SuggestedTask) => {
      if (isBusy(stateRef.current)) return;
      try {
        setWorkspaceExplicit("engineering", "auto-focus");
        const resumeKey = `task:${task.id}`;
        const title =
          task.kind === "rfq"
            ? `RFQ · ${task.title}`.slice(0, 80)
            : task.title.slice(0, 80) || "Job";
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
        setError(err instanceof Error ? err.message : "Could not open job");
      }
    },
    [focusConversation, pushLog, send, setWorkspaceExplicit],
  );

  const taskDismiss = useCallback((id: string) => {
    void api.setSuggestedTaskStatus(id, "dismissed").catch(() => null);
    setSuggested((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const taskAction = useCallback(
    (task: SuggestedTask, actionId: string) => {
      if (task.kind === "rfq" && actionId === "engineering") {
        void openWorkflowFromTask(task);
      } else if (actionId === "calendar" || actionId === "meeting") {
        void send(`Create a calendar event for: ${task.title}`);
      } else if (actionId === "chat" || actionId === "review") {
        void (async () => {
          setWorkspaceExplicit("casual");
          const row = await api.startDiscussion(task.title.slice(0, 80));
          await focusConversation(row, { announce: true });
          void send(`Let's discuss: ${task.title}. ${task.detail || ""}`);
        })();
      } else {
        void send(`${actionId} for suggested task: ${task.title}`);
      }
    },
    [focusConversation, openWorkflowFromTask, send, setWorkspaceExplicit],
  );

  const shellTree = (
    <LensSparkShell>
      <Pane
        workspace={workspace}
        workspacePinned={workspacePinned}
        orchestratorMode={mode}
        assistantName={prefs?.assistant_name || "Jarvis"}
        focusTitle={focusTitle}
        dimmed={hitl}
        batonHidden={hitl}
        batonDisabled={busy || hitl}
        compose={compose}
        listening={listening}
        onComposeChange={setCompose}
        onComposeSubmit={(value) => void send(value)}
        onMic={() => void startMic()}
        onSelectWorkspace={persistWorkspaceIntent}
        onTogglePin={toggleWorkspacePin}
        onOpenPrefs={() => setPrefsOpen(true)}
        className="flex-1"
        panels={{
          voice: (
            <VoiceDockPanel
              voice={voice}
              voiceVisible={voiceVisible}
              showCenterVoice={showCenterVoice}
              hitlAction={hitlAction}
              scene={scene}
              sending={sending}
              ledgerTurnId={ledgerTurnId}
              error={error}
              focusTitle={focusTitle}
              prefsName={prefs?.assistant_name || "Jarvis"}
              orchestratorMode={mode}
              onLedgerTurnComplete={onLedgerTurnComplete}
              onLedgerTurnFailed={onLedgerTurnFailed}
              compose={compose}
              listening={listening}
              batonDisabled={busy || hitl}
              batonHidden={hitl}
              onComposeChange={setCompose}
              onComposeSubmit={(value) => void send(value)}
              onMic={() => void startMic()}
            />
          ),
          notes: (
            <ConversationRail
              items={desk}
              openCount={desk.length}
              maxOpen={MAX_OPEN_CONVERSATIONS}
              ambientActive={activeSession === AMBIENT_SESSION && !activeConversationId}
              dimmed={hitl}
              hidden={dockHidden}
              onSelectAmbient={() => void focusAmbient()}
              onSelect={(id) => {
                void (async () => {
                  const rows = await refreshDesk(activeConversationId);
                  const row = rows.find((item) => item.id === id);
                  if (row) await focusConversation(row, { announce: true });
                })();
              }}
              onNewDiscussion={() => void startNewDiscussion()}
            />
          ),
          weather: weatherLine ? (
            <div className="p-2">
              <WeatherCard line={weatherLine} />
            </div>
          ) : null,
          tasks: (
            <TasksDockPanel tasks={suggested} hitl={hitl} onDismiss={taskDismiss} onAction={taskAction} />
          ),
          agents: (
            <AgentsDockPanel agents={agents} activity={activity} hitl={Boolean(hitlAction)} />
          ),
          agentsStatus: <BenchAgentDots agents={agents} />,
          activity: activity.length > 0 ? <ActivityStream items={activity} /> : null,
          stage: (
            <BenchStagePanel
              scene={scene}
              focus={conversationFocus}
            />
          ),
          sheet: <BenchQuotePanel scene={scene} />,
        }}
      />

      <HitlModal
        action={hitlAction}
        visible={Boolean(hitlAction)}
        listening={confirmListening}
        busy={busy}
        onDecide={(id, approved) => void decide(id, approved)}
      />

      <ConnectGoogleModal
        status={googleStatus}
        visible={googleConnectOpen}
        onLater={() => setGoogleConnectOpen(false)}
        onOpenPreferences={() => {
          setGoogleConnectOpen(false);
          setPrefsOpen(true);
        }}
        onPromptInteract={() => {
          if (googleStatus) announceGoogleConnect(googleStatus, { force: true });
        }}
      />

      <PreferencesPanel
        open={prefsOpen}
        prefs={prefs}
        onClose={() => setPrefsOpen(false)}
        onSave={async (next) => {
          const saved = await api.updatePreferences(next);
          setPrefs(saved);
          voiceEnabledRef.current = saved.voice_enabled !== false;
        }}
      />

      <DraftComposeModal
        action={composeDraft}
        visible={Boolean(composeDraft)}
        listening={confirmListening}
        busy={busy}
        onFieldsChange={(fields) => {
          composeFieldsRef.current = fields;
        }}
        onDecide={(id, approved, fields) => void decide(id, approved, fields)}
      />

    </LensSparkShell>
  );

  return (
    <>
      {isJarvisPerfMode() ? (
        <>
          <Profiler id="OrchestratorShell" onRender={recordOrchestratorShellCommit}>
            <span data-orch-shell-probe hidden aria-hidden />
          </Profiler>
          <PerfOverlay />
        </>
      ) : null}
      {shellTree}
    </>
  );
}
