"use client";

import GradientText from "@/components/react-bits/GradientText";
import { Notifications } from "@/core/chrome/Notifications";
import { useTurnView } from "@/core/desk/useTurnView";
import { setDesk, useDesk } from "@/core/stores/deskStore";
import { togglePinned, useSectionState } from "@/core/stores/sectionStore";

function PinIcon({ pinned }: { pinned: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className="h-3 w-3"
      fill={pinned ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.4"
      aria-hidden
    >
      <path d="M8 1.5 6.2 3.3 4.5 2.8 3.8 4.5 2.1 5.2 2.6 6.9 1.5 8 2.6 9.1 2.1 10.8 3.8 11.5 4.5 13.2 6.2 12.7 8 14.5 9.8 12.7 11.5 13.2 12.2 11.5 13.9 10.8 13.4 9.1 14.5 8 13.4 6.9 13.9 5.2 12.2 4.5 11.5 2.8 9.8 3.3z" />
      <circle cx="8" cy="8" r="1.6" fill={pinned ? "var(--bg)" : "none"} />
    </svg>
  );
}

/** L3 top: who is speaking and about what; pin (blocks automatic scrolls) and preferences. */
export function StatusCluster() {
  const assistantName = useDesk((s) => s.prefs?.assistant_name || "Jarvis");
  const focusTitle = useDesk((s) => s.focusTitle);
  const sessionId = useDesk((s) => s.activeSession);
  const pinned = useSectionState((s) => s.pinned);
  const { hitl } = useTurnView();

  return (
    <header
      className="pointer-events-none fixed inset-x-0 top-0 z-chrome flex items-center justify-between px-4"
      style={{ height: "var(--chrome-top)" }}
      data-chrome="status"
    >
      <div className="pointer-events-auto flex min-w-0 items-center gap-3">
        <p className="status-title truncate font-mono text-[10px] uppercase tracking-[0.18em] text-[color:var(--muted)]">
          <GradientText className="font-mono text-[10px] uppercase tracking-[0.18em]" animationSpeed={9}>
            {assistantName}
          </GradientText>
          <span className="mx-2 text-[color:var(--muted)]/40">·</span>
          <span className="text-[color:var(--fg)]/90">{focusTitle}</span>
        </p>
      </div>
      <div className="pointer-events-auto flex items-center gap-2">
        <button
          type="button"
          aria-pressed={pinned}
          aria-label={pinned ? "Unpin section" : "Pin section"}
          title={pinned ? "Pinned: automatic scrolls paused" : "Pin: pause automatic scrolls"}
          onClick={() => togglePinned(sessionId)}
          className={[
            "flex h-7 w-7 items-center justify-center rounded-full border transition",
            pinned
              ? "border-[color:var(--accent)]/45 bg-[color:var(--accent)]/12 text-[color:var(--accent)]"
              : "border-[color:var(--border)] bg-black/40 text-[color:var(--muted)] hover:border-[color:var(--accent)]/25 hover:text-[color:var(--accent)]/85",
            hitl ? "opacity-45" : "",
          ].join(" ")}
        >
          <PinIcon pinned={pinned} />
        </button>
        <Notifications />
        <button
          type="button"
          onClick={() => setDesk({ prefsOpen: true })}
          className={[
            "rounded-full border border-[color:var(--border)] bg-black/40 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)] transition hover:border-[color:var(--accent)]/40 hover:text-[color:var(--accent)]",
            hitl ? "opacity-45" : "",
          ].join(" ")}
          title="Preferences: Gmail, voice and connectors"
        >
          Prefs
        </button>
      </div>
    </header>
  );
}
