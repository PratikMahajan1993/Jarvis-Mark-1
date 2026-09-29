"use client";

import { motion, useTransform } from "motion/react";
import type { SectionDef } from "@/core/sections/defineSection";
import { scrollProgress } from "@/core/scroll/values";
import { useSectionState } from "@/core/stores/sectionStore";

const ROW_PX = 36;

/** L3 left edge (X2): section labels plus a live progress mark. A click is a user scroll. */
export function SectionNav({
  sections,
  onNavigate,
}: {
  sections: readonly SectionDef[];
  onNavigate: (sectionId: string, reason: string) => void;
}) {
  const active = useSectionState((s) => s.active);
  const last = Math.max(1, sections.length - 1);
  const markY = useTransform(scrollProgress, [0, last], [0, last * ROW_PX], { clamp: true });

  return (
    <nav
      aria-label="Sections"
      className="pointer-events-none fixed left-0 top-1/2 z-chrome -translate-y-1/2 pl-4"
      style={{ width: "var(--nav-w)" }}
      data-chrome="nav"
    >
      <div className="relative">
        <span
          className="absolute left-[3px] top-[18px] w-px bg-[color:var(--border)]"
          style={{ height: last * ROW_PX }}
          aria-hidden
        />
        <motion.span
          className="absolute left-0 top-[15px] h-[7px] w-[7px] rounded-full bg-[color:var(--accent)] shadow-[0_0_10px_color-mix(in_oklch,var(--accent)_60%,transparent)]"
          style={{ y: markY }}
          aria-hidden
          data-nav-mark
        />
        <ol className="pointer-events-auto relative">
          {sections.map((s, i) => {
            const isActive = s.id === active;
            return (
              <li key={s.id} style={{ height: ROW_PX }}>
                <button
                  type="button"
                  onClick={() => onNavigate(s.id, "nav")}
                  aria-current={isActive ? "true" : undefined}
                  title={`${s.label} (Alt+${i + 1})`}
                  className={[
                    "flex h-full w-full items-center gap-3 pl-4 text-left font-mono text-[10px] uppercase tracking-[0.14em] transition",
                    isActive
                      ? "text-[color:var(--accent)]"
                      : "text-[color:var(--muted)]/70 hover:text-[color:var(--fg)]",
                  ].join(" ")}
                >
                  <span className="text-[9px] opacity-60">{String(i + 1).padStart(2, "0")}</span>
                  <span className="truncate">{s.label}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>
    </nav>
  );
}
