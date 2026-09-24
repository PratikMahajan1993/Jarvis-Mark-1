import type { HudWorkspace } from "@/components/orchestrator/hudWorkspace";
import type { Lens } from "@/substrate/protocol";

export type PanelId =
  | "voice"
  | "notes"
  | "weather"
  | "tasks"
  | "agents"
  | "activity"
  | "stage"
  | "sheet";

export type SlotId =
  | "centre-low"
  | "left-rail"
  | "left-peek"
  | "right-rail-top"
  | "right-rail"
  | "under-centre"
  | "bottom-centre"
  | "bottom-left"
  | "stage"
  | "sheet"
  | "strip"
  | "status";

export type PanelDepth = 0 | 1 | 2 | 3;

export type PanelPlacement = { slot: SlotId; depth: PanelDepth };

export const PANEL_IDS: PanelId[] = [
  "voice",
  "notes",
  "weather",
  "tasks",
  "agents",
  "activity",
  "stage",
  "sheet",
];

export const LENS_LAYOUT: Record<Lens, Record<PanelId, PanelPlacement>> = {
  watch: {
    voice: { slot: "centre-low", depth: 1 },
    notes: { slot: "left-rail", depth: 3 },
    weather: { slot: "right-rail-top", depth: 3 },
    tasks: { slot: "right-rail", depth: 1 },
    agents: { slot: "under-centre", depth: 1 },
    activity: { slot: "bottom-left", depth: 2 },
    stage: { slot: "stage", depth: 3 },
    sheet: { slot: "sheet", depth: 3 },
  },
  converse: {
    voice: { slot: "centre-low", depth: 0 },
    notes: { slot: "left-rail", depth: 1 },
    weather: { slot: "right-rail-top", depth: 1 },
    tasks: { slot: "right-rail", depth: 1 },
    agents: { slot: "bottom-centre", depth: 2 },
    activity: { slot: "bottom-left", depth: 2 },
    stage: { slot: "stage", depth: 3 },
    sheet: { slot: "sheet", depth: 3 },
  },
  bench: {
    voice: { slot: "strip", depth: 1 },
    notes: { slot: "left-peek", depth: 3 },
    weather: { slot: "right-rail-top", depth: 3 },
    tasks: { slot: "right-rail", depth: 3 },
    agents: { slot: "status", depth: 3 },
    activity: { slot: "bottom-left", depth: 3 },
    stage: { slot: "stage", depth: 0 },
    sheet: { slot: "sheet", depth: 0 },
  },
};

export type LensThemeTokens = {
  bg: string;
  surface: string;
  fg: string;
  muted: string;
  border: string;
  accent: string;
  mat: string;
  gridOpacity: number;
  vignetteOpacity: number;
};

export const LENS_THEME: Record<Lens, LensThemeTokens> = {
  converse: {
    bg: "oklch(10% 0.005 240)",
    surface: "oklch(14% 0.008 240)",
    fg: "oklch(96% 0.004 240)",
    muted: "oklch(62% 0.008 240)",
    border: "oklch(22% 0.01 240)",
    accent: "oklch(74% 0.15 160)",
    mat: "transparent",
    gridOpacity: 0,
    vignetteOpacity: 0.8,
  },
  watch: {
    bg: "oklch(12% 0.022 55)",
    surface: "oklch(16% 0.028 52)",
    fg: "oklch(94% 0.018 75)",
    muted: "oklch(58% 0.04 62)",
    border: "oklch(24% 0.03 55)",
    accent: "oklch(72% 0.14 78)",
    mat: "transparent",
    gridOpacity: 0,
    vignetteOpacity: 0.9,
  },
  bench: {
    bg: "oklch(9% 0.004 240)",
    surface: "oklch(13% 0.005 240)",
    fg: "oklch(95% 0.003 240)",
    muted: "oklch(60% 0.006 240)",
    border: "oklch(20% 0.006 240)",
    accent: "oklch(74% 0.10 165)",
    mat: "oklch(16% 0.004 240)",
    gridOpacity: 0.35,
    vignetteOpacity: 0.5,
  },
};

export function lensForWorkspace(workspace: HudWorkspace): Lens {
  if (workspace === "monitor") return "watch";
  if (workspace === "casual") return "converse";
  return "bench";
}

export function workspaceForLens(lens: Lens): HudWorkspace {
  if (lens === "watch") return "monitor";
  if (lens === "converse") return "casual";
  return "engineering";
}
