"use client";

import { motion, useReducedMotion, useTransform, type MotionValue } from "motion/react";
import type { SectionDef } from "@/core/sections/defineSection";
import { scrollProgress, scrollY } from "@/core/scroll/values";

const PARALLAX = -0.3;

const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E\")";

/** Section i fades in over section i − 1 as the page scrolls from i − 1 to i. */
function TintLayer({ index, color }: { index: number; color: string }) {
  const opacity = useTransform(scrollProgress, [index - 1, index], [0, 1], { clamp: true });
  return <motion.div className="absolute inset-0" style={{ background: color, opacity }} />;
}

function stops(sections: readonly SectionDef[], pick: (s: SectionDef) => number): [number[], number[]] {
  return [sections.map((_, i) => i), sections.map(pick)];
}

function useStops(sections: readonly SectionDef[], pick: (s: SectionDef) => number): MotionValue<number> {
  const [input, output] = stops(sections, pick);
  return useTransform(scrollProgress, input.length > 1 ? input : [0, 1], output.length > 1 ? output : [output[0]!, output[0]!]);
}

/**
 * L0 (X6): section tint blend, the Engineering grid, grain and vignette.
 * Texture drifts at −0.3 × scroll; the tint and vignette stay put.
 */
export function Backdrop({ sections }: { sections: readonly SectionDef[] }) {
  const reduced = useReducedMotion();
  const drift = useTransform(scrollY, (y) => (reduced ? 0 : y * PARALLAX));
  const gridOpacity = useStops(sections, (s) => s.theme.gridOpacity ?? 0);
  const vignetteOpacity = useStops(sections, (s) => s.theme.vignetteOpacity ?? 0.8);
  const textureHeight = `${100 + 30 * Math.max(0, sections.length - 1)}vh`;

  return (
    <div className="pointer-events-none fixed inset-0 z-backdrop overflow-hidden" aria-hidden data-layer="backdrop">
      <div className="absolute inset-0" style={{ background: sections[0]?.theme.bg }} />
      {sections.slice(1).map((s, i) => (
        <TintLayer key={s.id} index={i + 1} color={s.theme.bg} />
      ))}

      <motion.div className="absolute inset-x-0 top-0 will-change-transform" style={{ y: drift, height: textureHeight }}>
        <motion.div
          className="absolute inset-0"
          style={{
            opacity: gridOpacity,
            backgroundImage:
              "linear-gradient(rgba(125, 255, 224, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(125, 255, 224, 0.05) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.035] mix-blend-overlay"
          style={{ backgroundImage: GRAIN, backgroundSize: "160px 160px" }}
        />
      </motion.div>

      <motion.div
        className="absolute inset-0"
        style={{
          opacity: vignetteOpacity,
          background: "radial-gradient(circle, transparent 40%, rgba(0, 0, 0, 0.8) 100%)",
        }}
      />
    </div>
  );
}
