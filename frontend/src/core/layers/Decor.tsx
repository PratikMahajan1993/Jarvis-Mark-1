"use client";

import { motion, useReducedMotion, useTransform } from "motion/react";
import type { DecorPiece, SectionDef } from "@/core/sections/defineSection";
import { scrollY, sectionHeight } from "@/core/scroll/values";

const DEFAULT_DEPTH = 1.25;
const DEFAULT_OPACITY = 0.2;

function Reticle() {
  return (
    <svg viewBox="-50 -50 100 100" className="h-full w-full" fill="none" stroke="currentColor" strokeWidth="0.18">
      <path d="M -48 0 A 48 48 0 0 1 -34 -34" />
      <path d="M 34 -34 A 48 48 0 0 1 48 0" />
      <path d="M 48 6 A 48 48 0 0 1 20 43.6" />
      <path d="M -20 43.6 A 48 48 0 0 1 -48 6" />
      <path d="M -50 0 H -45 M 45 0 H 50 M 0 -50 V -45 M 0 45 V 50" strokeWidth="0.3" />
    </svg>
  );
}

function Ticks() {
  const ticks = Array.from({ length: 72 }, (_, i) => i * 5);
  return (
    <svg viewBox="-50 -50 100 100" className="h-full w-full" stroke="currentColor" strokeWidth="0.16">
      {ticks.map((deg) => {
        const long = deg % 45 === 0;
        const a = (deg * Math.PI) / 180;
        const r0 = long ? 45 : 47;
        return (
          <line
            key={deg}
            x1={Math.cos(a) * r0}
            y1={Math.sin(a) * r0}
            x2={Math.cos(a) * 49}
            y2={Math.sin(a) * 49}
          />
        );
      })}
    </svg>
  );
}

function Dimension({ label }: { label?: string }) {
  return (
    <svg viewBox="0 0 200 12" className="h-full w-full" fill="none" stroke="currentColor" strokeWidth="0.4">
      <path d="M 1 2 V 10 M 199 2 V 10 M 1 6 H 199" />
      <path d="M 1 6 l 4 -2 M 1 6 l 4 2 M 199 6 l -4 -2 M 199 6 l -4 2" />
      {label ? (
        <text x="100" y="4.5" textAnchor="middle" fontSize="4" fill="currentColor" stroke="none" fontFamily="var(--font-mono)">
          {label}
        </text>
      ) : null}
    </svg>
  );
}

function PieceBody({ piece }: { piece: DecorPiece }) {
  switch (piece.kind) {
    case "reticle":
      return <Reticle />;
    case "ticks":
      return <Ticks />;
    case "dimension":
      return <Dimension label={piece.label} />;
    case "numeral":
      return (
        <span className="block font-mono leading-none tracking-[0.2em]" style={{ fontSize: `${piece.size * 100}vh` }}>
          {piece.label}
        </span>
      );
  }
}

function Piece({ piece, index }: { piece: DecorPiece; index: number }) {
  const reduced = useReducedMotion();
  const depth = reduced ? 1 : (piece.depth ?? DEFAULT_DEPTH);
  // At rest on its own section the piece sits at (x, y); in between it moves at depth × scroll.
  const y = useTransform(() => (index * sectionHeight.get() - scrollY.get()) * depth);
  const size = `${piece.size * 100}vh`;
  const box =
    piece.kind === "dimension"
      ? { width: size, height: `calc(${size} * 0.06)` }
      : piece.kind === "numeral"
        ? {}
        : { width: size, height: size };

  return (
    <motion.div
      className="absolute text-[color:var(--accent)]"
      style={{ left: `${piece.x * 100}%`, top: `${piece.y * 100}vh`, y, opacity: piece.opacity ?? DEFAULT_OPACITY }}
    >
      <div className="-translate-x-1/2 -translate-y-1/2" style={{ ...box, rotate: `${piece.rotate ?? 0}deg` }}>
        <PieceBody piece={piece} />
      </div>
    </motion.div>
  );
}

/** L3 decor (X6): hairline SVG pieces over the content, under the chrome. Never interactive. */
export function DecorLayer({ sections }: { sections: readonly SectionDef[] }) {
  return (
    <div className="pointer-events-none fixed inset-0 z-decor overflow-hidden" aria-hidden data-layer="decor">
      {sections.flatMap((section, index) =>
        (section.decor ?? []).map((piece, i) => <Piece key={`${section.id}-${i}`} piece={piece} index={index} />),
      )}
    </div>
  );
}
