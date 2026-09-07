"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { canListen, claimGlanceSpeech, classifyDecision, silence, speak, startListening, startWakeWatch, stopListening, stopWakeWatch } from "@/lib/voice";
import type { Artifact, AuditEntry, ChatResponse, Health, PendingAction, Preferences, Scene } from "@/lib/types";
import { ArtifactTray } from "./ArtifactTray";
import { Composer } from "./Composer";
import { ConfirmBar } from "./ConfirmBar";
import { SceneBoard } from "./SceneBoard";
import { VoiceOrb } from "./VoiceOrb";

const EMPTY_SCENE: Scene = { title: "", subtitle: null, widgets: [] };

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
  const [input, setInput] = useState("");
  const [compose, setCompose] = useState(false);
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
  const fileTimer = useRef<number | null>(null);
  const lastWhisper = useRef("");
  const lastWatchSpeak = useRef("");
  const idleSince = useRef(Date.now());
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
        }, 900);
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
    const onVis = () => setPageOpen(document.visibilityState === "visible");
    onVis();
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => () => stopListening(), []);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false, ollama: false, model: "unknown", models: [] }));
    void refreshSide().then(async () => {
      if (pendingIdRef.current) listenForConfirm.current(pendingIdRef.current);
      try {
        const last = await api.session();
        if (!last?.scene?.title && !last?.speak) return;
        applyResponse(
          {
            speak: last.speak || "",
            reply: last.reply || last.speak || "",
            scene: last.scene || EMPTY_SCENE,
            artifacts: last.artifacts || [],
            pending: last.pending || [],
            offline: Boolean(last.offline),
            more: last.more || 0,
            watching: Boolean(last.watching),
          },
          false,
        );
      } catch {
        /* first launch has no saved board */
      }
    });
  }, [refreshSide, applyResponse]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await api.glance();
        if (cancelled) return;
        setGlance(next.line || "");
        const geminiReady = Boolean(next.key?.startsWith("gemini:") && next.speak);
        const occupied =
          busyRef.current ||
          listeningRef.current ||
          composeRef.current ||
          hotRef.current ||
          pendingRef.current ||
          moreRef.current > 0;
        const current = replyRef.current;
        const holdingGlance = !current || current === lastWhisper.current;
        if (!geminiReady && (occupied || !holdingGlance)) return;
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

  useEffect(() => {
    if (!pageOpen || busy || listening || compose || talking || pending.length || more || watching || panel !== "none") {
      stopWakeWatch();
      return;
    }
    if (!canListen()) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      void startWakeWatch({
        name: () => nameRef.current,
        onHot: () => {
          if (!cancelled) setHot(true);
        },
        onWake: (rest) => {
          if (!cancelled) handleWake.current(rest);
        },
      });
    }, 550);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      stopWakeWatch();
    };
  }, [pageOpen, busy, listening, compose, talking, pending.length, more, watching, panel]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await api.watch();
        if (cancelled) return;
        if (next.watching) setWatching(true);
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
        applyResponse(
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
  }, [applyResponse]);

  const send = useCallback(async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
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
    setInput("");
    setReply("…");
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
  }, [applyResponse, busy, refreshSide]);

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
      setReply("");
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
        stopListening();
        setListening(false);
        setHot(false);
        setCompose(false);
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
      if (!typing && !compose && event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        silence();
        setCompose(true);
        setInput(event.key);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [compose, decide, startListen]);

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
        <SceneBoard scene={scene} dense={density} />
      </main>

      <footer className="relative z-10 flex shrink-0 flex-col items-center gap-3 border-t border-white/5 bg-[#020508] px-6 pb-8 pt-3">
        <p className="whisper max-h-16 max-w-2xl overflow-auto text-center text-xl text-white/70">
          {error || reply}
        </p>
        <Composer value={input} onChange={setInput} onSubmit={() => send(input)} busy={busy} open={compose} />
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
  const [status, setStatus] = useState<{ configured: boolean; connected: boolean; account: string } | null>(null);
  useEffect(() => {
    api.googleStatus().then(setStatus).catch(() => setStatus(null));
  }, []);
  if (!status) return null;
  return (
    <div className="border-t border-white/10 pt-4 text-sm text-white/50">
      <p>Gmail</p>
      <p className="mt-1 text-white/70">
        {status.connected ? `Connected as ${status.account}` : status.configured ? "Not connected" : "Add Google client keys to .env"}
      </p>
      {status.configured && !status.connected ? (
        <a href={api.googleAuthUrl()} className="mt-2 inline-block text-cyan">Connect Gmail</a>
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
