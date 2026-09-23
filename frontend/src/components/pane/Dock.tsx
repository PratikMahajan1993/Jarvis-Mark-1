"use client";

import type { ReactNode } from "react";
import { useLens } from "@/lib/pane/paneStore";

export function Dock({ children }: { children: ReactNode }) {
  const lens = useLens();
  return (
    <div
      className="pane-dock pointer-events-none absolute inset-0 z-10 isolation-isolate"
      style={{ perspective: "1400px" }}
      data-dock
      data-lens={lens}
    >
      {children}
    </div>
  );
}
