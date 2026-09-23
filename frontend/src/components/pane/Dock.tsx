"use client";

import type { ReactNode } from "react";

export function Dock({ children }: { children: ReactNode }) {
  return (
    <div
      className="pane-dock pointer-events-none absolute inset-0 z-10 isolation-isolate"
      style={{ perspective: "1400px" }}
      data-dock
    >
      {children}
    </div>
  );
}
