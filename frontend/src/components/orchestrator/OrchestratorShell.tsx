"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ChatResponse, Conversation, PendingAction, Preferences, Scene } from "@/lib/types";
import {
  DEFAULT_AGENTS,
  agentCode,
  agentForPending,
  agentIdFromTarget,
  formatClock,
  type ActivityItem,
  type AgentId,
  type AgentNode,
  type OrchestratorMode,
} from "@/lib/orchestrator";
import {
  INITIAL_JARVIS_STATE,
  isBusy,
  jarvisReducer,
  listenAllowed,
  type JarvisEvent,
  type JarvisState,
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
import BlurText from "@/components/react-bits/BlurText";
import ClickSpark from "@/components/react-bits/ClickSpark";
import GradientText from "@/components/react-bits/GradientText";
import SpotlightCard from "@/components/react-bits/SpotlightCard";
import { ActivityStream } from "./ActivityStream";
import { CommandBaton } from "./CommandBaton";
import { ConversationRail, type RailConversation } from "./ConversationRail";
import { DraftComposeModal } from "./DraftComposeModal";
import { HitlModal } from "./HitlModal";
import { JarvisCore } from "./JarvisCore";
import { Orchestra } from "./Orchestra";
import { SuggestedTasksPanel, type SuggestedTask } from "./SuggestedTasksPanel";
import { WeatherCard } from "./WeatherCard";

const AMBIENT_SESSION = "default";
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

function VoiceLine({ text, dimmed }: { text: string; dimmed?: boolean }) {
  const compact = text.length > 220 || text.split("\n").length > 4;
  return (
    <h1
      className={[
        "orch-voice mx-auto max-h-[42vh] max-w-[min(800px,90vw)] overflow-y-auto text-center font-display font-normal leading-snug tracking-[-0.01em] whitespace-pre-wrap break-words transition-all duration-[600ms]",
        compact ? "text-[1.35rem]" : "text-[2.25rem]",
        dimmed ? "opacity-20 blur-[2px]" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {dimmed ? (
        text
      ) : (
        <BlurText
          key={text}
          text={text}
          delay={compact ? 40 : 70}
          stepDuration={0.24}
          className="inline"
        />
      )}
    </h1>
  );
}

/** Maps the FSM's macro-state onto the visual mode JarvisCore/Orchestra already render.
 * SPEAKING maps to "busy" — same visual treatment as THINKING/EXECUTING, just correctly
 * covering the TTS-playback window that the old flag-based code left unaccounted for. */
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
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [error, setError] = useState("");
  const [suggested, setSuggested] = useState<SuggestedTask[]>([]);
  const [weatherLine, setWeatherLine] = useState("");
  const [dockHidden, setDockHidden] = useState(false);

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

  /** Applies a transition. Returns the new state if it took effect, or null
   * if the event was refused (no-op) — e.g. LISTEN_START while SPEAKING. */
  const applyEvent = useCallback((event: JarvisEvent) => {
    const next = jarvisReducer(stateRef.current, event);
    if (next === stateRef.current) return null;
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

  const setAgentStates = useCallback((ids: AgentId[], state: AgentNode["state"]) => {
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

  const refreshDesk = useCallback(async (focusId: string | null = activeConversationId) => {
    const payload = await api.conversations(true).catch(() => ({ items: [] as Conversation[] }));
    setDesk(mapDeskItems(payload.items || [], focusId));
    return payload.items || [];
  }, [activeConversationId]);

  const loadSessionSurface = useCallback(
    async (sessionId: string, opts?: { announce?: boolean }) => {
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

  const focusAmbient = useCallback(async () => {
    sessionRef.current = AMBIENT_SESSION;
    setActiveSession(AMBIENT_SESSION);
    setActiveConversationId(null);
    setFocusTitle("Everyday desk");
    try {
      localStorage.removeItem(FOCUS_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    await refreshDesk(null);
    await loadSessionSurface(AMBIENT_SESSION, { announce: true });
    showVoice("Back on the everyday desk.");
  }, [loadSessionSurface, refreshDesk, showVoice]);

  const focusConversation = useCallback(
    async (row: Conversation, opts?: { announce?: boolean }) => {
      const sessionId = row.session_id || AMBIENT_SESSION;
      sessionRef.current = sessionId;
      setActiveSession(sessionId);
      setActiveConversationId(row.id);
      setFocusTitle(row.title || row.kind_label || "Conversation");
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
    [loadSessionSurface, refreshDesk, showVoice],
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
      if (boardOwnsHud) clearVoice();
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
        setAgents((prev) =>
          prev.map((agent) => {
            const match = result.agents!.find((row) => row.id === agent.id);
            return match ? { ...agent, state: (match.state as AgentNode["state"]) || "" } : agent;
          }),
        );
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
            confirmListenRef.current(nextAction);
          }
        });
      } else if (nextAction) {
        const settled = applyEvent({ type: "AWAIT_HITL", action: nextAction });
        if (settled) confirmListenRef.current(nextAction);
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
      onEnd: () => applyEvent({ type: "HITL_LISTEN_STOP" }),
      onError: () => applyEvent({ type: "HITL_LISTEN_STOP" }),
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
        setError(err instanceof Error ? err.message : "Confirm failed");
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

      const next = applyEvent({ type: "SEND", text });
      if (!next) return;

      setCompose("");
      setError("");
      stopListening();

      pushLog("SYS", text.length > 72 ? `${text.slice(0, 72)}…` : text);
      showVoice("Orchestrating…");

      try {
        const result = await api.chat(text, sessionRef.current);
        applyResponse(result);
        void refreshDesk(activeConversationId);
      } catch (err) {
        clearAgents();
        const msg = err instanceof Error ? err.message : "Request failed";
        setError(msg);
        showVoice("Connection fault. Awaiting instruction.");
        pushLog("SYS", "Request failed.");
        applyEvent({ type: "RESET" });
      }
    },
    [activeConversationId, applyEvent, applyResponse, clearAgents, decide, pushLog, refreshDesk, showVoice],
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
        const [preferences, deskRows, tasks] = await Promise.all([
          api.preferences().catch(() => null),
          api.conversations(true).catch(() => ({ items: [] as Conversation[] })),
          api.suggestedTasks(false, AMBIENT_SESSION).catch(() => ({ items: [], weather: undefined })),
        ]);
        if (cancelled) return;
        if (preferences) {
          setPrefs(preferences);
          voiceEnabledRef.current = preferences.voice_enabled !== false;
        }
        const rows = deskRows.items || [];
        const restored = storedId ? rows.find((row) => row.id === storedId) : null;
        const focusId = restored?.id || null;
        setDesk(mapDeskItems(rows, focusId));
        if (restored) {
          sessionRef.current = restored.session_id || AMBIENT_SESSION;
          setActiveSession(sessionRef.current);
          setActiveConversationId(restored.id);
          setFocusTitle(restored.title || "Conversation");
          void api.patchConversation(restored.id, { minimized: false }).catch(() => null);
          await loadSessionSurface(sessionRef.current, { announce: true });
        } else {
          sessionRef.current = AMBIENT_SESSION;
          setActiveSession(AMBIENT_SESSION);
          setActiveConversationId(null);
          setFocusTitle("Everyday desk");
          await loadSessionSurface(AMBIENT_SESSION, { announce: true });
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
      } catch {
        /* offline bootstrap is fine for UI shell */
      }
    })();
    return () => {
      cancelled = true;
      stopListening();
      silence();
    };
  }, [loadSessionSurface]);

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
  }, [desk.length, focusConversation, pushLog, refreshDesk]);

  const openWorkflowFromTask = useCallback(
    async (task: SuggestedTask) => {
      if (isBusy(stateRef.current)) return;
      try {
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
    [focusConversation, pushLog, send],
  );

  return (
    <ClickSpark className="orch-root relative flex h-screen flex-col overflow-hidden" sparkColor="#7dffe0">
      <div className="orch-vignette" />
      <JarvisCore mode={mode} />

      <ActivityStream items={activity} />

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

      <main className="relative z-[1] flex flex-1 flex-col items-center justify-center px-16">
        <div
          className={[
            "transition-all duration-[600ms]",
            showCenterVoice
              ? "translate-y-0 opacity-100"
              : "pointer-events-none translate-y-2.5 opacity-0",
          ].join(" ")}
          aria-hidden={!showCenterVoice}
        >
          <VoiceLine text={voice} dimmed={Boolean(hitlAction)} />
        </div>
        {sceneHasBoardContent(scene) ? (
          <SpotlightCard
            className="orch-board mt-8 w-full max-w-[min(720px,92vw)] rounded-2xl border border-[color:var(--border)] bg-black/35 backdrop-blur-md"
            bodyClassName="max-h-[38vh] overflow-y-auto p-4"
          >
            <SceneBoard scene={scene} compact />
          </SpotlightCard>
        ) : null}
        {sending ? (
          <div className="orch-sending mt-10 flex flex-col items-center gap-3" aria-live="polite">
            <div className="orch-sending-ring" />
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[color:var(--accent)]/80">
              Transmitting…
            </p>
          </div>
        ) : null}
        {error ? (
          <p className="mt-4 max-w-lg text-center font-mono text-xs text-red-300/80">{error}</p>
        ) : null}
        <p className="mt-6 font-mono text-[10px] uppercase tracking-[0.2em] text-[color:var(--muted)]/55">
          <GradientText className="font-mono text-[10px] uppercase tracking-[0.2em]" animationSpeed={9}>
            {prefs?.assistant_name || "Jarvis"}
          </GradientText>
          <span className="mx-2 text-[color:var(--muted)]/40">·</span>
          {focusTitle}
        </p>
      </main>

      <Orchestra agents={agents} dimmed={hitl} />

      {!hitl && (weatherLine || suggested.length) ? (
        <aside className="pointer-events-auto absolute right-4 top-24 z-10 flex max-h-[calc(100vh-11rem)] w-[min(360px,92vw)] flex-col gap-3">
          <WeatherCard line={weatherLine} />
          <SuggestedTasksPanel
            tasks={suggested}
            onDismiss={(id) => {
              void api.setSuggestedTaskStatus(id, "dismissed").catch(() => null);
              setSuggested((prev) => prev.filter((t) => t.id !== id));
            }}
            onAction={(task, actionId) => {
              if (task.kind === "rfq" && actionId === "engineering") {
                void openWorkflowFromTask(task);
              } else if (actionId === "calendar" || actionId === "meeting") {
                void send(`Create a calendar event for: ${task.title}`);
              } else if (actionId === "chat" || actionId === "review") {
                void (async () => {
                  const row = await api.startDiscussion(task.title.slice(0, 80));
                  await focusConversation(row, { announce: true });
                  void send(`Let's discuss: ${task.title}. ${task.detail || ""}`);
                })();
              } else {
                void send(`${actionId} for suggested task: ${task.title}`);
              }
            }}
          />
        </aside>
      ) : null}

      <CommandBaton
        value={compose}
        onChange={setCompose}
        onSubmit={(value) => void send(value)}
        onMic={() => void startMic()}
        listening={listening}
        disabled={busy || hitl}
        hidden={hitl}
      />

      <HitlModal
        action={hitlAction}
        visible={Boolean(hitlAction)}
        listening={confirmListening}
        busy={busy}
        onDecide={(id, approved) => void decide(id, approved)}
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
    </ClickSpark>
  );
}
