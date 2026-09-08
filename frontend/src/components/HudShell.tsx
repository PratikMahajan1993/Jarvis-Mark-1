"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { canListen, claimGlanceSpeech, classifyDecision, isWakeWatching, silence, speak, startListening, startWakeWatch, stopListening, stopWakeWatch } from "@/lib/voice";
import type { Artifact, AuditEntry, ChatResponse, Health, MailAttachment, PendingAction, Preferences, Scene } from "@/lib/types";
import { ArtifactTray } from "./ArtifactTray";
import { Composer } from "./Composer";
import { ConfirmBar } from "./ConfirmBar";
import { DrawingViewer } from "./DrawingViewer";
import { SceneBoard } from "./SceneBoard";
import { VoiceOrb } from "./VoiceOrb";
import {
  isViewCommand,
  matchViewAttachment,
  parseViewerCommand,
  sceneAttachments,
  type ViewerCommand,
} from "@/lib/viewerMatch";

const EMPTY_SCENE: Scene = { title: "", subtitle: null, widgets: [] };
const ALWAYS_ON_MIC_KEY = "jarvis.alwaysOnMic";

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

  sceneRef.current = scene;
  viewerRef.current = viewerAttachment;

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

  useEffect(() => {
    busyRef.current = busy;
    listeningRef.current = listening;
    composeRef.current = compose;
    hotRef.current = hot;
    pendingRef.current = pending.length > 0;
    replyRef.current = reply;
    voiceEnabledRef.current = prefs?.voice_enabled !== false;
    if (busy || listening || compose || pending.length) idleSince.current = Date.now();
  }, [busy, listening, compose, hot, pending, reply, prefs?.voice_enabled]);

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
      try {
        const last = await api.session();
        if (cancelled) return;
        if (last?.scene?.title || last?.reply) {
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
  }, [refreshSide]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await api.glance();
        if (cancelled) return;
        setGlance(next.line || "");
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
  }, []);

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
    if (!pageOpen || busy || listening || talking || pending.length || more || watching || panel !== "none") {
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
  }, [alwaysOnMic, pageOpen, busy, listening, talking, pending.length, more, watching, panel]);

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
    whisper(`Viewing ${item.local_name || item.filename}.`);
  }, [whisper]);

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
      const items = sceneAttachments(sceneRef.current);
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

  const interceptMessage = useCallback(
    (text: string): boolean => {
      if (viewerRef.current) return runViewerVoice(text);
      return tryViewCommand(text);
    },
    [runViewerVoice, tryViewCommand],
  );

  const send = useCallback(async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    if (interceptMessage(message)) return;
    const waiting = pendingIdRef.current;
    const decision = waiting ? classifyDecision(message) : null;
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
    setTurns((current) => [...current.slice(-4), { role: "you", text: message }]);
    try {
      const result = decision !== null && waiting
        ? await api.confirm(waiting, decision === "yes")
        : await api.chat(message);
      applyResponse(result);
      await refreshSide();
    } catch (err) {
      setError(err instanceof Error ? err.message : "I could not reach the house systems.");
    } finally {
      setBusy(false);
    }
  }, [applyResponse, busy, interceptMessage, refreshSide]);

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
      } catch (err) {
        setError(err instanceof Error ? err.message : "Attachment action failed.");
      } finally {
        setBusy(false);
      }
    },
    [applyResponse, busy, refreshSide],
  );

  const decide = useCallback(async (id: string, approved: boolean) => {
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
    } finally {
      setBusy(false);
    }
  }, [applyResponse, refreshSide]);

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
      <div className="scanline absolute inset-0" />

      <header className="relative z-10 flex shrink-0 items-start justify-between px-8 py-5">
        <button type="button" onClick={() => setPanel("settings")} className="text-white/20 hover:text-white/50">
          {prefs?.assistant_name || "Jarvis"}
        </button>
        <div className="flex items-center gap-4">
          {glance ? <p className="hidden text-sm text-white/25 md:block">{glance}</p> : null}
          <button
            type="button"
            onClick={toggleAlwaysOnMic}
            className={`flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] transition-colors ${
              alwaysOnMic ? "text-cyan/55 hover:text-cyan/80" : "text-white/25 hover:text-white/45"
            }`}
            aria-pressed={alwaysOnMic}
            aria-label={alwaysOnMic ? "Always-on mic on" : "Always-on mic off"}
            title={
              alwaysOnMic
                ? "Always listening for wake word — click to turn off"
                : "Wake word off — press Space or tap the orb to listen"
            }
          >
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                alwaysOnMic ? "bg-cyan/70" : "bg-white/20"
              }`}
            />
            {alwaysOnMic ? "Mic always on" : "Mic off"}
          </button>
          <Clock timezone={prefs?.timezone || "Asia/Kolkata"} />
          <button
            type="button"
            onClick={() => setPanel("audit")}
            className={`h-1.5 w-1.5 rounded-full ${health?.model_ready ? "bg-cyan/70" : "bg-amber/70"}`}
            aria-label="Systems"
          />
        </div>
      </header>

      <main className="relative z-0 min-h-0 flex-1 overflow-auto">
        <SceneBoard
          scene={scene}
          dense={density}
          busy={busy}
          onSaveAttachments={(emailId, attachmentIds, filenames) => void runAttachmentAction("save", emailId, attachmentIds, filenames)}
          onReplyAttachments={(emailId, attachmentIds, filenames) => void runAttachmentAction("reply", emailId, attachmentIds, filenames)}
          onViewAttachment={openViewer}
        />
      </main>

      <footer className="relative z-10 flex shrink-0 flex-col items-center gap-3 border-t border-white/5 bg-[#020508] px-6 pb-8 pt-3">
        <p className="whisper max-h-16 max-w-2xl overflow-auto text-center text-xl text-white/70">
          {error || reply}
        </p>
        {turns.length ? (
          <p className="max-w-2xl text-center text-[11px] leading-5 text-white/25">
            {turns.slice(-3).map((turn, index) => (
              <span key={`${turn.role}-${index}`}>
                {index ? " · " : ""}
                {turn.role === "you" ? "You" : "Jarvis"}: {turn.text.slice(0, 72)}
                {turn.text.length > 72 ? "…" : ""}
              </span>
            ))}
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

      <ConfirmBar actions={pending} onDecide={decide} listening={listening} />

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
          <div className="glass ml-auto h-full max-w-md overflow-auto p-8" onClick={(event) => event.stopPropagation()}>
            <div className="mb-8 flex justify-between text-white/40">
              <p>{panel === "settings" ? "Preferences" : "What I have done"}</p>
              <button type="button" onClick={() => setPanel("none")}>Close</button>
            </div>
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
                  <li key={entry.id}>
                    <p className="text-white/80">{entry.tool}</p>
                    <p className="text-white/40">{entry.detail}</p>
                  </li>
                ))}
              </ul>
            )}
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
      <p>Google</p>
      <p className="mt-1 text-white/70">
        {status.connected
          ? `Connected as ${status.account}${calendarOn ? " · Calendar on" : " · Calendar needs reconnect"}${calendarOn && !allCalendars ? " · primary only" : ""}`
          : status.configured
            ? "Not connected"
            : "Add Google client keys to .env"}
      </p>
      {status.configured && !status.connected ? (
        <a href={api.googleAuthUrl()} className="mt-2 inline-block text-cyan">Connect Gmail</a>
      ) : null}
      {status.connected && !calendarOn ? (
        <a href={api.googleAuthUrl()} className="mt-2 inline-block text-cyan">Add Calendar</a>
      ) : null}
      {status.connected && calendarOn && !allCalendars ? (
        <a href={api.googleAuthUrl()} className="mt-2 block text-cyan">Allow all calendars</a>
      ) : null}
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
          <span className="text-white/40">{label}</span>
          <input
            value={String(draft[key])}
            onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
            className="mt-1 w-full border-b border-white/10 bg-transparent py-2 outline-none"
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
      <button type="submit" className="pt-4 text-cyan">Remember this</button>
    </form>
  );
}
