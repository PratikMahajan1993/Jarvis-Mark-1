import type { ComponentType } from "react";
import type { SlotId } from "@/core/sections/defineSection";

export type CardDef = {
  id: string;
  slot: SlotId;
  component: ComponentType;
  order?: number;
};

export type FeatureDef = {
  id: string;
  title?: string;
  cards?: CardDef[];
};

type RegisteredCard = CardDef & { featureId: string; order: number };

const _features: FeatureDef[] = [];
const _cards: RegisteredCard[] = [];

export function defineCard(def: CardDef, featureId: string): RegisteredCard {
  const card: RegisteredCard = {
    ...def,
    featureId,
    order: def.order ?? 0,
  };
  if (process.env.NODE_ENV !== "production") {
    if (_cards.some((c) => c.id === card.id)) {
      throw new Error(`duplicate card id "${card.id}"`);
    }
  }
  _cards.push(card);
  return card;
}

export function defineFeature(def: FeatureDef): FeatureDef {
  if (process.env.NODE_ENV !== "production") {
    if (_features.some((f) => f.id === def.id)) {
      throw new Error(`duplicate feature id "${def.id}"`);
    }
  }
  _features.push({ id: def.id, title: def.title });
  for (const card of def.cards ?? []) {
    defineCard(card, def.id);
  }
  return def;
}

export function getCardsForSlot(slot: SlotId): RegisteredCard[] {
  return _cards.filter((c) => c.slot === slot).sort((a, b) => a.order - b.order);
}

export function registeredFeatures(): readonly FeatureDef[] {
  return _features;
}
