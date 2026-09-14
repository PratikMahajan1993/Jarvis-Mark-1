"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ChatResponse, Conversation, PendingAction, Preferences, Scene } from "@/lib/types";
import {
  DEFAULT_AGENTS,
  agentCode,
  agentForPending,
  formatClock,
  inferBusyAgents,
  type ActivityItem,
  type AgentId,
  type AgentNode,
  type OrchestratorMode,
} from "@/lib/orchestrator";
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

export function OrchestratorShell() {
  const [voice, setVoice] = useState(IDLE_VOICE);
  const [voiceVisible, setVoiceVisible] = useState(false);
  const [scene, setScene] = useState<Scene>(EMPTY_SCENE);
  const [compose, setCompose] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [confirmListening, setConfirmListening] = useState(false);
  const [agents, setAgents] = useState<AgentNode[]>(DEFAULT_AGENTS);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [pending, setPending] = useState<PendingAction[]>([]);
  const [desk, setDesk] = useState<RailConversation[]>([]);
  const [activeSession, setActiveSession] = useState(AMBIENT_SESSION);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [focusTitle, setFocusTitle] = useState("Everyday desk");
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [suggested, setSuggested] = useState<SuggestedTask[]>([]);
  const [weatherLine, setWeatherLine] = useState("");

  const busyRef = useRef(false);
  const pendingIdRef = useRef("");
  const sessionRef = useRef(AMBIENT_SESSION);
  const voiceEnabledRef = useRef(true);
  const speakToken = useRef(0);
  const composeFieldsRef = useRef({ to: "", subject: "", body: "" });
  const decideRef = useRef<(id: string, approved: boolean, fields?: { to: string; subject: string; body: string }) => Promise<void>>(
    async () => undefined,
  );
  const listenConfirmRef = useRef<(actionId: string, fillCompose?: boolean) => Promise<void>>(async () => undefined);
  const sendRef = useRef<(message: string) => Promise<void>>(async () => undefined);

  const focused = pending[0] || null;
  const composeDraft = !sending && focused?.kind === "email_compose" ? focused : null;
  const composeMissing = Array.isArray(composeDraft?.payload?.missing)
    ? (composeDraft!.payload.missing as string[])
    : [];
  const composeNeedsInput = Boolean(composeDraft && composeMissing.length > 0);
  const hitlAction = composeDraft || sending ? null : focused;
  const hitl = Boolean(focused) && !sending;
  const mode: OrchestratorMode = sending ? "busy" : hitl ? "hitl" : busy ? "busy" : listening ? "listening" : "idle";

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
      setPending(items);
      pendingIdRef.current = items[0]?.id || "";
      if (opts?.announce !== false && session?.speak) {
        showVoice(session.speak);
      } else if (opts?.announce !== false && !items[0]) {
        showVoice(IDLE_VOICE);
      }
      if (items[0]) {
        const agentId = agentForPending(items[0]);
        setAgentStates([agentId], "waiting");
        pushLog(agentCode(agentId), "Pending authorization restored.");
      } else {
        clearAgents();
      }
    },
    [clearAgents, pushLog, setAgentStates, showVoice],
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

  const applyResponse = useCallback(
    (result: ChatResponse, opts?: { fromConfirm?: boolean; approved?: boolean }) => {
      const waiting = result.pending || [];
      setPending(waiting);
      pendingIdRef.current = waiting[0]?.id || "";

      // Prefer reply for on-screen HUD text; speak stays short for TTS
      const display = (result.reply || result.speak || "").trim() || IDLE_VOICE;
      const tts = (result.speak || result.reply || "").trim();
      showVoice(display);
      setScene(result.scene?.title || (result.scene?.widgets || []).length ? result.scene : EMPTY_SCENE);

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
      } else if (waiting[0]) {
        const agentId = agentForPending(waiting[0]);
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
      } else if (!result.agents?.length) {
        clearAgents();
      }

      if (result.scene?.title) {
        pushLog("SYS", result.scene.title);
      }

      speakToken.current += 1;
      const token = speakToken.current;
      const missing = waiting[0]?.payload?.missing;
      const needsFill =
        waiting[0]?.kind === "email_compose" && Array.isArray(missing) && missing.length > 0;
      if (voiceEnabledRef.current && tts) {
        speak(tts, true, () => {
          if (token !== speakToken.current) return;
          if (pendingIdRef.current) {
            void listenConfirmRef.current(pendingIdRef.current, needsFill);
          }
        });
      } else if (waiting[0]) {
        void listenConfirmRef.current(waiting[0].id, needsFill);
      }
    },
    [clearAgents, pushLog, setAgentStates, showVoice],
  );

  const listenForConfirm = useCallback(async (actionId: string, fillCompose = false) => {
    if (!canListen() || !actionId) return;
    stopListening();
    setConfirmListening(true);
    try {
      await startListening({
        onFinal: (text) => {
          if (pendingIdRef.current !== actionId) return;
          const decision = classifyDecision(text);
          const words = text.trim().split(/\s+/).filter(Boolean).length;
          // Short authorize/reject phrases always win; otherwise body dictation goes to chat.
          if (decision && words <= 5) {
            setConfirmListening(false);
            void decideRef.current(actionId, decision === "yes");
            return;
          }
          if (fillCompose) {
            setConfirmListening(false);
            void sendRef.current(text);
            return;
          }
        },
        onEnd: () => setConfirmListening(false),
        onError: () => setConfirmListening(false),
      });
    } catch {
      setConfirmListening(false);
    }
  }, []);

  const decide = useCallback(
    async (id: string, approved: boolean, fields?: { to: string; subject: string; body: string }) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setBusy(true);
      setConfirmListening(false);
      stopListening();
      silence();
      const focusedKind = pending.find((p) => p.id === id)?.kind || "";
      const syncFields =
        fields ||
        (focusedKind === "email_compose" || composeDraft?.id === id
          ? composeFieldsRef.current
          : undefined);
      if (approved) {
        setSending(true);
        showVoice(focusedKind === "email_compose" || focusedKind === "email_send" || focusedKind === "quote_send" ? "Sending…" : "Working…");
        setAgentStates(["ops"], "active");
        pushLog("OPS.04", "Executing authorized action…");
      }
      try {
        if (approved && syncFields && (focusedKind === "email_compose" || composeDraft?.id === id)) {
          await api.updatePending(id, syncFields, sessionRef.current);
        }
        const result = await api.confirm(id, approved, sessionRef.current);
        setSending(false);
        if (approved) {
          setPending([]);
          pendingIdRef.current = "";
        }
        applyResponse(result, { fromConfirm: true, approved });
        void refreshDesk(activeConversationId);
      } catch (err) {
        setSending(false);
        // Restore pending from server so HUD doesn't strand without Authorize
        try {
          const waiting = await api.pending(sessionRef.current);
          const items = waiting.items || [];
          setPending(items);
          pendingIdRef.current = items[0]?.id || "";
        } catch {
          /* ignore */
        }
        setError(err instanceof Error ? err.message : "Confirm failed");
        pushLog("SYS", "Confirm failed.");
        showVoice("That did not go through. Awaiting instruction.");
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [activeConversationId, applyResponse, composeDraft?.id, pending, pushLog, refreshDesk, setAgentStates, showVoice],
  );

  useEffect(() => {
    decideRef.current = decide;
  }, [decide]);

  useEffect(() => {
    listenConfirmRef.current = listenForConfirm;
  }, [listenForConfirm]);

  const send = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text || busyRef.current) return;

      const decision = pendingIdRef.current ? classifyDecision(text) : null;
      const words = text.trim().split(/\s+/).filter(Boolean).length;
      if (decision && pendingIdRef.current && words <= 5) {
        await decide(pendingIdRef.current, decision === "yes");
        setCompose("");
        return;
      }

      busyRef.current = true;
      setBusy(true);
      setCompose("");
      setError("");
      stopListening();
      setListening(false);

      const busyIds = inferBusyAgents(text);
      setAgentStates(busyIds, "active");
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
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [activeConversationId, applyResponse, clearAgents, decide, pushLog, refreshDesk, setAgentStates, showVoice],
  );

  useEffect(() => {
    sendRef.current = send;
  }, [send]);

  const startMic = useCallback(async () => {
    if (busyRef.current || (hitl && !composeNeedsInput) || !canListen()) return;
    stopListening();
    setListening(true);
    try {
      await startListening({
        onPartial: (text) => setCompose(text),
        onFinal: (text) => {
          setListening(false);
          setCompose("");
          void send(text);
        },
        onEnd: () => setListening(false),
        onError: (message) => {
          setListening(false);
          setError(message);
        },
      });
    } catch (err) {
      setListening(false);
      setError(err instanceof Error ? err.message : "Microphone unavailable");
    }
  }, [composeNeedsInput, hitl, send]);

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
      if (pendingIdRef.current && !typing && !busyRef.current) {
        if (event.key === "y" || event.key === "Y") {
          event.preventDefault();
          void decide(pendingIdRef.current, true);
          return;
        }
        if (event.key === "n" || event.key === "N") {
          event.preventDefault();
          void decide(pendingIdRef.current, false);
          return;
        }
      }
      if (event.code === "Space" && !typing && !(hitl && !composeNeedsInput) && !busyRef.current) {
        event.preventDefault();
        void startMic();
      }
      if (event.key === "Escape") {
        stopListening();
        setListening(false);
        setConfirmListening(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [composeNeedsInput, decide, hitl, startMic]);

  const startNewDiscussion = useCallback(async () => {
    if (busyRef.current) return;
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
      if (busyRef.current) return;
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
            voiceVisible ? "translate-y-0 opacity-100" : "translate-y-2.5 opacity-0",
          ].join(" ")}
        >
          <VoiceLine text={voice} dimmed={Boolean(hitlAction)} />
        </div>
        {scene.title || (scene.widgets || []).length ? (
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
