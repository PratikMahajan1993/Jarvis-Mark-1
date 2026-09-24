"use client";

import type { ReactNode } from "react";

export function ConverseStrip({
  line,
  baton,
}: {
  /** One Jarvis line — voice when visible, else focus title. */
  line: string;
  /** Existing CommandBaton when the shell passes it into the strip slot. */
  baton?: ReactNode;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col justify-center gap-2 px-4 py-2">
      <p className="font-display text-[1.05rem] leading-snug text-[color:var(--fg)] whitespace-pre-wrap break-words">
        {line}
      </p>
      {baton ? <div className="shrink-0">{baton}</div> : null}
    </div>
  );
}
