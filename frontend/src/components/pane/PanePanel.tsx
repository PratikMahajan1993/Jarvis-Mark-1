"use client";

import { motion, useWillChange } from "motion/react";
import { useLayoutEffect, useRef, type ReactNode } from "react";
import { markHeroPanelSettled, usePane } from "@/lib/pane/paneStore";
import { LENS_LAYOUT, type PanelId } from "@/lib/pane/lenses";
import { DEPTH_VARIANTS, SPRING } from "@/lib/pane/springs";

const DEPTH_Z: Record<number, string> = {
  0: "z-[14]",
  1: "z-[13]",
  2: "z-[12]",
  3: "z-[11]",
};

export function PanePanel({
  id,
  children,
  className = "",
  onHeroLayoutComplete,
}: {
  id: PanelId;
  children: React.ReactNode;
  className?: string;
  onHeroLayoutComplete?: () => void;
}) {
  const lens = usePane((s) => s.lens);
  const phase = usePane((s) => s.phase);
  const { depth } = LENS_LAYOUT[lens][id];
  const willChange = useWillChange();
  const parked = depth === 3;
  const frozenBody = useRef<ReactNode>(children);
  if (phase === "settled") {
    frozenBody.current = children;
  }
  const body = phase === "moving" ? frozenBody.current : children;
  const depthKey = String(depth);

  useLayoutEffect(() => {
    if (phase !== "moving" || depth !== 0) return;
    onHeroLayoutComplete?.();
    markHeroPanelSettled();
  }, [phase, depth, lens, onHeroLayoutComplete]);

  return (
    <motion.div
      layout={phase === "settled"}
      layoutId={`panel-${id}`}
      data-panel={id}
      data-depth={depth}
      className={[
        "pane-frost pointer-events-auto min-h-0 min-w-0 overflow-hidden",
        DEPTH_Z[depth] ?? "z-[11]",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{
        willChange,
        transformStyle: "preserve-3d",
        visibility: parked ? "hidden" : "visible",
        contentVisibility: parked ? "hidden" : "visible",
      }}
      variants={DEPTH_VARIANTS}
      animate={depthKey}
      transition={phase === "moving" ? { duration: 0 } : SPRING.pane}
      initial={false}
      aria-hidden={parked}
      inert={parked ? true : undefined}
      onLayoutAnimationComplete={() => {
        if (depth === 0 && phase === "settled") {
          onHeroLayoutComplete?.();
          markHeroPanelSettled();
        }
      }}
    >
      <motion.div layout={false} className="h-full min-h-0">
        {body}
      </motion.div>
    </motion.div>
  );
}
