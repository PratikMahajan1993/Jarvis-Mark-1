"use client";

import { lazy } from "react";
import { registeredSections } from "@/sdk/featureRegistry";
import { defineSection, validateSections, type SectionDef } from "./defineSection";
import { CasualSection } from "./casual/CasualSection";
import { MonitorSection } from "./monitor/MonitorSection";
import { CASUAL_ORB, ENGINEERING_ORB, MONITOR_ORB } from "./orbs";
import { CASUAL_THEME, ENGINEERING_THEME, MONITOR_THEME } from "./themes";

const loadEngineering = () => import("./engineering/EngineeringSection");

export const prefetchEngineering = () => loadEngineering();

const monitor = defineSection({
  id: "monitor",
  order: 100,
  label: "Monitor",
  workspace: "monitor",
  orb: MONITOR_ORB,
  theme: MONITOR_THEME,
  decor: [
    { kind: "reticle", x: 0.5, y: 0.46, size: 0.86, depth: 1.25, opacity: 0.16 },
    { kind: "numeral", x: 0.06, y: 0.9, size: 0.06, depth: 1.3, opacity: 0.22, label: "01" },
  ],
  slots: ["monitor.main", "monitor.rail"],
  component: MonitorSection,
});

const casual = defineSection({
  id: "casual",
  order: 200,
  label: "Casual",
  workspace: "casual",
  orb: CASUAL_ORB,
  theme: CASUAL_THEME,
  decor: [
    { kind: "ticks", x: 0.5, y: 0.47, size: 0.74, depth: 1.2, opacity: 0.14 },
    { kind: "numeral", x: 0.06, y: 0.9, size: 0.06, depth: 1.3, opacity: 0.22, label: "02" },
  ],
  slots: ["casual.left", "casual.right"],
  component: CasualSection,
});

const engineering = defineSection({
  id: "engineering",
  order: 300,
  label: "Engineering",
  workspace: "engineering",
  orb: ENGINEERING_ORB,
  theme: ENGINEERING_THEME,
  decor: [
    { kind: "dimension", x: 0.36, y: 0.035, size: 0.6, depth: 1.35, opacity: 0.2, label: "A1 · 841" },
    { kind: "numeral", x: 0.06, y: 0.9, size: 0.06, depth: 1.3, opacity: 0.22, label: "03" },
  ],
  lazy: { mountWithin: 1, unmountBeyond: 2 },
  preload: loadEngineering,
  slots: ["engineering.side", "engineering.deck-empty"],
  component: lazy(loadEngineering),
});

/** Core sections plus every feature section, sorted by `order`. Called on render so plug-in sections have registered. */
export function getDeskSections(): readonly SectionDef[] {
  return validateSections([monitor, casual, engineering, ...registeredSections()]);
}

export function sectionById(id: string): SectionDef | undefined {
  return getDeskSections().find((s) => s.id === id);
}
