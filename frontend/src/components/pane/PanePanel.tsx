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

function isEmptyBody(node: ReactNode): boolean {
  if (node == null || node === false || node === true) return true;
  if (typeof node === "string" || typeof node === "number") return String(node).trim() === "";
  if (Array.isArray(node)) return node.every(isEmptyBody);
  return false;
}

/** Chrome over the substrate — dots / voice line / activity orb — never a frost slab. */
function isBarePanel(id: PanelId, lens: string): boolean {
  if (id === "voice" && (lens === "converse" || lens === "watch")) return true;
  if (id === "agents" && (lens === "converse" || lens === "watch")) return true;
  if (id === "activity" && (lens === "converse" || lens === "watch")) return true;
  return false;
}

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
  const emptyOptional = (id === "activity" || id === "weather") && isEmptyBody(body);
  const bare = isBarePanel(id, lens) || emptyOptional;
  const hidden = parked || emptyOptional;
  const depthKey = String(depth);
  const allowHits = id === "agents" || id === "activity" || (id === "voice" && lens === "bench");

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
      data-bare={bare ? "1" : undefined}
      data-empty={emptyOptional ? "1" : undefined}
      className={[
        bare
          ? "min-h-0 min-w-0 overflow-visible bg-transparent shadow-none"
          : "pane-frost min-h-0 min-w-0 overflow-hidden",
        allowHits && !hidden ? "pointer-events-auto" : "pointer-events-none",
        DEPTH_Z[depth] ?? "z-[11]",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{
        willChange,
        transformStyle: "preserve-3d",
        visibility: hidden ? "hidden" : "visible",
        contentVisibility: hidden ? "hidden" : "visible",
        ...(bare
          ? {
              borderRadius: 0,
              background: "transparent",
              boxShadow: "none",
              /* Depth variants force opacity/pointerEvents — keep bare chrome clear. */
              pointerEvents: (allowHits && !hidden ? "auto" : "none") as "auto" | "none",
              ...(emptyOptional ? { opacity: 0 } : null),
            }
          : null),
      }}
      variants={DEPTH_VARIANTS}
      animate={depthKey}
      transition={phase === "moving" ? { duration: 0 } : SPRING.pane}
      initial={false}
      aria-hidden={hidden}
      inert={hidden ? true : undefined}
      onLayoutAnimationComplete={() => {
        if (depth === 0 && phase === "settled") {
          onHeroLayoutComplete?.();
          markHeroPanelSettled();
        }
      }}
    >
      <motion.div layout={false} className="h-full min-h-0 overflow-visible">
        {body}
      </motion.div>
    </motion.div>
  );
}
