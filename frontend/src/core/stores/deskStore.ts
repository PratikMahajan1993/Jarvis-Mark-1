"use client";

import type { GoogleConnectStatus } from "@/components/orchestrator/ConnectGoogleModal";
import type { RailConversation } from "@/components/orchestrator/ConversationRail";
import type { SuggestedTask } from "@/components/orchestrator/SuggestedTasksPanel";
import { DEFAULT_AGENTS, type ActivityItem, type AgentNode } from "@/lib/orchestrator";
import type { ChatResponse, Preferences, Scene } from "@/lib/types";
import { createStore } from "./createStore";

export const AMBIENT_SESSION = "default";
export const IDLE_VOICE = "Awaiting instruction.";
export const EMPTY_SCENE: Scene = { title: "", widgets: [] };
export const MAX_OPEN_CONVERSATIONS = 3;

export type DrawingChat = NonNullable<ChatResponse["drawing_chat"]>;

export type DeskState = {
  voice: string;
  voiceVisible: boolean;
  scene: Scene;
  compose: string;
  agents: AgentNode[];
  activity: ActivityItem[];
  desk: RailConversation[];
  activeSession: string;
  activeConversationId: string | null;
  focusTitle: string;
  conversationFocus: Record<string, unknown>;
  prefs: Preferences | null;
  error: string;
  extractCard: { title: string; text: string } | null;
  runStatus: string;
  suggested: SuggestedTask[];
  weatherLine: string;
  dockHidden: boolean;
  prefsOpen: boolean;
  googleStatus: GoogleConnectStatus | null;
  googleConnectOpen: boolean;
  ledgerTurnId: string | null;
  drawingChat: DrawingChat | null;
  /** Session bootstrap settled (landing gate G3). */
  booted: boolean;
};

/** Sessions, conversations, desk items and the on-screen voice line. */
export const deskStore = createStore<DeskState>({
  voice: IDLE_VOICE,
  voiceVisible: false,
  scene: EMPTY_SCENE,
  compose: "",
  agents: DEFAULT_AGENTS,
  activity: [],
  desk: [],
  activeSession: AMBIENT_SESSION,
  activeConversationId: null,
  focusTitle: "Everyday desk",
  conversationFocus: {},
  prefs: null,
  error: "",
  extractCard: null,
  runStatus: "",
  suggested: [],
  weatherLine: "",
  dockHidden: false,
  prefsOpen: false,
  googleStatus: null,
  googleConnectOpen: false,
  ledgerTurnId: null,
  drawingChat: null,
  booted: false,
});

export const getDesk = deskStore.get;
export const setDesk = deskStore.set;

export function useDesk<T>(selector: (s: DeskState) => T): T {
  return deskStore.use(selector);
}

/** Mail / HITL / tool boards keep widgets; speak-only chat shells do not. */
export function sceneHasBoardContent(scene: Scene | null | undefined): boolean {
  if (!scene) return false;
  const widgets = scene.widgets || [];
  const title = (scene.title || "").trim();
  const decorativeTitle = !title || /^jarvis$/i.test(title);
  if (widgets.length === 0) {
    return Boolean(title) && !/^jarvis$/i.test(title);
  }
  const onlyQuotes = widgets.every((w) => w.type === "quote");
  if (onlyQuotes && decorativeTitle) return false;
  return true;
}
