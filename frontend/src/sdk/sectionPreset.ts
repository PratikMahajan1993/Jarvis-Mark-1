import type { ThemeTokens } from "@/core/sections/defineSection";
import type { OrbSpec } from "@/substrate/protocol";

/** Neutral theme for a scaffolded feature section. The feature may replace it. */
export const FEATURE_SECTION_THEME: ThemeTokens = {
  bg: "oklch(10% 0.006 240)",
  surface: "oklch(14% 0.008 240)",
  fg: "oklch(95% 0.004 240)",
  muted: "oklch(62% 0.008 240)",
  border: "oklch(22% 0.01 240)",
  accent: "oklch(74% 0.12 165)",
  gridOpacity: 0.12,
  vignetteOpacity: 0.7,
};

/** A valid orb spec using a formula the substrate already runs. */
export function featureSectionOrb(): OrbSpec {
  return {
    formula: "chat-gpt",
    placement: { center: [0.5, 0.46], height: 0.42 },
    dim: 0.45,
    states: {
      idle: { rate: 1 },
      listening: { rate: 0.7 },
      thinking: { rate: 2 },
      speaking: { rate: 1 },
      hitl: { rate: 0.5 },
    },
  };
}
