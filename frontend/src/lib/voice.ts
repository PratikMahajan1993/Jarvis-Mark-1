import { postSubstrate } from "@/core/root/substrateBridge";

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
let activeSource: AudioBufferSourceNode | null = null;
let playbackCtx: AudioContext | null = null;
let speakAbort: AbortController | null = null;
let levelRaf = 0;
let levelAnalyser: AnalyserNode | null = null;
let levelScratch: Float32Array | null = null;

function stopLevelLoop() {
  if (levelRaf) {
    cancelAnimationFrame(levelRaf);
    levelRaf = 0;
  }
  levelAnalyser = null;
  levelScratch = null;
  postSubstrate({ type: "level", value: 0 });
}

function startLevelLoop(analyser: AnalyserNode) {
  stopLevelLoop();
  levelAnalyser = analyser;
  const scratch = new Float32Array(analyser.fftSize);
  levelScratch = scratch;
  const tick = () => {
    if (!levelAnalyser || levelScratch !== scratch) return;
    levelAnalyser.getFloatTimeDomainData(scratch);
    let sum = 0;
    for (let i = 0; i < scratch.length; i += 1) {
      const s = scratch[i]!;
      sum += s * s;
    }
    const rms = Math.sqrt(sum / scratch.length);
    postSubstrate({ type: "level", value: Math.min(1, rms * 6) });
    levelRaf = requestAnimationFrame(tick);
  };
  levelRaf = requestAnimationFrame(tick);
}

function connectPlayback(ctx: AudioContext, source: AudioBufferSourceNode) {
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = 0.55;
  source.connect(analyser);
  analyser.connect(ctx.destination);
  startLevelLoop(analyser);
}

function playbackContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor =
    window.AudioContext ||
    (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!playbackCtx) playbackCtx = new Ctor();
  return playbackCtx;
}

/** Resume audio during a click or keypress. A later Gemini clip can then play. */
export function ensureAudioContextUnlocked() {
  const ctx = playbackContext();
  if (ctx && ctx.state !== "running") void ctx.resume();
}

if (typeof window !== "undefined") {
  const prime = () => ensureAudioContextUnlocked();
  window.addEventListener("pointerdown", prime, true);
  window.addEventListener("keydown", prime, true);
}

function apiRoot(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
}

function stopSource() {
  if (activeSource) {
    try {
      activeSource.onended = null;
      activeSource.stop();
    } catch {
      /* already stopped */
    }
    activeSource = null;
  }
  stopLevelLoop();
}

function stopAudio() {
  speakAbort?.abort();
  speakAbort = null;
  stopSource();
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

/** Fetch a Gemini WAV. Playback is this blob. A failed fetch leaves the desk silent. */
async function fetchSpeech(text: string): Promise<Blob | null> {
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
    return await response.blob();
  } catch (err) {
    if ((err as { name?: string })?.name === "AbortError") return null;
    return null;
  } finally {
    if (speakAbort === controller) speakAbort = null;
  }
}

let playGen = 0;
let speakChain: Promise<void> = Promise.resolve();
let playsInFlight = 0;
const speechIdleWaiters: Array<() => void> = [];

function flushSpeechIdle() {
  if (playsInFlight > 0 || activeSource) return;
  const waiters = speechIdleWaiters.splice(0);
  waiters.forEach((waiter) => waiter());
}

function playBuffer(blob: Blob, gen: number): Promise<void> {
  const ctx = playbackContext();
  if (!ctx) return Promise.resolve();
  return blob.arrayBuffer().then(async (raw) => {
    if (gen !== playGen) return;
    if (ctx.state !== "running") await ctx.resume();
    if (gen !== playGen) return;
    const decoded = await ctx.decodeAudioData(raw.slice(0));
    if (gen !== playGen) return;
    stopSource();
    await new Promise<void>((resolve) => {
      const source = ctx.createBufferSource();
      source.buffer = decoded;
      activeSource = source;
      connectPlayback(ctx, source);
      source.onended = () => {
        if (activeSource === source) activeSource = null;
        stopLevelLoop();
        deafUntil = Date.now() + 500;
        resolve();
      };
      source.start(0);
    });
  });
}

/** The only way a reply is spoken. Fetches a Gemini WAV and plays that buffer. */
export function speakText(text: string): Promise<void> {
  const line = text.trim();
  if (!line || typeof window === "undefined") return Promise.resolve();
  const gen = playGen;
  playsInFlight += 1;
  const job = speakChain.then(async () => {
    if (gen !== playGen) return;
    ensureAudioContextUnlocked();
    let blob = await fetchSpeech(line);
    if (gen !== playGen) return;
    if (!blob) {
      await new Promise((resolve) => window.setTimeout(resolve, 400));
      if (gen !== playGen) return;
      blob = await fetchSpeech(line);
    }
    if (!blob || gen !== playGen) return;
    await playBuffer(blob, gen);
  });
  const settled = job.finally(() => {
    if (gen !== playGen) return;
    playsInFlight = Math.max(0, playsInFlight - 1);
    flushSpeechIdle();
  });
  speakChain = settled.then(
    () => undefined,
    () => undefined,
  );
  return settled;
}

export function isSpeaking(): boolean {
  return Boolean(activeSource) || playsInFlight > 0 || Date.now() < deafUntil;
}

export function whenSpeechIdle(callback: () => void) {
  if (playsInFlight === 0 && !activeSource) {
    callback();
    return;
  }
  speechIdleWaiters.push(callback);
}

const QUOTE_BLOCKER_STORE = "jarvis.quoteBlockerSpeech";
const spokenQuoteBlockers = new Set<string>();
let quoteBlockerStoreLoaded = false;

function loadQuoteBlockerStore() {
  if (quoteBlockerStoreLoaded || typeof window === "undefined") return;
  quoteBlockerStoreLoaded = true;
  try {
    const raw = window.localStorage.getItem(QUOTE_BLOCKER_STORE);
    if (!raw) return;
    const keys = JSON.parse(raw) as string[];
    for (const key of keys.slice(-40)) spokenQuoteBlockers.add(key);
  } catch {
    /* ignore */
  }
}

function persistQuoteBlockerStore() {
  try {
    window.localStorage.setItem(QUOTE_BLOCKER_STORE, JSON.stringify([...spokenQuoteBlockers].slice(-40)));
  } catch {
    /* ignore */
  }
}

/** With a drawing open on Engineering, chat replies are not auto-spoken — blockers use trySpeakQuoteBlocker. */
export function shouldAutoSpeakChatReply(opts: { drawingOpen: boolean; workspace: string }): boolean {
  if (!opts.drawingOpen || opts.workspace !== "engineering") return true;
  return false;
}

export function claimQuoteBlockerSpeech(blockerId: string): boolean {
  const key = (blockerId || "").trim();
  if (!key) return false;
  loadQuoteBlockerStore();
  if (spokenQuoteBlockers.has(key)) return false;
  spokenQuoteBlockers.add(key);
  persistQuoteBlockerStore();
  return true;
}

export function releaseQuoteBlockerSpeech(blockerId: string) {
  const key = (blockerId || "").trim();
  if (!key) return;
  loadQuoteBlockerStore();
  if (!spokenQuoteBlockers.delete(key)) return;
  persistQuoteBlockerStore();
}

export function trySpeakQuoteBlocker(blocker: { id: string; evidence: string }) {
  const line = (blocker.evidence || "").trim();
  if (!line || !claimQuoteBlockerSpeech(blocker.id)) return;
  void speakText(line.slice(0, 480));
}

export function isMarginSuggestion(text: string): boolean {
  return /\bmargin\s+(hint|suggestion|move)\b/i.test(text);
}

export function shouldShowReplySpeakControl(text: string): boolean {
  return Boolean(text.trim()) && !isMarginSuggestion(text);
}

export function speakReplyLine(text: string) {
  void speakText(text.trim());
}

export function silence() {
  playGen += 1;
  playsInFlight = 0;
  speakChain = Promise.resolve();
  deafUntil = Date.now() + 450;
  stopAudio();
  const waiters = speechIdleWaiters.splice(0);
  waiters.forEach((waiter) => waiter());
}

