"use client";

import { useEffect } from "react";
import type { SectionDef } from "@/core/sections/defineSection";
import { themeVars } from "@/core/sections/themes";
import { useSectionState } from "@/core/stores/sectionStore";

/** Chrome and decor live outside the sections, so the root carries the active section's theme. */
export function ThemeSync({ sections }: { sections: readonly SectionDef[] }) {
  const active = useSectionState((s) => s.active);

  useEffect(() => {
    const def = sections.find((s) => s.id === active) ?? sections[0];
    if (!def) return;
    const root = document.documentElement;
    const vars = themeVars(def.theme);
    for (const [k, v] of Object.entries(vars)) root.style.setProperty(k, v);
    root.dataset.activeSection = def.id;
  }, [active, sections]);

  useEffect(
    () => () => {
      const root = document.documentElement;
      for (const k of Object.keys(themeVars(sections[0]!.theme))) root.style.removeProperty(k);
      delete root.dataset.activeSection;
    },
    [sections],
  );

  return null;
}
