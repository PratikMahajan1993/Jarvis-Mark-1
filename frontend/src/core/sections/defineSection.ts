import type { ComponentType } from "react";
import type { HudWorkspace } from "@/components/orchestrator/hudWorkspace";
import type { OrbSpec } from "@/substrate/protocol";
import type { LazyMount } from "@/core/scroll/progress";

export type SlotId =
  | "monitor.main"
  | "monitor.rail"
  | "casual.left"
  | "casual.right"
  | "engineering.side"
  | "engineering.deck-empty";

export type ThemeTokens = {
  bg: string;
  surface: string;
  fg: string;
  muted: string;
  border: string;
  accent: string;
  /** Engineering drafting mat behind the stage. */
  mat?: string;
  /** L0 grid strength, 0…1. */
  gridOpacity?: number;
  /** L0 vignette strength, 0…1. */
  vignetteOpacity?: number;
};

/** L3 decor (X6): SVG only, pointer-events none, at most 4 per section. */
export type DecorPiece = {
  kind: "reticle" | "ticks" | "numeral" | "dimension";
  /** Position inside the section, as fractions of its box. */
  x: number;
  y: number;
  /** Size in viewport heights. */
  size: number;
  /** Parallax factor, 1.2…1.4. */
  depth?: number;
  /** ≤ 0.35 where it overlaps cards. */
  opacity?: number;
  rotate?: number;
  label?: string;
};

export type SectionProps = {
  id: string;
  index: number;
};

export type SectionDef = {
  id: string;
  order: number;
  label: string;
  icon?: string;
  workspace?: HudWorkspace;
  orb: OrbSpec;
  theme: ThemeTokens;
  decor?: DecorPiece[];
  lazy?: LazyMount;
  /** Warm the lazy chunk ahead of time (during the landing). */
  preload?: () => Promise<unknown>;
  /** Show the command baton in this section. Default true. */
  baton?: boolean;
  slots: SlotId[];
  component: ComponentType<SectionProps>;
};

export const MAX_DECOR_PER_SECTION = 4;

export function defineSection(def: SectionDef): SectionDef {
  return def;
}

function inRange(v: number, lo: number, hi: number) {
  return Number.isFinite(v) && v >= lo && v <= hi;
}

/** Throws on the first contract violation; returns the sections sorted by `order`. */
export function validateSections(defs: readonly SectionDef[]): SectionDef[] {
  const ids = new Set<string>();
  const orders = new Set<number>();
  for (const def of defs) {
    const where = `section "${def.id}"`;
    if (!/^[a-z][a-z0-9-]*$/.test(def.id)) throw new Error(`${where}: id must be kebab-case`);
    if (ids.has(def.id)) throw new Error(`${where}: duplicate id`);
    ids.add(def.id);
    if (!Number.isInteger(def.order)) throw new Error(`${where}: order must be an integer`);
    if (orders.has(def.order)) throw new Error(`${where}: duplicate order ${def.order}`);
    orders.add(def.order);
    if (!def.label.trim()) throw new Error(`${where}: label is required`);

    const { placement, dim } = def.orb;
    if (!def.orb.formula) throw new Error(`${where}: orb.formula is required`);
    if (!inRange(placement.center[0], 0, 1) || !inRange(placement.center[1], 0, 1)) {
      throw new Error(`${where}: orb.placement.center must be within 0…1`);
    }
    if (!inRange(placement.height, 0.05, 1.5)) throw new Error(`${where}: orb.placement.height must be within 0.05…1.5`);
    if (!inRange(dim, 0, 1)) throw new Error(`${where}: orb.dim must be within 0…1`);

    const decor = def.decor ?? [];
    if (decor.length > MAX_DECOR_PER_SECTION) {
      throw new Error(`${where}: at most ${MAX_DECOR_PER_SECTION} decor pieces`);
    }
    for (const piece of decor) {
      if (piece.depth != null && !inRange(piece.depth, 1.2, 1.4)) throw new Error(`${where}: decor depth must be 1.2…1.4`);
      if (piece.opacity != null && !inRange(piece.opacity, 0, 0.35)) throw new Error(`${where}: decor opacity must be ≤ 0.35`);
    }

    if (def.lazy) {
      const { mountWithin, unmountBeyond } = def.lazy;
      if (!(mountWithin >= 0) || !(unmountBeyond >= mountWithin)) {
        throw new Error(`${where}: lazy needs 0 ≤ mountWithin ≤ unmountBeyond`);
      }
    }
  }
  return [...defs].sort((a, b) => a.order - b.order);
}
