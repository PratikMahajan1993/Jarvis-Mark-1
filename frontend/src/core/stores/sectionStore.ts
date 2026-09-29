"use client";

import {
  isHudWorkspace,
  loadStoredWorkspace,
  loadStoredWorkspacePinned,
  persistWorkspace,
  persistWorkspacePinned,
  type HudWorkspace,
} from "@/components/orchestrator/hudWorkspace";
import { liveLog } from "@/lib/liveLog";
import { autoContext, decideAuto } from "@/core/scroll/director";
import { createStore } from "./createStore";

export type ScrollSource = "auto" | "user";

export type SectionRequest = {
  id: number;
  section: string;
  source: ScrollSource;
  reason: string;
  /** Jump without animation (landing exit, reduced motion). */
  immediate?: boolean;
};

export type SectionState = {
  /** Active section id (more than 60% in view, with hysteresis). */
  active: string;
  /** Scroll position in section units (0 = first section top). */
  progress: number;
  workspace: HudWorkspace;
  pinned: boolean;
  /** Latest scroll request for the scroll engine to execute. */
  request: SectionRequest | null;
  /** The page is scrolling (baton dimming, X7). */
  scrolling: boolean;
};

export const sectionStore = createStore<SectionState>({
  active: "monitor",
  progress: 0,
  workspace: "monitor",
  pinned: false,
  request: null,
  scrolling: false,
});

let requestSeq = 0;
let pendingAuto = 0;

export function getSection(): SectionState {
  return sectionStore.get();
}

export function useSectionState<T>(selector: (s: SectionState) => T): T {
  return sectionStore.use(selector);
}

export function hydrateWorkspace(): { workspace: HudWorkspace; pinned: boolean } {
  const pinned = loadStoredWorkspacePinned();
  const workspace = loadStoredWorkspace() ?? "monitor";
  sectionStore.set({ pinned, workspace });
  return { workspace, pinned };
}

export function setWorkspace(next: HudWorkspace, reason: string, sessionId = "default") {
  const from = sectionStore.get().workspace;
  if (from === next) return;
  sectionStore.set({ workspace: next });
  persistWorkspace(next);
  liveLog("workspace", { from, to: next, pinned: sectionStore.get().pinned, reason }, { sessionId });
}

export function togglePinned(sessionId = "default") {
  const next = !sectionStore.get().pinned;
  sectionStore.set({ pinned: next });
  persistWorkspacePinned(next);
  const ws = sectionStore.get().workspace;
  liveLog("workspace", { from: ws, to: ws, pinned: next, reason: "pin" }, { sessionId });
}

/**
 * Ask the scroll engine to move to a section. A user request always runs; an
 * automatic one is dropped while pinned. (The step-6 director adds the
 * interaction / modal suppression rules on top of this.)
 */
export function requestSection(
  section: string,
  opts: { source: ScrollSource; reason: string; immediate?: boolean },
): boolean {
  const s = sectionStore.get();
  if (opts.source === "auto" && s.active === section && !opts.immediate) return false;
  if (opts.source === "auto" && !opts.immediate) {
    const decision = decideAuto(autoContext(s.pinned));
    if (!decision.run) {
      window.clearTimeout(pendingAuto);
      if (!decision.drop && decision.retryInMs != null) {
        pendingAuto = window.setTimeout(() => requestSection(section, opts), decision.retryInMs);
      }
      return false;
    }
  } else if (opts.source === "auto" && s.pinned) {
    return false;
  }
  window.clearTimeout(pendingAuto);
  requestSeq += 1;
  sectionStore.set({
    request: { id: requestSeq, section, source: opts.source, reason: opts.reason, immediate: opts.immediate },
  });
  return true;
}

/** Called by the scroll engine as the page moves. */
export function reportScroll(progress: number, active: string, workspace: string | undefined) {
  const prev = sectionStore.get();
  sectionStore.set({ progress, active });
  if (active !== prev.active && workspace && isHudWorkspace(workspace)) {
    setWorkspace(workspace, "scroll");
  }
}

export function setScrolling(scrolling: boolean) {
  sectionStore.set({ scrolling });
}
