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

const YES_SHORT = new Set(["y", "yes", "yeah", "yep", "yup", "yea", "confirm", "send", "send it", "do it", "go ahead", "proceed", "affirmative", "yes please", "yes send it", "yeah do it", "yes do it", "go for it", "do that", "ship it", "do so", "that's a yes", "thats a yes"]);
const NO_SHORT = new Set(["n", "no", "nope", "nah", "cancel", "stop", "dont", "don't", "do not", "never", "reject", "negative", "abort", "wait", "no thanks", "no thank you", "not now", "hold on", "leave it", "later", "not yet", "hold off"]);

export function classifyDecision(text: string): "yes" | "no" | null {
  const cleaned = text.toLowerCase().trim().replace(/[!.?,]/g, "").replace(/\s+/g, " ").replace(/'/g, "");
  if (!cleaned) return null;
  const no = new Set([...NO_SHORT].map((item) => item.replace(/'/g, "")));
  const yes = new Set([...YES_SHORT].map((item) => item.replace(/'/g, "")));
  if (no.has(cleaned)) return "no";
  if (yes.has(cleaned)) return "yes";
  return null;
}

const GLANCE_STORE = "jarvis.spokenGlance";
const spokenGlanceKeys = new Set<string>();
let glanceStoreLoaded = false;
let cachedVoice: SpeechSynthesisVoice | null = null;
let activeSpeech: SpeechSynthesisUtterance | null = null;

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

function pickVoice(): SpeechSynthesisVoice | undefined {
  if (cachedVoice) return cachedVoice;
  if (typeof window === "undefined" || !window.speechSynthesis) return undefined;
  const voices = window.speechSynthesis.getVoices();
  cachedVoice =
    voices.find((voice) => /en-GB|Daniel|Google UK/i.test(`${voice.name} ${voice.lang}`)) ||
    voices.find((voice) => voice.lang.startsWith("en")) ||
    voices[0] ||
    null;
  return cachedVoice || undefined;
}

export function isSpeaking(): boolean {
  return Boolean(activeSpeech) || Date.now() < deafUntil;
}

let lastSpokenText = "";
let lastSpokenAt = 0;

export function speak(text: string, enabled = true, onEnd?: () => void) {
  if (!enabled || !text || typeof window === "undefined" || !window.speechSynthesis) {
    onEnd?.();
    return;
  }
  if (activeSpeech?.text === text) return;
  if (text === lastSpokenText && Date.now() - lastSpokenAt < 90000) {
    onEnd?.();
    return;
  }
  lastSpokenText = text;
  lastSpokenAt = Date.now();
  const words = text.split(/\s+/).filter(Boolean).length;
  deafUntil = Date.now() + Math.min(8000, 700 + words * 280);
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  const voice = pickVoice();
  if (voice) utterance.voice = voice;
  utterance.rate = 1.02;
  utterance.pitch = 0.95;
  let finished = false;
  const done = () => {
    if (finished) return;
    finished = true;
    if (activeSpeech === utterance) activeSpeech = null;
    deafUntil = Date.now() + 500;
    onEnd?.();
  };
  utterance.onend = done;
  utterance.onerror = done;
  activeSpeech = utterance;
  window.setTimeout(() => {
    if (activeSpeech !== utterance) return;
    window.speechSynthesis.speak(utterance);
  }, 40);
}

export function silence() {
  activeSpeech = null;
  deafUntil = Date.now() + 450;
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}
