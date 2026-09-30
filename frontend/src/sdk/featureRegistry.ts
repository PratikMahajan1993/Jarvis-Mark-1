import { createElement, type ComponentType } from "react";
import {
  CORE_SLOTS,
  isSlotId,
  type SectionDef,
  type SectionProps,
  type SlotId,
} from "@/core/sections/defineSection";
import { isFeatureEnabled, setFeatureFlagDefault } from "./featureFlags";

const KNOWN_SLOTS: Set<string> = new Set(CORE_SLOTS);

export type CardDef = {
  id: string;
  slot: SlotId;
  component: ComponentType;
  order?: number;
  size?: "sm" | "md" | "lg";
  flag?: { default: boolean };
};

export type FeatureDef = {
  id: string;
  title?: string;
  flag?: { default: boolean };
  sections?: SectionDef[];
  cards?: CardDef[];
};

type RegisteredCard = CardDef & { featureId: string; order: number };

const _features: FeatureDef[] = [];
const _cards: RegisteredCard[] = [];
const _sections: SectionDef[] = [];

function gateSection(featureId: string, section: SectionDef): SectionDef {
  const Component = section.component;
  function GatedSection(props: SectionProps) {
    if (!isFeatureEnabled(featureId)) return null;
    return createElement(Component, props);
  }
  return { ...section, component: GatedSection };
}

function fail(message: string): never {
  throw new Error(`[features] ${message}`);
}

function warnOrThrow(message: string) {
  if (process.env.NODE_ENV === "production") {
    console.error(`[features] ${message}`);
    return;
  }
  fail(message);
}

/** Card helper for feature manifests — returns the def for the `cards` array. */
export function defineCard(def: CardDef): CardDef;
export function defineCard(def: CardDef, featureId: string): RegisteredCard | null;
export function defineCard(def: CardDef, featureId?: string): CardDef | RegisteredCard | null {
  if (featureId === undefined) return def;
  if (!KNOWN_SLOTS.has(def.slot)) {
    warnOrThrow(`card "${def.id}" uses unknown slot "${def.slot}"`);
    return null;
  }
  if (_cards.some((c) => c.id === def.id)) {
    warnOrThrow(`duplicate card id "${def.id}"`);
    return null;
  }
  if (def.flag) setFeatureFlagDefault(def.id, def.flag.default);
  const card: RegisteredCard = {
    ...def,
    featureId,
    order: def.order ?? 0,
  };
  _cards.push(card);
  return card;
}

export function defineFeature(def: FeatureDef): FeatureDef {
  if (_features.some((f) => f.id === def.id)) {
    warnOrThrow(`duplicate feature id "${def.id}"`);
    return def;
  }
  if (def.flag) setFeatureFlagDefault(def.id, def.flag.default);
  _features.push({ id: def.id, title: def.title, flag: def.flag });
  for (const section of def.sections ?? []) {
    if (_sections.some((existing) => existing.id === section.id)) {
      warnOrThrow(`duplicate section id "${section.id}"`);
      continue;
    }
    for (const slot of section.slots) {
      if (!isSlotId(slot)) {
        warnOrThrow(`section "${section.id}" uses invalid slot "${slot}"`);
        continue;
      }
      KNOWN_SLOTS.add(slot);
    }
    _sections.push(gateSection(def.id, section));
  }
  for (const card of def.cards ?? []) {
    defineCard(card, def.id);
  }
  return def;
}

/** Feature sections, in registration order. The desk merges these with the core three. */
export function registeredSections(): readonly SectionDef[] {
  return _sections;
}

export function getCardsForSlot(slot: SlotId): RegisteredCard[] {
  return _cards.filter((c) => c.slot === slot).sort((a, b) => a.order - b.order);
}

export function registeredFeatures(): readonly FeatureDef[] {
  return _features;
}

/** Pure check used by vitest — does not mutate the live registry. */
export function validateFeatureList(ids: readonly string[]): { ok: true } | { ok: false; error: string } {
  const seen = new Set<string>();
  for (const id of ids) {
    if (!id || !/^[a-z][a-z0-9-]*$/.test(id)) {
      return { ok: false, error: `invalid feature id "${id}"` };
    }
    if (seen.has(id)) return { ok: false, error: `duplicate feature id "${id}"` };
    seen.add(id);
  }
  return { ok: true };
}
