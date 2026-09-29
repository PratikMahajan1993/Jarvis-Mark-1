"use client";

import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { CommandBaton } from "@/components/orchestrator/CommandBaton";
import { TurnStageLine } from "@/components/orchestrator/TurnStageLine";
import * as desk from "@/core/desk/controller";
import { useTurnView } from "@/core/desk/useTurnView";
import type { SectionDef } from "@/core/sections/defineSection";
import { loadBatonText, saveBatonText } from "@/core/desk/drafts";
import { setDesk, useDesk, getDesk } from "@/core/stores/deskStore";
import { useSectionState } from "@/core/stores/sectionStore";

const DIM = { opacity: 0.35, filter: "blur(2px)", scale: 0.98 };
const REST = { opacity: 1, filter: "blur(0px)", scale: 1 };

/**
 * L3 bottom centre (X7): the command baton in every section. While the page
 * scrolls it dims; it restores when scrolling settles, or at once on focus or
 * typing. It stays interactive throughout.
 */
export function BatonDock({ sections }: { sections: readonly SectionDef[] }) {
  const { hitl, busy, listening, sending, thinking, state } = useTurnView();
  const compose = useDesk((s) => s.compose);
  const ledgerTurnId = useDesk((s) => s.ledgerTurnId);
  const deskError = useDesk((s) => s.error);
  const scrolling = useSectionState((s) => s.scrolling);
  const active = useSectionState((s) => s.active);
  const [engaged, setEngaged] = useState(false);
  const wasScrolling = useRef(scrolling);

  useEffect(() => {
    if (scrolling && !wasScrolling.current) setEngaged(false);
    wasScrolling.current = scrolling;
  }, [scrolling]);

  useEffect(() => {
    if (!getDesk().compose) setDesk({ compose: loadBatonText(active) });
    // Per-section text is restored once the section becomes active, unless something is already typed.
  }, [active]);

  useEffect(() => {
    const t = window.setTimeout(() => saveBatonText(active, compose), 2000);
    return () => window.clearTimeout(t);
  }, [active, compose]);

  const sectionAllowsBaton = sections.find((s) => s.id === active)?.baton !== false;
  const hidden = hitl || !sectionAllowsBaton;
  const dimmed = scrolling && !engaged;
  const error = deskError || (state.mode === "IDLE" && state.error ? state.error : "");

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-0 z-chrome flex flex-col items-center justify-end gap-2 pb-5"
      style={{ height: "var(--chrome-bottom)" }}
      data-chrome="baton"
    >
      <div className="flex min-h-[18px] items-center gap-3" aria-live="polite">
        {sending ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[color:var(--accent)]/80">
            Transmitting…
          </span>
        ) : null}
        <TurnStageLine
          turnId={ledgerTurnId}
          onComplete={desk.onLedgerTurnComplete}
          onFailed={desk.onLedgerTurnFailed}
          onReconcile={desk.onLedgerReconcile}
        />
        {error ? (
          <span className="max-w-md truncate font-mono text-xs text-red-300/80" title={error}>
            {error}
          </span>
        ) : null}
        {thinking ? (
          <button
            type="button"
            className="pointer-events-auto rounded-md border border-[color:var(--accent)]/60 bg-black/50 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[color:var(--accent)]"
            onClick={() => void desk.cancelRun()}
          >
            Cancel
          </button>
        ) : null}
      </div>
      <motion.div
        className="pointer-events-auto"
        initial={false}
        animate={dimmed ? DIM : REST}
        transition={{ duration: dimmed ? 0.18 : 0.3, ease: "easeOut" }}
        onFocusCapture={() => setEngaged(true)}
        onKeyDownCapture={() => setEngaged(true)}
        onPointerDownCapture={() => setEngaged(true)}
        aria-hidden={hidden}
        data-dimmed={dimmed ? "1" : undefined}
      >
        <CommandBaton
          value={compose}
          onChange={(value) => {
            setEngaged(true);
            setDesk({ compose: value });
          }}
          onSubmit={(value) => void desk.send(value)}
          onMic={() => void desk.startMic()}
          listening={listening}
          disabled={busy || hitl}
          hidden={hidden}
          absolute={false}
        />
      </motion.div>
    </div>
  );
}
