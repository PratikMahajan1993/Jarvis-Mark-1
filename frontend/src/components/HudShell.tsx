"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { canListen, claimGlanceSpeech, classifyDecision, isWakeWatching, silence, speak, startListening, startWakeWatch, stopListening, stopWakeWatch } from "@/lib/voice";
import type { Artifact, AuditEntry, ChatResponse, Conversation, CriticalAlert, Health, MailAttachment, PendingAction, Preferences, RfqPublic, Scene } from "@/lib/types";
import { ArtifactTray } from "./ArtifactTray";
import { Composer } from "./Composer";
import { ConfirmBar } from "./ConfirmBar";
import { ConversationDock } from "./ConversationDock";
import { DrawingViewer } from "./DrawingViewer";
import { SceneBoard } from "./SceneBoard";
import { CriticalStrip, deriveCritical } from "./Widgets";
import { VoiceOrb } from "./VoiceOrb";
import {
  conversationToAttachment,
  isSavedLocal,
  isViewCommand,
  matchViewAttachment,
  parseViewerCommand,
  sceneAttachments,
  type ViewerCommand,
} from "@/lib/viewerMatch";
import { matchConversation, namesConversation, parseWindowCommand } from "@/lib/conversationVoice";
import { Alert, HudButton, Panel, StatCard, StatusDot } from "./hud/Hud";

const EMPTY_SCENE: Scene = { title: "", subtitle: null, widgets: [] };
const ALWAYS_ON_MIC_KEY = "jarvis.alwaysOnMic";
const IDLE_SCENE_MS = 8000;

function readAlwaysOnMic(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.localStorage.getItem(ALWAYS_ON_MIC_KEY) !== "false";
  } catch {
    return true;
  }
}

function Clock({ timezone }: { timezone: string }) {
  const [now, setNow] = useState("");
  useEffect(() => {
    const tick = () => {
      try {
        setNow(new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: timezone }).format(new Date()));
      } catch {
        setNow(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
      }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => clearInterval(id);
  }, [timezone]);
  return <span className="font-display text-lg tracking-[0.2em] text-white/50">{now}</span>;
}

export function HudShell() {
  const [compose, setCompose] = useState(false);
  const [turns, setTurns] = useState<{ role: string; text: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [scene, setScene] = useState<Scene>(EMPTY_SCENE);
  const [reply, setReply] = useState("");
  const [glance, setGlance] = useState("");
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [showFiles, setShowFiles] = useState(false);
  const [pending, setPending] = useState<PendingAction[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [panel, setPanel] = useState<"none" | "settings" | "audit">("none");
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [hot, setHot] = useState(false);
  const [more, setMore] = useState(0);
  const [watching, setWatching] = useState(false);
  const [pageOpen, setPageOpen] = useState(true);
  const [talking, setTalking] = useState(false);
  const [alwaysOnMic, setAlwaysOnMic] = useState(readAlwaysOnMic);
  const [viewerAttachment, setViewerAttachment] = useState<MailAttachment | null>(null);
  const [viewerVoiceCmd, setViewerVoiceCmd] = useState<ViewerCommand | null>(null);
  const [viewerVoiceSeq, setViewerVoiceSeq] = useState(0);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [dockHidden, setDockHidden] = useState(false);
  const [spawnAsk, setSpawnAsk] = useState<PendingAction | null>(null);
  const [convBusyId, setConvBusyId] = useState<string | null>(null);
  const [dismissedCriticalId, setDismissedCriticalId] = useState<string | null>(null);
  const [rfqs, setRfqs] = useState<RfqPublic[]>([]);
  const [glanceCritical, setGlanceCritical] = useState<CriticalAlert | null>(null);
  const [chatCritical, setChatCritical] = useState<CriticalAlert | null>(null);
  const fileTimer = useRef<number | null>(null);
  const lastWhisper = useRef("");
  const lastWatchSpeak = useRef("");
  const idleSince = useRef(Date.now());
  const announceAt = useRef(Date.now() + 20000);
  const restored = useRef(false);
  const applyResponseRef = useRef<(result: ChatResponse, spoken?: boolean) => void>(() => {});
  const voiceEnabledRef = useRef(true);
  const busyRef = useRef(false);
  const listeningRef = useRef(false);
  const composeRef = useRef(false);
  const hotRef = useRef(false);
  const pendingRef = useRef(false);
  const replyRef = useRef("");
  const pendingIdRef = useRef("");
  const speakToken = useRef(0);
  const confirmGen = useRef(0);
  const moreRef = useRef(0);
  const listenForConfirm = useRef<(actionId: string) => void>(() => {});
  const advanceThought = useRef<() => void>(() => {});
  const nameRef = useRef("Jarvis");
  const handleWake = useRef<(rest: string) => void>(() => {});
  const sceneRef = useRef(scene);
  const viewerRef = useRef<MailAttachment | null>(null);
  const conversationsRef = useRef<Conversation[]>([]);
  const focusedRef = useRef<string | null>(null);
  const spawnAskRef = useRef<PendingAction | null>(null);
  const dockHiddenRef = useRef(false);
  const commandPendingRef = useRef(false);
  const talkingRef = useRef(false);
  const convBusyRef = useRef<string | null>(null);

  sceneRef.current = scene;
  viewerRef.current = viewerAttachment;
  conversationsRef.current = conversations;
  focusedRef.current = focusedId;
  spawnAskRef.current = spawnAsk;
  dockHiddenRef.current = dockHidden;

  const applyResponse = useCallback((result: ChatResponse, spoken = true) => {
    setScene(result.scene || EMPTY_SCENE);
    setReply(result.speak || result.reply || "");
    setArtifacts(result.artifacts || []);
    setPending(result.pending || []);
    const pendingId = result.pending?.[0]?.id || "";
    pendingIdRef.current = pendingId;
    moreRef.current = result.more || 0;
    setMore(result.more || 0);
    setWatching(Boolean(result.watching));
    if ("critical" in result) {
      setChatCritical(result.critical ?? null);
    }
    setShowFiles((result.artifacts || []).length > 0);
    if (result.speak) {
      setTurns((current) => [...current.slice(-4), { role: "jarvis", text: result.speak }]);
    }
    if (fileTimer.current) window.clearTimeout(fileTimer.current);
    fileTimer.current = window.setTimeout(() => setShowFiles(false), 12000);
    const token = ++speakToken.current;
    let armed = false;
    const afterSpeak = () => {
      if (armed || token !== speakToken.current) return;
      armed = true;
      if (pendingId && pendingIdRef.current === pendingId) {
        window.setTimeout(() => {
          if (token !== speakToken.current || pendingIdRef.current !== pendingId) return;
          listenForConfirm.current(pendingId);
        }, 400);
        return;
      }
      if (moreRef.current > 0) {
        window.setTimeout(() => {
          if (token !== speakToken.current) return;
          advanceThought.current();
        }, 200);
      }
    };
    if (result.speak && spoken && prefs?.voice_enabled !== false) {
      setTalking(true);
      speak(result.speak, true, () => {
        afterSpeak();
        setTalking(false);
      });
      window.setTimeout(() => {
        afterSpeak();
        setTalking(false);
      }, 8000);
    } else {
      afterSpeak();
      setTalking(false);
    }
  }, [prefs?.voice_enabled]);
  applyResponseRef.current = applyResponse;

  const refreshSide = useCallback(async () => {
    try {
      const [prefData, auditData, artifactData, waiting] = await Promise.all([
        api.preferences(),
        api.audit(),
        api.artifacts(),
        api.pending(),
      ]);
      setPrefs(prefData);
      setAudit(auditData.items);
      setArtifacts(artifactData.items);
      setPending(waiting.items || []);
      pendingIdRef.current = waiting.items?.[0]?.id || "";
    } catch {
      /* HUD still works */
    }
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const listed = await api.conversations();
      setConversations(listed.items || []);
    } catch {
      /* dock is optional */
    }
  }, []);

  const refreshRfqs = useCallback(async () => {
    const listed = await api.listRfqs();
    setRfqs(listed.items || []);
  }, []);

  useEffect(() => {
    busyRef.current = busy;
    listeningRef.current = listening;
    composeRef.current = compose;
    hotRef.current = hot;
    talkingRef.current = talking;
    convBusyRef.current = convBusyId;
    pendingRef.current = pending.length > 0 || Boolean(spawnAsk);
    commandPendingRef.current = pending.length > 0;
    pendingIdRef.current = pending[0]?.id || spawnAsk?.id || pendingIdRef.current;
    if (!pending.length && !spawnAsk) pendingIdRef.current = "";
    replyRef.current = reply;
    voiceEnabledRef.current = prefs?.voice_enabled !== false;
    if (busy || listening || compose || pending.length || spawnAsk || talking || convBusyId) idleSince.current = Date.now();
  }, [busy, listening, compose, hot, pending, spawnAsk, reply, prefs?.voice_enabled, talking, convBusyId]);

  useEffect(() => {
    const occupied = busy || listening || talking || compose || hot || pending.length > 0 || Boolean(spawnAsk) || Boolean(convBusyId);
    const hasBoard = Boolean(scene?.title) || (scene?.widgets || []).length > 0;
    const hasReply = Boolean(reply) && !error;
    if (occupied || (!hasBoard && !hasReply)) return;
    const timer = window.setTimeout(() => {
      if (
        busyRef.current ||
        listeningRef.current ||
        composeRef.current ||
        hotRef.current ||
        pendingRef.current ||
        spawnAskRef.current ||
        talkingRef.current ||
        convBusyRef.current
      ) {
        return;
      }
      setScene((current) => {
        if (!current?.title && !(current?.widgets || []).length) return current;
        return EMPTY_SCENE;
      });
      if (!error) {
        setReply((current) => (current ? "" : current));
      }
    }, IDLE_SCENE_MS);
    return () => window.clearTimeout(timer);
  }, [busy, listening, talking, compose, hot, pending, spawnAsk, convBusyId, scene, reply, error]);

  useEffect(() => {
    nameRef.current = prefs?.assistant_name || "Jarvis";
  }, [prefs?.assistant_name]);

  useEffect(() => {
    const onVis = () => {
      const open = document.visibilityState === "visible";
      setPageOpen(open);
      if (open) {
        idleSince.current = Date.now();
        announceAt.current = Math.max(announceAt.current, Date.now() + 8000);
      }
    };
    onVis();
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => () => stopListening(), []);

  useEffect(() => {
    let cancelled = false;
    api.health().then(setHealth).catch(() => setHealth({ ok: false, ollama: false, model: "unknown", models: [] }));
    void refreshSide().then(async () => {
      if (cancelled) return;
      await refreshConversations();
      await refreshRfqs();
      try {
        const last = await api.session();
        if (cancelled) return;
        if (last?.scene?.title || last?.reply || last?.critical) {
          applyResponseRef.current(
            {
              speak: "",
              reply: last.reply || "",
              scene: last.scene || EMPTY_SCENE,
              artifacts: last.artifacts || [],
              pending: last.pending || [],
              offline: Boolean(last.offline),
              more: 0,
              watching: false,
              critical: last.critical ?? null,
            },
            false,
          );
        }
      } catch {
        /* first launch has no saved board */
      }
      try {
        await api.ackWatch();
      } catch {
        /* no live watch */
      }
      if (cancelled) return;
      restored.current = true;
      announceAt.current = Date.now() + 20000;
      idleSince.current = Date.now();
    });
    return () => {
      cancelled = true;
    };
  }, [refreshSide, refreshConversations, refreshRfqs]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (!cancelled) void refreshRfqs();
      try {
        const next = await api.glance();
        if (cancelled) return;
        setGlance(next.line || "");
        setGlanceCritical(next.critical ?? null);
        if (!restored.current || Date.now() < announceAt.current) return;
        const geminiReady = Boolean(next.key?.startsWith("gemini:") && next.speak);
        const occupied =
          busyRef.current ||
          listeningRef.current ||
          composeRef.current ||
          hotRef.current ||
          pendingRef.current ||
          moreRef.current > 0 ||
          Boolean(viewerRef.current);
        const current = replyRef.current;
        const holdingGlance = !current || current === lastWhisper.current;
        if (geminiReady) {
          stopListening();
          setListening(false);
          setHot(false);
          if (next.whisper && next.whisper !== lastWatchSpeak.current) {
            lastWhisper.current = next.whisper;
            setReply(next.whisper);
          }
          return;
        }
        if (occupied || !holdingGlance) return;
        if (next.whisper) {
          lastWhisper.current = next.whisper;
          setReply(next.whisper);
        }
        if (
          next.speak &&
          next.key &&
          voiceEnabledRef.current &&
          Date.now() - idleSince.current > 800 &&
          claimGlanceSpeech(next.key)
        ) {
          speak(next.speak, true);
        }
      } catch {
        /* glance is optional */
      }
    };
    tick();
    const id = window.setInterval(tick, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [refreshRfqs]);

  const toggleAlwaysOnMic = useCallback(() => {
    setAlwaysOnMic((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(ALWAYS_ON_MIC_KEY, String(next));
      } catch {
        /* ignore */
      }
      if (!next) {
        stopWakeWatch();
        setHot(false);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (!alwaysOnMic) {
      stopWakeWatch();
      setHot(false);
      return;
    }
    if (!pageOpen || busy || listening || talking || pending.length || spawnAsk || more || watching || panel !== "none") {
      stopWakeWatch();
      return;
    }
    if (!canListen()) return;
    let cancelled = false;
    let delay = 0;
    const arm = (immediate: boolean) => {
      if (cancelled) return;
      const start = () => {
        if (cancelled) return;
        void startWakeWatch({
          name: () => nameRef.current,
          onHot: () => {
            if (!cancelled) setHot(true);
          },
          onWake: (rest) => {
            if (!cancelled) handleWake.current(rest);
          },
          onError: (message) => {
            if (!cancelled && message) setError(message);
          },
        });
      };
      if (immediate) {
        start();
        return;
      }
      window.clearTimeout(delay);
      delay = window.setTimeout(start, 200);
    };
    arm(false);
    const onGesture = () => {
      if (cancelled || isWakeWatching()) return;
      arm(true);
    };
    window.addEventListener("pointerdown", onGesture);
    window.addEventListener("keydown", onGesture);
    return () => {
      cancelled = true;
      window.clearTimeout(delay);
      window.removeEventListener("pointerdown", onGesture);
      window.removeEventListener("keydown", onGesture);
      stopWakeWatch();
    };
  }, [alwaysOnMic, pageOpen, busy, listening, talking, pending.length, spawnAsk, more, watching, panel]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await api.watch();
        if (cancelled) return;
        if (next.watching) setWatching(true);
        if (!restored.current) {
          if (!next.watching && !next.ready) setWatching(false);
          return;
        }
        if (!next.ready || !next.speak) {
          if (!next.watching && !next.ready) setWatching(false);
          return;
        }
        const watchKey = next.key || `gemini:${next.status || "ready"}:${next.speak}`;
        const spoken = next.speak !== lastWatchSpeak.current && claimGlanceSpeech(watchKey);
        lastWatchSpeak.current = next.speak;
        lastWhisper.current = next.speak;
        if (spoken) {
          stopListening();
          setListening(false);
          setHot(false);
        }
        setWatching(false);
        applyResponseRef.current(
          {
            speak: next.speak,
            reply: next.speak,
            scene: next.scene || EMPTY_SCENE,
            artifacts: [],
            pending: [],
            offline: false,
            more: 0,
            watching: false,
          },
          spoken,
        );
        try {
          await api.ackWatch();
        } catch {
          /* already shown */
        }
      } catch {
        /* watch is optional */
      }
    };
    tick();
    const id = window.setInterval(tick, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const whisper = useCallback((line: string) => {
    lastWhisper.current = line;
    setReply(line);
  }, []);

  const closeViewer = useCallback(() => {
    setViewerAttachment(null);
    setViewerVoiceCmd(null);
  }, []);

  const openViewer = useCallback((item: MailAttachment) => {
    setViewerAttachment(item);
    setViewerVoiceCmd(null);
    const existing = conversationsRef.current.find((row) => {
      if (row.category !== "drawing") return false;
      const focus = row.focus || {};
      return (
        (item.local_name && focus.local_name === item.local_name) ||
        (item.filename && focus.filename === item.filename)
      );
    });
    if (existing) {
      setDockHidden(false);
      setFocusedId(existing.id);
      void api.patchConversation(existing.id, { minimized: false }).then(() => refreshConversations());
      whisper(`Viewing ${item.local_name || item.filename}.`);
      return;
    }
    if (isSavedLocal(item)) {
      const pending: PendingAction = {
        id: "spawn-drawing",
        kind: "start_conversation",
        title: "Keep a conversation on this drawing?",
        summary: item.local_name || item.filename,
        payload: { ...item },
      };
      setSpawnAsk(pending);
      const line = "Shall I keep a conversation on this drawing?";
      whisper(line);
      if (voiceEnabledRef.current) speak(line, true);
      return;
    }
    whisper(`Viewing ${item.local_name || item.filename}.`);
  }, [refreshConversations, whisper]);

  const decideSpawn = useCallback(async (approved: boolean) => {
    const ask = spawnAskRef.current;
    setSpawnAsk(null);
    if (!approved) {
      whisper("Alright.");
      return;
    }
    const payload = (ask?.payload || {}) as MailAttachment;
    speakToken.current += 1;
    setBusy(true);
    setConvBusyId("spawn");
    try {
      const created = await api.spawnDrawingConversation({
        filename: payload.filename,
        local_name: payload.local_name || payload.filename,
        local_path: payload.local_path || "",
        mime: payload.mime,
        drive_link: payload.drive_link || "",
      });
      setDockHidden(false);
      setFocusedId(created.id);
      await refreshConversations();
      const line = created.speak || "The drawing is in focus.";
      whisper(line);
      if (voiceEnabledRef.current) speak(line, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "I could not start that conversation.");
    } finally {
      setBusy(false);
      setConvBusyId(null);
    }
  }, [refreshConversations, whisper]);

  const runViewerVoice = useCallback(
    (text: string): boolean => {
      const cmd = parseViewerCommand(text);
      if (cmd) {
        if (cmd === "close") {
          closeViewer();
          whisper("Closed.");
          return true;
        }
        setViewerVoiceCmd(cmd);
        setViewerVoiceSeq((seq) => seq + 1);
        return true;
      }
      return false;
    },
    [closeViewer, whisper],
  );

  const tryViewCommand = useCallback(
    (text: string): boolean => {
      if (!isViewCommand(text)) return false;
      const fromScene = sceneAttachments(sceneRef.current);
      const fromConv = conversationsRef.current
        .filter((row) => row.category === "drawing")
        .map((row) => conversationToAttachment(row.focus))
        .filter((item): item is MailAttachment => Boolean(item));
      const seen = new Set(fromScene.map((item) => item.local_name || item.filename));
      const items = [...fromScene, ...fromConv.filter((item) => !seen.has(item.local_name || item.filename))];
      if (!items.length) return false;
      const { attachment, whisper: line } = matchViewAttachment(text, items);
      if (line) {
        whisper(line);
        if (voiceEnabledRef.current) speak(line, true);
        return true;
      }
      if (attachment) {
        openViewer(attachment);
        return true;
      }
      return false;
    },
    [openViewer, whisper],
  );

  const runWindowCommand = useCallback((text: string): boolean => {
    const cmd = parseWindowCommand(text);
    if (!cmd) return false;
    if (cmd.action === "hide_dock") {
      setDockHidden(true);
      whisper("Conversations hidden.");
      return true;
    }
    if (cmd.action === "show_dock") {
      setDockHidden(false);
      whisper("Conversations are on the right.");
      return true;
    }
    const row = matchConversation(cmd.query, conversationsRef.current);
    if (!row) {
      whisper("I do not have that window.");
      return true;
    }
    if (cmd.action === "minimize") {
      void api.patchConversation(row.id, { minimized: true }).then(() => refreshConversations());
      if (focusedRef.current === row.id) setFocusedId(null);
      whisper(`Minimized ${row.title}.`);
      return true;
    }
    setDockHidden(false);
    void api.patchConversation(row.id, { minimized: false }).then(() => refreshConversations());
    setFocusedId(row.id);
    whisper(`${row.title} is open.`);
    return true;
  }, [refreshConversations, whisper]);

  const interceptMessage = useCallback(
    (text: string): boolean => {
      if (viewerRef.current) {
        const viewerCmd = parseViewerCommand(text);
        const windowCmd = parseWindowCommand(text);
        if (viewerCmd && !windowCmd) return runViewerVoice(text);
      }
      if (runWindowCommand(text)) return true;
      if (spawnAskRef.current && !commandPendingRef.current && classifyDecision(text)) {
        void decideSpawn(classifyDecision(text) === "yes");
        return true;
      }
      return tryViewCommand(text);
    },
    [decideSpawn, runViewerVoice, runWindowCommand, tryViewCommand],
  );

  const send = useCallback(async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    if (interceptMessage(message)) return;
    const waiting = pendingIdRef.current;
    const decision = waiting ? classifyDecision(message) : null;
    const named = namesConversation(message, conversationsRef.current);
    const commandRoom = /\b(mail|inbox|calendar|schedule|brief|briefing|catch me up)\b/i.test(message);
    const target = !decision && !commandRoom ? named || conversationsRef.current.find((row) => row.id === focusedRef.current) : null;
    const threadPending = target?.pending?.[0];
    const threadDecision = threadPending ? classifyDecision(message) : null;
    speakToken.current += 1;
    confirmGen.current += 1;
    setBusy(true);
    setError("");
    setCompose(false);
    silence();
    stopListening();
    setListening(false);
    setHot(false);
    setReply("…");
    if (!target) {
      setTurns((current) => [...current.slice(-4), { role: "you", text: message }]);
    } else {
      setFocusedId(target.id);
      setConvBusyId(target.id);
    }
    try {
      const result =
        decision !== null && waiting
          ? await api.confirm(waiting, decision === "yes")
          : threadDecision && threadPending && target
            ? await api.confirm(threadPending.id, threadDecision === "yes", target.session_id)
            : await api.chat(message, target?.session_id || "default");
      if (target) {
        await refreshConversations();
        if ("critical" in result) setChatCritical(result.critical ?? null);
        whisper(result.speak || result.reply || "");
        if (voiceEnabledRef.current && result.speak) speak(result.speak, true);
      } else {
        applyResponse(result);
      }
      await refreshSide();
      await refreshRfqs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "I could not reach the house systems.");
    } finally {
      setBusy(false);
      setConvBusyId(null);
    }
  }, [applyResponse, busy, interceptMessage, refreshConversations, refreshRfqs, refreshSide, whisper]);

  const runAttachmentAction = useCallback(
    async (kind: "save" | "reply", emailId: string, attachmentIds: string[], filenames: string[]) => {
      if (!emailId || !filenames.length || busy) return;
      speakToken.current += 1;
      setBusy(true);
      setError("");
      try {
        const result =
          kind === "save"
            ? await api.saveMailAttachments(emailId, attachmentIds, filenames)
            : await api.replyWithAttachments(emailId, attachmentIds, filenames);
        applyResponse(result);
        await refreshSide();
        await refreshRfqs();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Attachment action failed.");
      } finally {
        setBusy(false);
      }
    },
    [applyResponse, busy, refreshRfqs, refreshSide],
  );

  const decide = useCallback(async (id: string, approved: boolean) => {
    if (id === "spawn-drawing") {
      await decideSpawn(approved);
      return;
    }
    speakToken.current += 1;
    confirmGen.current += 1;
    silence();
    stopListening();
    setListening(false);
    setBusy(true);
    try {
      const result = await api.confirm(id, approved);
      applyResponse(result);
      await refreshSide();
      await refreshRfqs();
    } finally {
      setBusy(false);
    }
  }, [applyResponse, decideSpawn, refreshRfqs, refreshSide]);

  const sendToConversation = useCallback(async (id: string, message: string) => {
    const row = conversationsRef.current.find((item) => item.id === id);
    if (!row || !message.trim()) return;
    setFocusedId(id);
    setConvBusyId(id);
    setBusy(true);
    try {
      const result = await api.chat(message.trim(), row.session_id);
      await refreshConversations();
      if ("critical" in result) setChatCritical(result.critical ?? null);
      await refreshRfqs();
      whisper(result.speak || result.reply || "");
      if (voiceEnabledRef.current && result.speak) speak(result.speak, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That conversation did not answer.");
    } finally {
      setBusy(false);
      setConvBusyId(null);
    }
  }, [refreshConversations, refreshRfqs, whisper]);

  const confirmConversation = useCallback(async (id: string, actionId: string, approved: boolean) => {
    const row = conversationsRef.current.find((item) => item.id === id);
    if (!row) return;
    setConvBusyId(id);
    setBusy(true);
    try {
      const result = await api.confirm(actionId, approved, row.session_id);
      await refreshConversations();
      if ("critical" in result) setChatCritical(result.critical ?? null);
      await refreshRfqs();
      whisper(result.speak || result.reply || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "I could not confirm that.");
    } finally {
      setBusy(false);
      setConvBusyId(null);
    }
  }, [refreshConversations, refreshRfqs, whisper]);

  advanceThought.current = () => {
    if (busyRef.current || pendingIdRef.current || composeRef.current || listeningRef.current) return;
    void (async () => {
      setBusy(true);
      try {
        const next = await api.nextThought();
        if (!next.scene?.title && !(next.scene?.widgets || []).length) {
          moreRef.current = 0;
          setMore(0);
          return;
        }
        applyResponse(next);
      } finally {
        setBusy(false);
      }
    })();
  };

  listenForConfirm.current = (actionId: string) => {
    if (busyRef.current || !canListen()) return;
    const gen = ++confirmGen.current;
    setCompose(false);
    setError("");
    setListening(true);
    setReply("Listening…");
    void startListening({
      onPartial: (text) => {
        if (gen !== confirmGen.current) return;
        setReply(text);
      },
      onFinal: (text) => {
        if (gen !== confirmGen.current) return;
        setListening(false);
        setReply(text);
        const decision = classifyDecision(text);
        if (decision && pendingIdRef.current === actionId) {
          void decide(actionId, decision === "yes");
          return;
        }
        listenForConfirm.current(actionId);
      },
      onError: (message) => {
        if (gen !== confirmGen.current) return;
        setListening(false);
        if (message) setError(message);
      },
      onEnd: () => {
        if (gen !== confirmGen.current) return;
        setListening(false);
      },
    });
  };

  const beginCommand = useCallback(async (prompt = "Listening…") => {
    if (busy) return;
    if (!canListen()) {
      setCompose(true);
      setError("Type. Voice needs Chrome.");
      return;
    }
    if (pendingIdRef.current) {
      listenForConfirm.current(pendingIdRef.current);
      return;
    }
    silence();
    setCompose(false);
    setError("");
    setHot(false);
    setListening(true);
    setReply(prompt);
    const timeout = window.setTimeout(() => {
      if (!listeningRef.current) return;
      stopListening();
      setListening(false);
      setHot(false);
      const line = "I didn't catch that.";
      setReply(line);
      if (voiceEnabledRef.current) speak(line, true);
    }, 12000);
    await startListening({
      onPartial: (text) => setReply(text),
      onFinal: (text) => {
        window.clearTimeout(timeout);
        setListening(false);
        setReply(text);
        void send(text);
      },
      onError: (message) => {
        window.clearTimeout(timeout);
        setListening(false);
        setHot(false);
        if (message) setError(message);
      },
      onEnd: () => {
        window.clearTimeout(timeout);
        setListening(false);
        setHot(false);
      },
    });
  }, [busy, send]);

  handleWake.current = (rest: string) => {
    speakToken.current += 1;
    confirmGen.current += 1;
    silence();
    setHot(false);
    if (rest) {
      setListening(false);
      if (interceptMessage(rest)) return;
      void send(rest);
      return;
    }
    setListening(true);
    setReply("Yes?");
    if (prefs?.voice_enabled !== false) {
      speak("Yes?", true, () => {
        void beginCommand("Listening…");
      });
      return;
    }
    void beginCommand("Listening…");
  };

  const startListen = useCallback(async () => {
    if (listening) {
      confirmGen.current += 1;
      stopListening();
      setListening(false);
      setHot(false);
      setReply("");
      return;
    }
    await beginCommand("Listening…");
  }, [beginCommand, listening]);

  const onDrop = async (file: File) => {
    setDragging(false);
    try {
      const uploaded = await api.uploadInbox(file);
      const preview = (uploaded.preview || "").trim();
      if (preview.length < 40) {
        setReply(`I have ${uploaded.name}, but there is no readable text.`);
      }
      await send(`I dropped a file named ${uploaded.name}. Review the dropped file.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "I could not read that file.");
    }
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      const typing = target.tagName === "INPUT" || target.tagName === "TEXTAREA";
      if (event.key === "Escape") {
        confirmGen.current += 1;
        speakToken.current += 1;
        silence();
        if (listeningRef.current) {
          stopListening();
          setListening(false);
        }
        setHot(false);
        setCompose(false);
        if (viewerRef.current) {
          closeViewer();
          if (typing) target.blur();
          return;
        }
        if (typing) target.blur();
        setPanel("none");
        setError("");
        return;
      }
      if (pendingIdRef.current && !typing) {
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
      if (event.key === "," && !typing) {
        event.preventDefault();
        setPanel((current) => (current === "settings" ? "none" : "settings"));
        return;
      }
      if (event.key === "." && !typing) {
        event.preventDefault();
        setPanel((current) => (current === "audit" ? "none" : "audit"));
        return;
      }
      if (event.code === "Space" && !typing && !compose) {
        event.preventDefault();
        startListen();
        return;
      }
      if (pendingIdRef.current) return;
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeViewer, compose, decide, startListen]);

  const mood = listening || hot ? "listen" : busy ? "think" : "idle";
  const density = prefs?.hud_density === "dense";
  const critical = deriveCritical(conversations, focusedId, { glanceCritical, chatCritical, rfqs });
  const showCritical = Boolean(critical && critical.sourceId !== dismissedCriticalId);

  return (
    <div
      className="hud-bg relative flex h-screen flex-col overflow-hidden"
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        const file = event.dataTransfer.files[0];
        if (file) onDrop(file);
      }}
    >
      <div className="hud-grid absolute inset-0" />
      <div className="scanline absolute inset-0" />

      <header className="relative z-10 flex shrink-0 items-start justify-between gap-4 px-8 py-4">
        <button
          type="button"
          onClick={() => {
            setPanel("settings");
            setFocusedId(null);
          }}
          className="hud-panel hud-accent-cyan px-4 py-1.5 font-display text-sm uppercase tracking-[0.3em] text-white/50 transition-colors hover:text-cyan"
        >
          {(prefs?.assistant_name || "Jarvis").toUpperCase()}
        </button>
        <div className="flex items-center gap-3">
          {glance ? <p className="hidden max-w-xs truncate text-xs text-white/25 md:block">{glance}</p> : null}
          <StatCard
            label="Mic"
            accent={alwaysOnMic ? "cyan" : "white"}
            value={
              <button
                type="button"
                onClick={toggleAlwaysOnMic}
                className="flex items-center gap-1.5 transition-colors"
                aria-pressed={alwaysOnMic}
                aria-label={alwaysOnMic ? "Always-on mic on" : "Always-on mic off"}
                title={
                  alwaysOnMic
                    ? "Always listening for wake word — click to turn off"
                    : "Wake word off — press Space or tap the orb to listen"
                }
              >
                <StatusDot accent={alwaysOnMic ? "cyan" : "white"} pulse={alwaysOnMic} />
                {alwaysOnMic ? "Always on" : "Off"}
              </button>
            }
          />
          <StatCard label="Local time" accent="violet" value={<Clock timezone={prefs?.timezone || "Asia/Kolkata"} />} />
          <button type="button" onClick={() => setPanel("audit")} aria-label="Systems">
            <StatCard
              label="Systems"
              accent={health?.model_ready ? "green" : "amber"}
              value={
                <span className="flex items-center gap-1.5">
                  <StatusDot accent={health?.model_ready ? "green" : "amber"} pulse />
                  {health?.model_ready ? "Nominal" : "Degraded"}
                </span>
              }
            />
          </button>
        </div>
      </header>

      <div className="relative z-0 flex min-h-0 flex-1">
        <main className="min-h-0 min-w-0 flex-1 overflow-auto" onClick={() => setFocusedId(null)}>
          {showCritical && critical ? (
            <div className="px-6 pb-2 pt-1" onClick={(event) => event.stopPropagation()}>
              <CriticalStrip
                item={critical}
                onDismiss={() => setDismissedCriticalId(critical.sourceId)}
              />
            </div>
          ) : null}
          <SceneBoard
            scene={scene}
            dense={density}
            busy={busy}
            onSaveAttachments={(emailId, attachmentIds, filenames) => void runAttachmentAction("save", emailId, attachmentIds, filenames)}
            onReplyAttachments={(emailId, attachmentIds, filenames) => void runAttachmentAction("reply", emailId, attachmentIds, filenames)}
            onViewAttachment={openViewer}
          />
        </main>
        <ConversationDock
          conversations={conversations}
          rfqs={rfqs}
          focusedId={focusedId}
          busyId={convBusyId}
          hidden={dockHidden}
          onFocus={setFocusedId}
          onMinimize={(id) => {
            void api.patchConversation(id, { minimized: true }).then(() => refreshConversations());
            if (focusedId === id) setFocusedId(null);
          }}
          onExpand={(id) => {
            setDockHidden(false);
            setFocusedId(id);
            void api.patchConversation(id, { minimized: false }).then(() => refreshConversations());
          }}
          onSend={(id, message) => void sendToConversation(id, message)}
          onConfirm={(id, actionId, approved) => void confirmConversation(id, actionId, approved)}
        />
      </div>

      <footer className="relative z-10 flex shrink-0 flex-col items-center gap-3 border-t border-white/5 bg-[#020508] px-6 pb-8 pt-4">
        {error || reply ? (
          <Alert
            tone={error ? "error" : listening ? "warn" : "info"}
            className="whisper max-h-16 max-w-2xl overflow-auto text-center"
          >
            <span className="text-lg">{error || reply}</span>
          </Alert>
        ) : null}
        {turns.length ? (
          <p className="max-w-2xl text-center font-mono text-[11px] leading-5 text-white/25">
            {turns.slice(-3).map((turn, index) => (
              <span key={`${turn.role}-${index}`}>
                {index ? " · " : ""}
                {turn.role === "you" ? "You" : "Jarvis"}: {turn.text.slice(0, 72)}
                {turn.text.length > 72 ? "…" : ""}
              </span>
            ))}
          </p>
        ) : null}
        {focusedId ? (
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-cyan/40">
            {conversations.find((row) => row.id === focusedId)?.title || "Conversation"} in focus
          </p>
        ) : null}
        <Composer
          onSubmit={(value) => void send(value)}
          onFocusChange={setCompose}
          busy={busy}
        />
        <div onMouseEnter={() => artifacts.length && setShowFiles(true)}>
          <VoiceOrb mood={mood} onClick={startListen} />
        </div>
        {showFiles ? (
          <div className="w-full max-w-3xl" onMouseLeave={() => setShowFiles(false)}>
            <ArtifactTray items={artifacts} />
          </div>
        ) : null}
      </footer>

      {dragging ? (
        <div className="pointer-events-none absolute inset-0 grid place-items-center bg-cyan/5 text-white/40">
          Leave it with me
        </div>
      ) : null}

      <ConfirmBar
        actions={pending.length ? pending : spawnAsk ? [spawnAsk] : []}
        onDecide={decide}
        listening={listening}
      />

      {viewerAttachment ? (
        <DrawingViewer
          attachment={viewerAttachment}
          onClose={closeViewer}
          onWhisper={whisper}
          onSaved={async () => {
            await refreshSide();
          }}
          voiceCommand={viewerVoiceCmd}
          voiceSeq={viewerVoiceSeq}
        />
      ) : null}

      {panel !== "none" ? (
        <div className="absolute inset-0 z-20 bg-black/55" onClick={() => setPanel("none")}>
          <div className="ml-auto h-full max-w-md" onClick={(event) => event.stopPropagation()}>
            <Panel
              accent={panel === "settings" ? "cyan" : "violet"}
              className="h-full overflow-auto rounded-none border-y-0 border-r-0"
              bodyClassName="p-8"
              eyebrow={panel === "settings" ? "Configuration" : "Activity log"}
              title={panel === "settings" ? "Preferences" : "What I have done"}
              right={
                <HudButton variant="ghost" className="py-1" onClick={() => setPanel("none")}>
                  Close
                </HudButton>
              }
            >
              {panel === "settings" && prefs ? (
                <SettingsForm
                  prefs={prefs}
                  onSave={async (next) => {
                    const saved = await api.updatePreferences(next);
                    setPrefs(saved);
                  }}
                />
              ) : (
                <ul className="space-y-4 text-sm">
                  {audit.map((entry) => (
                    <li key={entry.id} className="border-l-2 border-violet/25 pl-3">
                      <p className="text-white/80">{entry.tool}</p>
                      <p className="text-white/40">{entry.detail}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function GoogleConnect() {
  const [status, setStatus] = useState<{
    configured: boolean;
    connected: boolean;
    calendar?: boolean;
    calendar_list?: boolean;
    account: string;
  } | null>(null);
  useEffect(() => {
    api.googleStatus().then(setStatus).catch(() => setStatus(null));
  }, []);
  if (!status) return null;
  const calendarOn = Boolean(status.calendar);
  const allCalendars = Boolean(status.calendar_list);
  return (
    <div className="border-t border-white/10 pt-4 text-sm text-white/50">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-cyan/60">Google</p>
      <p className="mt-1 text-white/70">
        {status.connected
          ? `Connected as ${status.account}${calendarOn ? " · Calendar on" : " · Calendar needs reconnect"}${calendarOn && !allCalendars ? " · primary only" : ""}`
          : status.configured
            ? "Not connected"
            : "Add Google client keys to .env"}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {status.configured && !status.connected ? (
          <HudButton variant="primary" onClick={() => { window.location.href = api.googleAuthUrl(); }}>
            Connect Gmail
          </HudButton>
        ) : null}
        {status.connected && !calendarOn ? (
          <HudButton variant="primary" onClick={() => { window.location.href = api.googleAuthUrl(); }}>
            Add Calendar
          </HudButton>
        ) : null}
        {status.connected && calendarOn && !allCalendars ? (
          <HudButton variant="ghost" onClick={() => { window.location.href = api.googleAuthUrl(); }}>
            Allow all calendars
          </HudButton>
        ) : null}
      </div>
    </div>
  );
}

function SettingsForm({
  prefs,
  onSave,
}: {
  prefs: Preferences;
  onSave: (next: Partial<Preferences>) => Promise<void>;
}) {
  const [draft, setDraft] = useState(prefs);
  useEffect(() => setDraft(prefs), [prefs]);
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSave(draft);
      }}
    >
      {(
        [
          ["display_name", "What I call you"],
          ["assistant_name", "What you call me"],
          ["persona", "How I should be"],
          ["job_context", "Your work"],
          ["sign_off", "How I sign letters"],
          ["timezone", "Timezone"],
        ] as const
      ).map(([key, label]) => (
        <label key={key} className="block text-sm">
          <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/40">{label}</span>
          <input
            value={String(draft[key])}
            onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
            className="mt-1.5 w-full border border-white/10 bg-white/[0.02] px-3 py-2 outline-none transition-colors focus:border-cyan/50"
          />
        </label>
      ))}
      {(
        [
          ["voice_enabled", "Speak aloud — also listens for your name"],
          ["email_enabled", "Mail"],
          ["calendar_enabled", "Calendar"],
          ["files_enabled", "Files"],
          ["research_enabled", "Research"],
        ] as const
      ).map(([key, label]) => (
        <label key={key} className="flex items-center justify-between text-sm text-white/50">
          {label}
          <input
            type="checkbox"
            checked={Boolean(draft[key])}
            onChange={(event) => setDraft({ ...draft, [key]: event.target.checked })}
          />
        </label>
      ))}
      <GoogleConnect />
      <HudButton type="submit" variant="primary" className="mt-2">
        Remember this
      </HudButton>
    </form>
  );
}
