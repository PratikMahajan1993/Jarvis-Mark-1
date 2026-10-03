import { defineFeature, defineSection, FEATURE_SECTION_THEME, featureSectionOrb } from "@/sdk";
import { SheetsSection } from "./SheetsSection";

defineFeature({
  id: "sheets",
  title: "Sheets",
  sections: [
    defineSection({
      id: "sheets",
      order: 400,
      label: "Sheets",
      orb: featureSectionOrb(),
      theme: FEATURE_SECTION_THEME,
      lazy: { mountWithin: 1, unmountBeyond: 2 },
      slots: ["sheets.main"],
      component: SheetsSection,
    }),
  ],
});

