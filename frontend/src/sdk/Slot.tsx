"use client";

import { FeatureBoundary } from "@/core/boundary/FeatureBoundary";
import type { SlotId } from "@/core/sections/defineSection";
import { getCardsForSlot } from "./featureRegistry";

export function Slot({ id }: { id: SlotId }) {
  const cards = getCardsForSlot(id);
  if (cards.length === 0) return null;
  return (
    <>
      {cards.map((card) => {
        const Card = card.component;
        return (
          <FeatureBoundary key={card.id} id={`${card.featureId}.${card.id}`}>
            <Card />
          </FeatureBoundary>
        );
      })}
    </>
  );
}
