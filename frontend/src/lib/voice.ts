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
  return [...new Set([chosen, "Jarvis", "Jarvish", "Jar vis"])];
}

export function takeWake(text: string, name = "Jarvis"): { woke: boolean; rest: string } {
  const raw = text.trim();
  if (!raw) return { woke: false, rest: "" };
  const options = wakeNames(name).map(escapeReg).join("|");
  const re = new RegExp(`^(?:hey |ok |okay |hi )?(${options})\\b[,.\\s]*`, "i");
  const match = raw.match(re);
  if (!match) return { woke: false, rest: raw };
  return { woke: true, rest: raw.slice(match[0].length).trim() };
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

function beginSession(mode: "wake" | "command"): number {
  session += 1;
  armed = false;
  listenMode = "off";
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

type WakeHandlers = {
  name: string | (() => string);
  onHot?: () => void;
  onWake: (rest: string) => void;
  onError?: (message: string) => void;
};

function currentName(name: string | (() => string)): string {
  return typeof name === "function" ? name() : name;
}

export async function startWakeWatch(handlers: WakeHandlers): Promise<void> {
  const Ctor = speechCtor();
  if (!Ctor) return;

  const mine = beginSession("wake");
  wakeConsumed = "";

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (mine !== session) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    micStream = stream;
  } catch {
    if (mine === session) {
      armed = false;
      listenMode = "off";
    }
    return;
  }

  const rec = new Ctor();
  recognizer = rec;
  rec.lang = navigator.language || "en-IN";
  rec.interimResults = true;
  rec.continuous = true;
  rec.maxAlternatives = 3;

  rec.onresult = (event) => {
    if (mine !== session || listenMode !== "wake" || Date.now() < deafUntil) return;
    const { finalText, partial } = readLatest(event);
    const name = currentName(handlers.name);
    const hot = takeWake(partial || finalText, name);
    if (hot.woke && !finalText) {
      handlers.onHot?.();
      return;
    }
    if (!finalText) return;
    const heard = takeWake(finalText, name);
    if (!heard.woke) return;
    const key = `${finalText}:${heard.rest}`;
    if (key === wakeConsumed) return;
    wakeConsumed = key;
    armed = false;
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
    armed = false;
    const message = friendlyError(event.error);
    if (message) handlers.onError?.(message);
  };

  rec.onend = () => {
    if (mine !== session) return;
    if (armed && listenMode === "wake" && recognizer === rec) {
      restarting = true;
      try {
        rec.start();
      } catch {
        armed = false;
        listenMode = "off";
      }
      restarting = false;
      return;
    }
    if (!restarting && recognizer === rec) {
      recognizer = null;
      if (listenMode === "wake") listenMode = "off";
      releaseMic();
    }
  };

  try {
    rec.start();
  } catch {
    if (mine !== session) return;
    armed = false;
    listenMode = "off";
    if (recognizer === rec) {
      recognizer = null;
      releaseMic();
    }
  }
}

const YES = /^(yes|yeah|yep|yup|yea|ok|okay|sure|confirm|send( it)?|do it|go ahead|proceed|please|affirmative|that'?s fine)\b/;
const NO = /^(no|nope|nah|cancel|stop|don'?t|do not|never|reject|negative|abort|wait)\b/;

export function classifyDecision(text: string): "yes" | "no" | null {
  const cleaned = text.toLowerCase().trim().replace(/[!.?,]/g, "");
  if (!cleaned) return null;
  if (cleaned === "n" || NO.test(cleaned)) return "no";
  if (cleaned === "y" || YES.test(cleaned)) return "yes";
  return null;
}

const GLANCE_STORE = "jarvis.spokenGlance";
const spokenGlanceKeys = new Set<string>();
let glanceStoreLoaded = false;
let cachedVoice: SpeechSynthesisVoice | null = null;
let activeSpeech: SpeechSynthesisUtterance | null = null;

function loadGlanceStore() {
  if (glanceStoreLoaded || typeof sessionStorage === "undefined") return;
  glanceStoreLoaded = true;
  try {
    const raw = sessionStorage.getItem(GLANCE_STORE);
    if (!raw) return;
    for (const key of JSON.parse(raw) as string[]) spokenGlanceKeys.add(key);
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
    sessionStorage.setItem(GLANCE_STORE, JSON.stringify([...spokenGlanceKeys]));
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
  deafUntil = Date.now() + 30000;
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
