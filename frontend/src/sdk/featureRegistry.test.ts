import { describe, expect, it } from "vitest";
import { defineSection, validateSections, type SectionDef } from "@/core/sections/defineSection";
import {
  defineFeature,
  getCardsForSlot,
  registeredSections,
  validateFeatureList,
} from "./featureRegistry";
import { FEATURE_SECTION_THEME, featureSectionOrb } from "./sectionPreset";

function ProbeSection() {
  return null;
}

describe("validateFeatureList", () => {
  it("accepts unique kebab ids", () => {
    expect(validateFeatureList(["weather", "tool-wear"])).toEqual({ ok: true });
  });

  it("rejects duplicates", () => {
    const r = validateFeatureList(["weather", "weather"]);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/duplicate/);
  });

  it("rejects invalid ids", () => {
    const r = validateFeatureList(["Weather"]);
    expect(r.ok).toBe(false);
  });
});

describe("feature sections", () => {
  it("joins a declared section into the desk and accepts its slot", () => {
    defineFeature({
      id: "plug-probe",
      sections: [
        defineSection({
          id: "plug-probe",
          order: 400,
          label: "Plug",
          orb: featureSectionOrb(),
          theme: FEATURE_SECTION_THEME,
          slots: ["plug-probe.main"],
          component: ProbeSection,
        }),
      ],
      cards: [{ id: "plug-probe.card", slot: "plug-probe.main", component: ProbeSection }],
    });
    expect(registeredSections().some((section) => section.id === "plug-probe")).toBe(true);
    const core = [
      defineSection({
        id: "monitor",
        order: 100,
        label: "Monitor",
        orb: featureSectionOrb(),
        theme: FEATURE_SECTION_THEME,
        slots: ["monitor.main"],
        component: ProbeSection,
      }),
    ] satisfies SectionDef[];
    expect(validateSections([...core, ...registeredSections()]).map((section) => section.id)).toEqual([
      "monitor",
      "plug-probe",
    ]);
    expect(getCardsForSlot("plug-probe.main")).toHaveLength(1);
    expect(featureSectionOrb().formula).toBe("chat-gpt");
    expect(FEATURE_SECTION_THEME.accent.length).toBeGreaterThan(0);
  });
});
