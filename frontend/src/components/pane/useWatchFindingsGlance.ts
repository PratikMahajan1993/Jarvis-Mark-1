"use client";

import { useEffect, useRef } from "react";
import { enqueueFindingGlance } from "@/lib/pane/ambient";
import type { SuggestedTask } from "@/components/orchestrator/SuggestedTasksPanel";

function paneRoot(): HTMLElement | null {
  if (typeof document === "undefined") return null;
  return document.querySelector<HTMLElement>("[data-pane-root]");
}

/** When a new finding id appears on Watch, pull the Eye toward the tasks rail once. */
export function useWatchFindingsGlance(tasks: SuggestedTask[], enabled: boolean): void {
  const seenRef = useRef<Set<string>>(new Set());
  const bootRef = useRef(true);

  useEffect(() => {
    const root = paneRoot();
    if (!root || !enabled) return;

    if (bootRef.current) {
      bootRef.current = false;
      for (const t of tasks) seenRef.current.add(t.id);
      return;
    }

    for (const task of tasks) {
      if (seenRef.current.has(task.id)) continue;
      seenRef.current.add(task.id);
      enqueueFindingGlance(root, task.id);
    }
  }, [tasks, enabled]);
}
