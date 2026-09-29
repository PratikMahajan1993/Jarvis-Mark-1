"use client";

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
