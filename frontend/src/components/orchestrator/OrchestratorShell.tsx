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
import { HitlModal } from "./HitlModal";
import { JarvisCore } from "./JarvisCore";
import { Orchestra } from "./Orchestra";

const SESSION = "default";
const IDLE_VOICE = "Awaiting instruction.";

function highlightAuthorization(text: string): string {
  return text.replace(
    /(authorization required|authorize|shall i)/gi,
    '<span class="text-[color:var(--accent)]">$1</span>',
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

  const busyRef = useRef(false);
  const pendingIdRef = useRef("");
  const voiceEnabledRef = useRef(true);
  const speakToken = useRef(0);
  const decideRef = useRef<(id: string, approved: boolean) => Promise<void>>(async () => undefined);
  const listenConfirmRef = useRef<(actionId: string) => Promise<void>>(async () => undefined);

  const focused = pending[0] || null;
  const hitl = Boolean(focused);
  const mode: OrchestratorMode = hitl ? "hitl" : busy ? "busy" : listening ? "listening" : "idle";

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

      const line = (result.speak || result.reply || "").trim() || IDLE_VOICE;
      showVoice(line);

      if (waiting[0]) {
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
      } else {
        clearAgents();
      }

      if (result.scene?.title) {
        pushLog("SYS", result.scene.title);
      }

      speakToken.current += 1;
      const token = speakToken.current;
      if (voiceEnabledRef.current && result.speak) {
        speak(result.speak, true, () => {
          if (token !== speakToken.current) return;
          if (pendingIdRef.current) {
            void listenConfirmRef.current(pendingIdRef.current);
          }
        });
      } else if (waiting[0]) {
        void listenConfirmRef.current(waiting[0].id);
      }
    },
    [clearAgents, pushLog, setAgentStates, showVoice],
  );

  const listenForConfirm = useCallback(async (actionId: string) => {
    if (!canListen() || !actionId) return;
    stopListening();
    setConfirmListening(true);
    try {
      await startListening({
        onFinal: (text) => {
          const decision = classifyDecision(text);
          if (decision && pendingIdRef.current === actionId) {
            setConfirmListening(false);
            void decideRef.current(actionId, decision === "yes");
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
    async (id: string, approved: boolean) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setBusy(true);
      setConfirmListening(false);
      stopListening();
      silence();
      try {
        const result = await api.confirm(id, approved, SESSION);
        applyResponse(result, { fromConfirm: true, approved });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Confirm failed");
        pushLog("SYS", "Confirm failed.");
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [applyResponse, pushLog],
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
      if (decision && pendingIdRef.current) {
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

  const startMic = useCallback(async () => {
    if (busyRef.current || hitl || !canListen()) return;
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
  }, [hitl, send]);

  useEffect(() => {
    setVoiceVisible(true);
    let cancelled = false;
    (async () => {
      try {
        const [preferences, waiting, session, conversations] = await Promise.all([
          api.preferences().catch(() => null),
          api.pending(SESSION).catch(() => ({ items: [] as PendingAction[] })),
          api.session(SESSION).catch(() => null),
          api.conversations().catch(() => ({ items: [] as Conversation[] })),
        ]);
        if (cancelled) return;
        if (preferences) {
          setPrefs(preferences);
          voiceEnabledRef.current = preferences.voice_enabled !== false;
        }
        const items = waiting.items || [];
        setPending(items);
        pendingIdRef.current = items[0]?.id || "";
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
      if (event.code === "Space" && !typing && !hitl && !busyRef.current) {
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
  }, [decide, hitl, startMic]);

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
        <h1
          className={[
            "orch-voice max-w-[800px] text-center font-display text-[2.25rem] font-normal leading-snug tracking-[-0.01em] transition-all duration-[600ms]",
            voiceVisible ? "translate-y-0 opacity-100" : "translate-y-2.5 opacity-0",
            hitl ? "opacity-20 blur-[2px]" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          dangerouslySetInnerHTML={{ __html: highlightAuthorization(voice) }}
        />
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
        action={focused}
        visible={hitl}
        listening={confirmListening}
        busy={busy}
        onDecide={(id, approved) => void decide(id, approved)}
      />
    </div>
  );
}
