"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ChatResponse, Conversation, PendingAction, Preferences } from "@/lib/types";
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
import { ActivityStream } from "./ActivityStream";
import { CommandBaton } from "./CommandBaton";
import { ConversationRail, type RailConversation } from "./ConversationRail";
import { DraftComposeModal } from "./DraftComposeModal";
import { HitlModal } from "./HitlModal";
import { JarvisCore } from "./JarvisCore";
import { Orchestra } from "./Orchestra";
import { SuggestedTasksPanel, type SuggestedTask } from "./SuggestedTasksPanel";

const SESSION = "default";
const IDLE_VOICE = "Awaiting instruction.";

function VoiceLine({ text, dimmed }: { text: string; dimmed?: boolean }) {
  const compact = text.length > 220 || text.split("\n").length > 4;
  const parts = text.split(/(authorization required|authorize to send|authorize|shall i)/gi);
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
      {parts.map((part, index) =>
        /^(authorization required|authorize to send|authorize|shall i)$/i.test(part) ? (
          <span key={index} className="text-[color:var(--accent)]">
            {part}
          </span>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </h1>
  );
}

export function OrchestratorShell() {
  const [voice, setVoice] = useState(IDLE_VOICE);
  const [voiceVisible, setVoiceVisible] = useState(false);
  const [compose, setCompose] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [confirmListening, setConfirmListening] = useState(false);
  const [agents, setAgents] = useState<AgentNode[]>(DEFAULT_AGENTS);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [pending, setPending] = useState<PendingAction[]>([]);
  const [rail, setRail] = useState<RailConversation[]>([]);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [suggested, setSuggested] = useState<SuggestedTask[]>([]);
  const [weatherLine, setWeatherLine] = useState("");

  const busyRef = useRef(false);
  const pendingIdRef = useRef("");
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

  const applyResponse = useCallback(
    (result: ChatResponse, opts?: { fromConfirm?: boolean; approved?: boolean }) => {
      const waiting = result.pending || [];
      setPending(waiting);
      pendingIdRef.current = waiting[0]?.id || "";

      // Prefer reply for on-screen HUD text; speak stays short for TTS
      const display = (result.reply || result.speak || "").trim() || IDLE_VOICE;
      const tts = (result.speak || result.reply || "").trim();
      showVoice(display);

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
          await api.updatePending(id, syncFields, SESSION);
        }
        const result = await api.confirm(id, approved, SESSION);
        setSending(false);
        if (approved) {
          setPending([]);
          pendingIdRef.current = "";
        }
        applyResponse(result, { fromConfirm: true, approved });
      } catch (err) {
        setSending(false);
        // Restore pending from server so HUD doesn't strand without Authorize
        try {
          const waiting = await api.pending(SESSION);
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
    [applyResponse, composeDraft?.id, pending, pushLog, setAgentStates, showVoice],
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
        const result = await api.chat(text, SESSION);
        applyResponse(result);
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
    [applyResponse, clearAgents, decide, pushLog, setAgentStates, showVoice],
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
        const [preferences, waiting, session, conversations, tasks] = await Promise.all([
          api.preferences().catch(() => null),
          api.pending(SESSION).catch(() => ({ items: [] as PendingAction[] })),
          api.session(SESSION).catch(() => null),
          api.conversations().catch(() => ({ items: [] as Conversation[] })),
          // Fast path: do not block HUD on Gmail/weather refresh
          api.suggestedTasks(false, SESSION).catch(() => ({ items: [], weather: undefined })),
        ]);
        if (cancelled) return;
        if (preferences) {
          setPrefs(preferences);
          voiceEnabledRef.current = preferences.voice_enabled !== false;
        }
        const items = waiting.items || [];
        setPending(items);
        pendingIdRef.current = items[0]?.id || "";
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
        // Background refresh — never blocks first paint
        void api
          .officeRefresh(SESSION)
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
        if (session?.speak) showVoice(session.speak);
        if (items[0]) {
          const agentId = agentForPending(items[0]);
          setAgentStates([agentId], "waiting");
          pushLog(agentCode(agentId), "Pending authorization restored.");
        }
        setRail(
          (conversations.items || []).slice(0, 3).map((row) => ({
            id: row.id,
            title: row.title || row.category || "Conversation",
            time: row.updated_at
              ? new Date(row.updated_at).toLocaleTimeString("en-US", {
                  hour: "numeric",
                  minute: "2-digit",
                })
              : undefined,
            preview: row.speak || row.turns?.slice(-1)[0]?.content || "",
            minimized: true,
          })),
        );
      } catch {
        /* offline bootstrap is fine for UI shell */
      }
    })();
    return () => {
      cancelled = true;
      stopListening();
      silence();
    };
  }, [pushLog, setAgentStates, showVoice]);

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

  return (
    <div className="orch-root relative flex h-screen flex-col overflow-hidden">
      <div className="orch-vignette" />
      <JarvisCore mode={mode} />

      <ActivityStream items={activity} />

      <ConversationRail
        items={rail}
        dimmed={hitl}
        onToggle={(id) =>
          setRail((prev) =>
            prev.map((row) => (row.id === id ? { ...row, minimized: !row.minimized } : row)),
          )
        }
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
        {prefs?.assistant_name ? (
          <p className="mt-6 font-mono text-[10px] uppercase tracking-[0.2em] text-[color:var(--muted)]/50">
            {prefs.assistant_name}
          </p>
        ) : null}
      </main>

      <Orchestra agents={agents} dimmed={hitl} />

      {!hitl ? (
        <SuggestedTasksPanel
          tasks={suggested}
          weather={weatherLine}
          onDismiss={(id) => {
            void api.setSuggestedTaskStatus(id, "dismissed").catch(() => null);
            setSuggested((prev) => prev.filter((t) => t.id !== id));
          }}
          onAction={(task, actionId) => {
            if (task.kind === "rfq" && actionId === "engineering") {
              void send(`Start engineering review and quote for task ${task.id}`);
            } else if (actionId === "calendar" || actionId === "meeting") {
              void send(`Create a calendar event for: ${task.title}`);
            } else if (actionId === "chat" || actionId === "review") {
              void send(`Let's discuss: ${task.title}`);
            } else {
              void send(`${actionId} for suggested task: ${task.title}`);
            }
          }}
        />
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
    </div>
  );
}
