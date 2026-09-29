"use client";

import { AnimatePresence, motion } from "motion/react";
import * as desk from "@/core/desk/controller";
import { useDesk } from "@/core/stores/deskStore";
import { useTaskQueue } from "@/core/stores/taskQueueStore";
import { SPRING } from "@/lib/pane/springs";

const ENGINEERING_KINDS = new Set(["drawing", "workflow", "job"]);

/**
 * L3 right edge (X8): parked approvals as chips, plus one engineering-tasks chip.
 * A chip only reopens the full Authorize / Reject modal; it can never decide.
 */
export function TaskDock() {
  const parked = useTaskQueue((s) => s.items.filter((a) => s.parkedIds.includes(a.id)));
  const conversations = useDesk((s) => s.desk);
  const engineering = conversations.filter((c) => ENGINEERING_KINDS.has((c.kindLabel || "").toLowerCase()));
  const count = parked.length + (engineering.length ? 1 : 0);

  return (
    <aside
      aria-label="Task dock"
      className="pointer-events-none fixed right-3 top-1/2 z-chrome -translate-y-1/2"
      data-chrome="dock"
    >
      <ul className="pointer-events-auto flex flex-col items-end gap-2">
        <AnimatePresence initial={false}>
          {parked.map((action) => (
            <motion.li
              key={action.id}
              layout
              initial={{ opacity: 0, x: 24, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24, scale: 0.9 }}
              transition={SPRING.chip}
            >
              <button
                type="button"
                onClick={() => desk.resumeHitl(action)}
                title={`${action.title}: reopen to Authorize or Reject`}
                className="group flex max-w-[44px] items-center gap-2 overflow-hidden rounded-full border border-[color:var(--accent)]/40 bg-black/55 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[color:var(--accent)] backdrop-blur transition-[max-width] duration-300 hover:max-w-[240px] focus-visible:max-w-[240px]"
                data-dock-chip="approval"
              >
                <span className="h-2 w-2 shrink-0 rounded-full bg-[color:var(--accent)]" aria-hidden />
                <span className="truncate whitespace-nowrap">{action.title}</span>
              </button>
            </motion.li>
          ))}
          {engineering.length ? (
            <motion.li
              key="engineering-tasks"
              layout
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 24 }}
              transition={SPRING.chip}
            >
              <button
                type="button"
                onClick={() => desk.goToSection("engineering", "dock")}
                className="flex max-w-[44px] items-center gap-2 overflow-hidden rounded-full border border-[color:var(--border)] bg-black/55 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)] backdrop-blur transition-[max-width] duration-300 hover:max-w-[240px] hover:text-[color:var(--fg)] focus-visible:max-w-[240px]"
                data-dock-chip="engineering"
              >
                <span className="shrink-0">{engineering.length}</span>
                <span className="truncate whitespace-nowrap">engineering tasks</span>
              </button>
            </motion.li>
          ) : null}
        </AnimatePresence>
      </ul>
      {count > 0 ? (
        <span
          className="pointer-events-none absolute -left-2 -top-3 rounded-full bg-[color:var(--accent)] px-1.5 font-mono text-[9px] text-black"
          aria-label={`${count} waiting`}
        >
          {count}
        </span>
      ) : null}
    </aside>
  );
}
