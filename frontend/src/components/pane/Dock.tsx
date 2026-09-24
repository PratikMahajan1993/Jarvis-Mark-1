"use client";

import type { ReactNode } from "react";
import { useLens, usePane } from "@/lib/pane/paneStore";

export function Dock({ children }: { children: ReactNode }) {
  const lens = useLens();
  const focusMode = usePane((s) => s.focusMode);
  return (
    <div
      className="pane-dock pointer-events-none absolute inset-0 z-10 isolation-isolate"
      style={{ perspective: "1400px" }}
      data-dock
      data-lens={lens}
      data-focus={focusMode}
    >
      {children}
    </div>
  );
}
