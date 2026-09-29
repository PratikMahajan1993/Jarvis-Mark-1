"use client";

import { MotionConfig } from "motion/react";
import { Profiler } from "react";
import { PerfOverlay } from "@/components/PerfOverlay";
import { BatonDock } from "@/core/chrome/BatonDock";
import { Modals } from "@/core/chrome/Modals";
import { SectionNav } from "@/core/chrome/SectionNav";
import { StatusCluster } from "@/core/chrome/StatusCluster";
import { ThemeSync } from "@/core/chrome/ThemeSync";
import { Backdrop } from "@/core/layers/Backdrop";
import { DecorLayer } from "@/core/layers/Decor";
import { SectionStack } from "@/core/sections/SectionStack";
import { SECTIONS } from "@/core/sections/registry";
import { isJarvisPerfMode, recordOrchestratorShellCommit } from "@/lib/pane/perf";
import { DeskController } from "./DeskController";
import { goToSection } from "./controller";

/**
 * The desk on `/`: L0 backdrop, L2 sections (L1 substrate is hoisted in
 * JarvisRoot), L3 decor and chrome, then the modal tier.
 */
export function Desk() {
  const perf = isJarvisPerfMode();
  const tree = (
    <MotionConfig reducedMotion="user">
      <DeskController />
      <ThemeSync sections={SECTIONS} />
      <Backdrop sections={SECTIONS} />
      <SectionStack sections={SECTIONS} onUserNavigate={goToSection} />
      <DecorLayer sections={SECTIONS} />
      <StatusCluster />
      <SectionNav sections={SECTIONS} onNavigate={goToSection} />
      <BatonDock sections={SECTIONS} />
      <Modals />
    </MotionConfig>
  );

  if (!perf) return tree;
  return (
    <>
      <Profiler id="Desk" onRender={recordOrchestratorShellCommit}>
        <span data-orch-shell-probe hidden aria-hidden />
      </Profiler>
      <PerfOverlay />
      {tree}
    </>
  );
}
