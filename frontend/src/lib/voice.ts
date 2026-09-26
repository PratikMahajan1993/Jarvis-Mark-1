type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      length: number;
      [alt: number]: { transcript: string };
    };
  };
};

const WORK_HINTS = [
  "spreadsheet",
  "excel",
  "calendar",
  "schedule",
  "email",
  "inbox",
  "draft",
  "reply",
  "document",
  "research",
  "brief",
  "pricing",
  "priya",
];

function scoreHeard(text: string): number {
  const lower = text.toLowerCase();
  let score = 0;
  for (const word of WORK_HINTS) {
    if (lower.includes(word)) score += 2;
  }
  if (/\b\w*sheet\b/.test(lower) && !lower.includes("spread")) score -= 1;
  return score;
}

function bestHeard(result: { length: number; [alt: number]: { transcript: string } }): string {
  let winner = result[0]?.transcript || "";
  let best = scoreHeard(winner);
  for (let i = 1; i < result.length; i += 1) {
    const text = result[i]?.transcript || "";
    const score = scoreHeard(text);
    if (score > best) {
      winner = text;
      best = score;
    }
  }
  return winner.trim();
}

type ListenHandlers = {
  onPartial?: (text: string) => void;
  onFinal?: (text: string) => void;
  onError?: (message: string) => void;
  onEnd?: () => void;
};

type WakeHandlers = {
  name: string | (() => string);
  onHot?: () => void;
  onWake: (rest: string) => void;
  onError?: (message: string) => void;
};

const ERRORS: Record<string, string> = {
  "not-allowed": "Chrome blocked the microphone for this page. Click the lock icon in the address bar and allow the mic.",
  "service-not-allowed": "Chrome blocked speech recognition for this page.",
  network: "Chrome needs the internet for voice. Check the connection and try again.",
  "audio-capture": "I cannot hear a microphone on this machine.",
  aborted: "",
  "no-speech": "",
};

let recognizer: SpeechRecognitionLike | null = null;
let micStream: MediaStream | null = null;
let armed = false;
let restarting = false;
let listenMode: "off" | "wake" | "command" = "off";
let deafUntil = 0;
let wakeConsumed = "";
let session = 0;
let wakeRestartTimer = 0;
let wakeWatchdog = 0;
let wakeHandlers: WakeHandlers | null = null;

function speechCtor(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function canListen(): boolean {
  return typeof window !== "undefined" && Boolean(speechCtor());
}

export async function micGranted(): Promise<boolean> {
  if (typeof navigator === "undefined" || !navigator.permissions) return false;
  try {
    const status = await navigator.permissions.query({ name: "microphone" as PermissionName });
    return status.state === "granted";
  } catch {
    return false;
  }
}

function escapeReg(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function wakeNames(name: string): string[] {
  const chosen = (name || "Jarvis").trim() || "Jarvis";
  return [...new Set([chosen, "Jarvis", "Jarvish", "Jar vis", "Jarves", "Jervis", "Jarvice"])];
}

export function takeWake(text: string, name = "Jarvis"): { woke: boolean; rest: string } {
  const raw = text.trim();
  if (!raw) return { woke: false, rest: "" };
  const options = wakeNames(name).map(escapeReg).join("|");
  const re = new RegExp(`(?:^|[\\s,;:]+)(?:hey |ok |okay |hi |hello )?(${options})\\b[?!,.\\s]*`, "i");
  const padded = ` ${raw}`;
  const match = padded.match(re);
  if (!match || match.index === undefined) return { woke: false, rest: raw };
  const rest = padded.slice(match.index + match[0].length).trim().replace(/^[?!,.\s]+/, "");
  return { woke: true, rest };
}

function readLatest(event: SpeechRecognitionEventLike): { finalText: string; partial: string } {
  let finalText = "";
  let partial = "";
  for (let i = event.resultIndex; i < event.results.length; i += 1) {
    const piece = bestHeard(event.results[i]);
    if (!piece) continue;
    if (event.results[i]?.isFinal) finalText = finalText ? `${finalText} ${piece}` : piece;
    else partial = partial ? `${partial} ${piece}` : piece;
  }
  return { finalText: finalText.trim(), partial: partial.trim() };
}

function releaseMic() {
  micStream?.getTracks().forEach((track) => track.stop());
  micStream = null;
}

function friendlyError(code: string): string {
  if (code in ERRORS) return ERRORS[code];
  return `I could not listen (${code}).`;
}

function readTranscript(event: SpeechRecognitionEventLike): { finalText: string; partial: string } {
  let finalText = "";
  let partial = "";
  for (let i = 0; i < event.results.length; i += 1) {
    const piece = bestHeard(event.results[i]);
    if (event.results[i]?.isFinal) finalText += `${finalText ? " " : ""}${piece}`;
    else partial += `${partial ? " " : ""}${piece}`;
  }
  return { finalText: finalText.trim(), partial: partial.trim() };
}

export async function startListening(handlers: ListenHandlers): Promise<void> {
  const Ctor = speechCtor();
  if (!Ctor) {
    handlers.onError?.("This browser will not listen. Use Chrome.");
    return;
  }

  const mine = beginSession("command");

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (mine !== session) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    micStream = stream;
  } catch {
    if (mine !== session) return;
    armed = false;
    listenMode = "off";
    handlers.onError?.("Chrome did not get the microphone. Click the lock icon and allow the mic, then try again.");
    return;
  }

  const rec = new Ctor();
  recognizer = rec;
  rec.lang = navigator.language || "en-IN";
  rec.interimResults = true;
  rec.continuous = true;
  rec.maxAlternatives = 3;

  rec.onresult = (event) => {
    if (mine !== session || listenMode !== "command") return;
    const { finalText, partial } = readTranscript(event);
    if (partial) handlers.onPartial?.(partial);
    if (finalText) {
      armed = false;
      handlers.onFinal?.(finalText);
      try {
        rec.stop();
      } catch {
        /* already stopping */
      }
    }
  };

  rec.onerror = (event) => {
    if (mine !== session) return;
    if (event.error === "no-speech" || event.error === "aborted") return;
    armed = false;
    const message = friendlyError(event.error);
    if (message) handlers.onError?.(message);
  };

  rec.onend = () => {
    if (mine !== session) return;
    if (armed && recognizer === rec) {
      restarting = true;
      try {
        rec.start();
      } catch {
        armed = false;
        handlers.onEnd?.();
      }
      restarting = false;
      return;
    }
    if (!restarting) {
      if (recognizer === rec) {
        recognizer = null;
        releaseMic();
      }
      handlers.onEnd?.();
    }
  };

  try {
    rec.start();
  } catch (err) {
    if (mine !== session) return;
    armed = false;
    if (recognizer === rec) {
      recognizer = null;
      releaseMic();
    }
    handlers.onError?.(err instanceof Error ? err.message : "I could not start the microphone.");
  }
}

function clearWakeTimers() {
  if (wakeRestartTimer) {
    window.clearTimeout(wakeRestartTimer);
    wakeRestartTimer = 0;
  }
  if (wakeWatchdog) {
    window.clearInterval(wakeWatchdog);
    wakeWatchdog = 0;
  }
}

function beginSession(mode: "wake" | "command"): number {
  session += 1;
  armed = false;
  listenMode = "off";
  clearWakeTimers();
  const rec = recognizer;
  recognizer = null;
  try {
    rec?.abort();
  } catch {
    /* already stopped */
  }
  releaseMic();
  listenMode = mode;
  armed = true;
  return session;
}

export function stopListening() {
  session += 1;
  armed = false;
  listenMode = "off";
  wakeHandlers = null;
  clearWakeTimers();
  const rec = recognizer;
  recognizer = null;
  try {
    rec?.abort();
  } catch {
    /* already stopped */
  }
  releaseMic();
}

export function stopWakeWatch() {
  if (listenMode !== "wake") return;
  stopListening();
}

export function isWakeWatching(): boolean {
  return listenMode === "wake" && armed;
}

function currentName(name: string | (() => string)): string {
  return typeof name === "function" ? name() : name;
}

async function ensureMicPermission(): Promise<boolean> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    return true;
  } catch {
    return false;
  }
}

function heardWake(event: SpeechRecognitionEventLike, name: string): { woke: boolean; rest: string; hot: boolean } {
  const latest = readLatest(event);
  const all = readTranscript(event);
  const hotText = latest.partial || latest.finalText || all.partial;
  const hot = takeWake(hotText, name);
  const finalText = latest.finalText || all.finalText;
  if (!finalText) return { woke: false, rest: "", hot: hot.woke };
  const heard = takeWake(finalText, name);
  if (heard.woke) return { woke: true, rest: heard.rest, hot: true };
  return { woke: false, rest: "", hot: hot.woke };
}

function attachWakeRecognizer(mine: number, handlers: WakeHandlers) {
  const Ctor = speechCtor();
  if (!Ctor) return;
  if (mine !== session || listenMode !== "wake") return;

  try {
    recognizer?.abort();
  } catch {
    /* replace the dead instance */
  }

  const rec = new Ctor();
  recognizer = rec;
  rec.lang = navigator.language || "en-IN";
  rec.interimResults = true;
  rec.continuous = true;
  rec.maxAlternatives = 3;

  rec.onresult = (event) => {
    if (mine !== session || listenMode !== "wake" || Date.now() < deafUntil) return;
    const name = currentName(handlers.name);
    const heard = heardWake(event, name);
    if (heard.hot && !heard.woke) {
      handlers.onHot?.();
      return;
    }
    if (!heard.woke) return;
    const key = `${heard.rest}:${currentName(handlers.name)}`;
    if (key === wakeConsumed) return;
    wakeConsumed = key;
    armed = false;
    listenMode = "off";
    clearWakeTimers();
    handlers.onWake(heard.rest);
    try {
      rec.stop();
    } catch {
      /* already stopping */
    }
  };

  rec.onerror = (event) => {
    if (mine !== session || listenMode !== "wake") return;
    if (event.error === "no-speech" || event.error === "aborted") return;
    const message = friendlyError(event.error);
    if (event.error === "network") {
      scheduleWakeRestart(mine, handlers);
      return;
    }
    armed = false;
    if (message) handlers.onError?.(message);
  };

  rec.onend = () => {
    if (mine !== session) return;
    if (armed && listenMode === "wake") {
      scheduleWakeRestart(mine, handlers);
      return;
    }
    if (recognizer === rec) recognizer = null;
  };

  try {
    rec.start();
    armed = true;
    listenMode = "wake";
  } catch {
    scheduleWakeRestart(mine, handlers);
  }
}

function scheduleWakeRestart(mine: number, handlers: WakeHandlers) {
  if (mine !== session) return;
  listenMode = "wake";
  if (wakeRestartTimer) window.clearTimeout(wakeRestartTimer);
  wakeRestartTimer = window.setTimeout(() => {
    wakeRestartTimer = 0;
    if (mine !== session) return;
    listenMode = "wake";
    armed = true;
    attachWakeRecognizer(mine, handlers);
  }, 220);
}

export async function startWakeWatch(handlers: WakeHandlers): Promise<void> {
  const Ctor = speechCtor();
  if (!Ctor) return;
  if (listenMode === "wake" && armed && recognizer) {
    wakeHandlers = handlers;
    return;
  }

  const mine = beginSession("wake");
  wakeHandlers = handlers;
  wakeConsumed = "";
  deafUntil = Math.min(deafUntil, Date.now() + 350);

  const allowed = await ensureMicPermission();
  if (mine !== session) return;
  if (!allowed) {
    armed = false;
    listenMode = "off";
    handlers.onError?.("Chrome did not get the microphone. Click the lock icon and allow the mic, then say Jarvis again.");
    return;
  }
  await new Promise((resolve) => window.setTimeout(resolve, 80));
  if (mine !== session) return;

  attachWakeRecognizer(mine, handlers);
  if (wakeWatchdog) window.clearInterval(wakeWatchdog);
  wakeWatchdog = window.setInterval(() => {
    if (mine !== session || listenMode !== "wake") return;
    if (recognizer && armed) return;
    armed = true;
    attachWakeRecognizer(mine, handlers);
  }, 3000);
}

const YES_SHORT = new Set([
  "y", "yes", "yeah", "yep", "yup", "yea", "confirm", "send", "send it", "do it",
  "go ahead", "proceed", "affirmative", "yes please", "yes send it", "yeah do it",
  "yes do it", "go for it", "do that", "ship it", "do so", "that's a yes", "thats a yes",
  "authorize", "authorise", "authorize it", "authorise it", "authorize to send",
  "authorise to send", "send the email", "send the mail", "send email", "send mail",
]);
const NO_SHORT = new Set([
  "n", "no", "nope", "nah", "cancel", "stop", "dont", "don't", "do not", "never",
  "reject", "negative", "abort", "wait", "no thanks", "no thank you", "not now",
  "hold on", "leave it", "later", "not yet", "hold off", "dont send", "don't send",
  "do not send", "discard", "throw it away",
]);

export function classifyDecision(text: string): "yes" | "no" | null {
  const cleaned = text.toLowerCase().trim().replace(/[!.?,]/g, "").replace(/\s+/g, " ").replace(/'/g, "");
  if (!cleaned) return null;
  const words = cleaned.split(/\s+/).filter(Boolean);
  const no = new Set([...NO_SHORT].map((item) => item.replace(/'/g, "")));
  const yes = new Set([...YES_SHORT].map((item) => item.replace(/'/g, "")));
  if (no.has(cleaned)) return "no";
  if (yes.has(cleaned)) return "yes";
  // Long utterances are body/content, not authorize/reject.
  if (words.length > 6) return null;
  if (/\b(dont|do not|reject|cancel|discard|nope|nah|abort)\b/.test(cleaned) || /(?:^|\s)no(?:\s|$)/.test(cleaned)) {
    if (!/\b(yes|authorize|authorise)\b/.test(cleaned)) return "no";
  }
  if (/\b(authorize|authorise|send it|send the (?:e-?mail|mail)|go ahead|ship it|yes)\b/.test(cleaned)) {
    if (!/\b(dont|do not|reject)\b/.test(cleaned)) return "yes";
  }
  return null;
}

const GLANCE_STORE = "jarvis.spokenGlance";
const spokenGlanceKeys = new Set<string>();
let glanceStoreLoaded = false;
let activeAudio: HTMLAudioElement | null = null;
let activeSource: AudioBufferSourceNode | null = null;
let playbackCtx: AudioContext | null = null;
let unlockAudio: HTMLAudioElement | null = null;
let speakSeq = 0;
let speakAbort: AbortController | null = null;

const SILENT_WAV =
  "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

function playbackContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor =
    window.AudioContext ||
    (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!playbackCtx) playbackCtx = new Ctor();
  return playbackCtx;
}

/** Call from a click or keypress so a later Voicebox clip is allowed to play. */
export function primeVoicePlayback() {
  if (typeof window === "undefined") return;
  const ctx = playbackContext();
  if (ctx && ctx.state !== "running") void ctx.resume();
  if (!unlockAudio) {
    unlockAudio = new Audio();
    unlockAudio.setAttribute("playsinline", "true");
  }
  if (!unlockAudio.paused) return;
  unlockAudio.src = SILENT_WAV;
  void unlockAudio.play().then(() => unlockAudio?.pause()).catch(() => undefined);
}

if (typeof window !== "undefined") {
  const prime = () => primeVoicePlayback();
  window.addEventListener("pointerdown", prime, true);
  window.addEventListener("keydown", prime, true);
}

function apiRoot(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
}

function stopSource() {
  if (!activeSource) return;
  try {
    activeSource.onended = null;
    activeSource.stop();
  } catch {
    /* already stopped */
  }
  activeSource = null;
}

function stopAudio() {
  speakAbort?.abort();
  speakAbort = null;
  stopSource();
  if (activeAudio) {
    try {
      activeAudio.onended = null;
      activeAudio.onerror = null;
      activeAudio.pause();
      const src = activeAudio.src;
      activeAudio.removeAttribute("src");
      activeAudio.load();
      if (src.startsWith("blob:")) URL.revokeObjectURL(src);
    } catch {
      /* ignore */
    }
    activeAudio = null;
  }
}

function loadGlanceStore() {
  if (glanceStoreLoaded || typeof window === "undefined") return;
  glanceStoreLoaded = true;
  try {
    const raw = window.localStorage.getItem(GLANCE_STORE);
    if (!raw) return;
    const keys = JSON.parse(raw) as string[];
    for (const key of keys.slice(-80)) spokenGlanceKeys.add(key);
  } catch {
    /* ignore */
  }
}

export function claimGlanceSpeech(key: string): boolean {
  if (!key) return false;
  loadGlanceStore();
  if (spokenGlanceKeys.has(key)) return false;
  spokenGlanceKeys.add(key);
  try {
    window.localStorage.setItem(GLANCE_STORE, JSON.stringify([...spokenGlanceKeys].slice(-80)));
  } catch {
    /* ignore */
  }
  return true;
}

/** Fetch Voicebox WAV only — caller decides whether to play. */
async function fetchVoicebox(text: string, seq: number): Promise<Blob | null> {
  if (typeof window === "undefined") return null;
  const controller = new AbortController();
  speakAbort = controller;
  try {
    const response = await fetch(`${apiRoot()}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: controller.signal,
    });
    if (!response.ok) return null;
    const blob = await response.blob();
    if (seq !== speakSeq) return null;
    return blob;
  } catch (err) {
    if ((err as { name?: string })?.name === "AbortError") return null;
    return null;
  } finally {
    if (speakAbort === controller) speakAbort = null;
  }
}

function playVoiceboxBlob(blob: Blob, onEnd: (() => void) | undefined, seq: number) {
  const ctx = playbackContext();
  if (ctx) {
    void blob
      .arrayBuffer()
      .then(async (raw) => {
        if (seq !== speakSeq) return;
        if (ctx.state !== "running") await ctx.resume();
        if (seq !== speakSeq) return;
        const decoded = await ctx.decodeAudioData(raw.slice(0));
        if (seq !== speakSeq) return;
        stopSource();
        const source = ctx.createBufferSource();
        source.buffer = decoded;
        source.connect(ctx.destination);
        activeSource = source;
        source.onended = () => {
          if (activeSource !== source) return;
          activeSource = null;
          deafUntil = Date.now() + 500;
          onEnd?.();
        };
        source.start(0);
      })
      .catch(() => {
        if (seq !== speakSeq) return;
        playVoiceboxElement(blob, onEnd);
      });
    return;
  }
  playVoiceboxElement(blob, onEnd);
}

function playVoiceboxElement(blob: Blob, onEnd?: () => void) {
  const url = URL.createObjectURL(blob);
  const audio = unlockAudio ?? new Audio();
  if (!unlockAudio) unlockAudio = audio;
  audio.src = url;
  activeAudio = audio;
  let finished = false;
  const done = () => {
    if (finished) return;
    finished = true;
    if (activeAudio === audio) activeAudio = null;
    URL.revokeObjectURL(url);
    deafUntil = Date.now() + 500;
    onEnd?.();
  };
  audio.onended = done;
  audio.onerror = done;
  void audio.play().catch(() => done());
}

export function isSpeaking(): boolean {
  return Boolean(activeAudio || activeSource) || Date.now() < deafUntil;
}

let lastSpokenText = "";
let lastSpokenAt = 0;

type QueuedSentence = {
  text: string;
  enabled: boolean;
  onEnd?: () => void;
};

const sentenceQueue: QueuedSentence[] = [];
const speechIdleWaiters: Array<() => void> = [];
let queueHold = false;
let speechGen = 0;

function speechBusy(): boolean {
  return queueHold || Boolean(activeAudio || activeSource) || sentenceQueue.length > 0;
}

function drainSpeechQueue(gen: number) {
  if (gen !== speechGen) return;
  queueHold = false;
  const next = sentenceQueue.shift();
  if (next) {
    speak(next.text, next.enabled, next.onEnd, { force: true, queue: true });
    return;
  }
  const waiters = speechIdleWaiters.splice(0);
  waiters.forEach((fn) => fn());
}

/** Drop queued sentences. A new turn or cancel must not keep the previous clip's tail. */
export function resetSpeechQueue() {
  speechGen += 1;
  queueHold = false;
  sentenceQueue.length = 0;
  speechIdleWaiters.length = 0;
  silence();
}

export function whenSpeechIdle(callback: () => void) {
  if (!speechBusy()) {
    callback();
    return;
  }
  speechIdleWaiters.push(callback);
}

export function speak(
  text: string,
  enabled = true,
  onEnd?: () => void,
  options?: { force?: boolean; queue?: boolean },
) {
  if (!enabled || !text || typeof window === "undefined") {
    onEnd?.();
    return;
  }
  const queued = Boolean(options?.queue);
  if (queued && speechBusy()) {
    sentenceQueue.push({ text, enabled, onEnd });
    return;
  }
  const gen = speechGen;
  if (queued) queueHold = true;
  else {
    speechGen += 1;
    sentenceQueue.length = 0;
    queueHold = false;
  }
  const end = () => {
    onEnd?.();
    if (queued) drainSpeechQueue(gen);
  };
  const force = Boolean(options?.force);
  if (!force && activeAudio && text === lastSpokenText && performance.now() - lastSpokenAt < 2500) {
    end();
    return;
  }
  if (!force && text === lastSpokenText && performance.now() - lastSpokenAt < 90000) {
    end();
    return;
  }
  lastSpokenText = text;
  lastSpokenAt = performance.now();
  const words = text.split(/\s+/).filter(Boolean).length;
  deafUntil = Date.now() + Math.min(12000, 900 + words * 320);
  speakSeq += 1;
  const seq = speakSeq;
  stopAudio();
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }

  void (async () => {
    let blob = await fetchVoicebox(text, seq);
    if (seq !== speakSeq) return;
    if (!blob) {
      await new Promise((resolve) => window.setTimeout(resolve, 400));
      if (seq !== speakSeq) return;
      blob = await fetchVoicebox(text, seq);
      if (seq !== speakSeq) return;
    }
    if (blob) {
      playVoiceboxBlob(blob, end, seq);
      return;
    }
    end();
  })();
}

export function enqueueSentence(text: string, enabled = true, onEnd?: () => void) {
  const sentence = text.trim();
  if (!sentence) {
    onEnd?.();
    return;
  }
  speak(sentence, enabled, onEnd, { force: true, queue: true });
}

export function silence() {
  speechGen += 1;
  queueHold = false;
  sentenceQueue.length = 0;
  speechIdleWaiters.length = 0;
  speakSeq += 1;
  deafUntil = Date.now() + 450;
  stopAudio();
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}
