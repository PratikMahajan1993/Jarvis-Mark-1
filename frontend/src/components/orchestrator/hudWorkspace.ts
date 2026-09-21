"use client";

import { useEffect, useRef, useState } from "react";

/** HUD workspace — orthogonal to the turn FSM (IDLE | LISTENING | …). */
export type HudWorkspace = "casual" | "monitor" | "engineering";

export const HUD_WORKSPACE_KEY = "jarvis.hudWorkspace";
export const HUD_WORKSPACE_PINNED_KEY = "jarvis.hudWorkspacePinned";

const AMBIENT_SESSION = "default";

export const WORKSPACE_LABELS: Record<HudWorkspace, string> = {
  casual: "Casual",
  monitor: "Monitor",
  engineering: "Engineering",
};

export function isHudWorkspace(value: string | null | undefined): value is HudWorkspace {
  return value === "casual" || value === "monitor" || value === "engineering";
}

export function workspaceFromCategory(category: string | null | undefined): HudWorkspace {
  const cat = (category || "").toLowerCase();
  if (cat === "drawing" || cat === "workflow") return "engineering";
  if (cat === "discussion") return "casual";
  return "monitor";
}

/** Derive workspace from current desk focus (ambient vs open conversation). */
export function autoWorkspaceFromFocus(opts: {
  activeConversationId: string | null;
  activeSession: string;
  category?: string | null;
}): HudWorkspace {
  const { activeConversationId, activeSession, category } = opts;
  if (!activeConversationId && activeSession === AMBIENT_SESSION) return "monitor";
  if (category) return workspaceFromCategory(category);
  return "monitor";
}

/** Short status questions stay on monitor when the user talks from that workspace. */
export function isStatusUtterance(text: string): boolean {
  const t = text.trim().toLowerCase().replace(/[?!.]+$/g, "");
  if (!t) return false;

  const exact = [
    "status",
    "what are they doing",
    "what's running",
    "whats running",
    "is mail triaged",
    "any updates",
    "what is running",
    "what's the status",
    "whats the status",
    "any news",
    "what's happening",
    "whats happening",
  ];
  if (exact.includes(t)) return true;

  if (t.length > 80) return false;

  const statusLead =
    /^(what(?:'s| is| are)|how(?:'s| is| are)|is|are|any)\b/.test(t) &&
    /\b(status|running|updates?|triaged|happening|doing|progress|idle|watch)\b/.test(t);
  return statusLead;
}

const ENGINEERING_HINT =
  /\b(drawing|drawings|rfq|quote|machin(?:e|ing)|strategy|cnc|nc program|tolerance|fixture|part|job shop|engineering|cam|g[- ]?code|solidworks|step file|dxf)\b/i;

const CASUAL_HINT =
  /\b(mail|email|inbox|gmail|reply|send|discuss|chat|calendar|meeting|note|remember|remind|hello|hi\b|thanks|thank you)\b/i;

/** When talking from monitor, decide whether to jump workspace before send. */
export function talkJumpWorkspace(text: string, current: HudWorkspace): HudWorkspace | null {
  if (current !== "monitor") return null;
  if (isStatusUtterance(text)) return null;
  if (ENGINEERING_HINT.test(text)) return "engineering";
  if (CASUAL_HINT.test(text)) return "casual";
  // Ambiguous chat-like input defaults to casual desk.
  return "casual";
}

export function loadStoredWorkspace(): HudWorkspace | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(HUD_WORKSPACE_KEY);
    return isHudWorkspace(stored) ? stored : null;
  } catch {
    return null;
  }
}

export function loadStoredWorkspacePinned(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(HUD_WORKSPACE_PINNED_KEY) === "true";
  } catch {
    return false;
  }
}

export function persistWorkspace(workspace: HudWorkspace): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(HUD_WORKSPACE_KEY, workspace);
  } catch {
    /* ignore */
  }
}

export function persistWorkspacePinned(pinned: boolean): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(HUD_WORKSPACE_PINNED_KEY, pinned ? "true" : "false");
  } catch {
    /* ignore */
  }
}

export function initialWorkspaceFromBootstrap(opts: {
  restoredCategory?: string | null;
  pinned: boolean;
  stored?: HudWorkspace | null;
}): HudWorkspace {
  const derived = opts.restoredCategory
    ? workspaceFromCategory(opts.restoredCategory)
    : "monitor";
  if (opts.pinned && opts.stored) return opts.stored;
  return derived;
}

/** Staged HUD morph: presence (orb/eye/bench) → palette → chrome (rails). */
export const HUD_PRESENCE_MS = 1200;
export const HUD_THEME_DELAY_MS = 1300;
export const HUD_CHROME_DELAY_MS = 2400;

export type HudLayers = {
  incoming: HudWorkspace;
  outgoing: HudWorkspace | null;
  theme: HudWorkspace;
  chrome: HudWorkspace;
  morphReady: boolean;
  incomingLit: boolean;
};

function reduceMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function useWorkspaceLayers(target: HudWorkspace): HudLayers {
  const [incoming, setIncoming] = useState(target);
  const [outgoing, setOutgoing] = useState<HudWorkspace | null>(null);
  const [theme, setTheme] = useState(target);
  const [chrome, setChrome] = useState(target);
  const [morphReady, setMorphReady] = useState(false);
  const [incomingLit, setIncomingLit] = useState(true);
  const first = useRef(true);
  const incomingRef = useRef(target);
  incomingRef.current = incoming;

  useEffect(() => {
    const ready = window.requestAnimationFrame(() => setMorphReady(true));
    return () => window.cancelAnimationFrame(ready);
  }, []);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      setIncoming(target);
      setOutgoing(null);
      setTheme(target);
      setChrome(target);
      setIncomingLit(true);
      return;
    }
    const from = incomingRef.current;
    if (target === from) {
      setOutgoing(null);
      setTheme(target);
      setChrome(target);
      setIncomingLit(true);
      return;
    }

    if (reduceMotion()) {
      setIncoming(target);
      setOutgoing(null);
      setTheme(target);
      setChrome(target);
      setIncomingLit(true);
      return;
    }

    setOutgoing(from);
    setIncoming(target);
    setIncomingLit(false);
    let litFrame2 = 0;
    const litFrame1 = window.requestAnimationFrame(() => {
      litFrame2 = window.requestAnimationFrame(() => setIncomingLit(true));
    });
    const themeTimer = window.setTimeout(() => setTheme(target), HUD_THEME_DELAY_MS);
    const presenceTimer = window.setTimeout(() => setOutgoing(null), HUD_PRESENCE_MS);
    const chromeTimer = window.setTimeout(() => setChrome(target), HUD_CHROME_DELAY_MS);
    return () => {
      window.cancelAnimationFrame(litFrame1);
      window.cancelAnimationFrame(litFrame2);
      window.clearTimeout(themeTimer);
      window.clearTimeout(presenceTimer);
      window.clearTimeout(chromeTimer);
    };
  }, [target]);

  return { incoming, outgoing, theme, chrome, morphReady, incomingLit };
}

export function presenceVisible(id: HudWorkspace, layers: HudLayers): boolean {
  return layers.incoming === id || layers.outgoing === id;
}

export function presenceOn(id: HudWorkspace, layers: HudLayers): boolean {
  return layers.incoming === id && layers.incomingLit;
}

export function chromeOn(id: HudWorkspace, layers: HudLayers): boolean {
  return layers.incoming === id && layers.chrome === id;
}
