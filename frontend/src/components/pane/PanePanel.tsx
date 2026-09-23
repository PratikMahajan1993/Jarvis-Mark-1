"use client";

import { motion, useWillChange } from "motion/react";
import { markPaneSettled, usePane } from "@/lib/pane/paneStore";
import { LENS_LAYOUT, type PanelId } from "@/lib/pane/lenses";
import { DEPTH_VARIANTS } from "@/lib/pane/springs";

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
  const { slot, depth } = LENS_LAYOUT[lens][id];
  const willChange = useWillChange();
  const parked = depth === 3;

  return (
    <motion.div
      layout
      layoutId={`panel-${id}`}
      data-panel={id}
      data-depth={depth}
      data-slot={slot}
      className={[
        "pane-frost pointer-events-auto min-h-0 min-w-0 overflow-hidden",
        DEPTH_Z[depth] ?? "z-[11]",
        `slot-${slot}`,
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
      animate={String(depth)}
      initial={false}
      aria-hidden={parked}
      inert={parked ? true : undefined}
      onLayoutAnimationComplete={() => {
        if (depth === 0) {
          onHeroLayoutComplete?.();
          markPaneSettled();
        }
      }}
    >
      <motion.div layout="position" className="h-full min-h-0">
        {children}
      </motion.div>
    </motion.div>
  );
}
