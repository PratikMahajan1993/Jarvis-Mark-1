"use client";

import "@/features";
import { LayoutGroup, MotionConfig, motion, useReducedMotion } from "motion/react";
import { Profiler, useState } from "react";
import { Landing } from "@/core/landing/Landing";
import { PerfOverlay } from "@/components/PerfOverlay";
import { BatonDock } from "@/core/chrome/BatonDock";
import { Modals } from "@/core/chrome/Modals";
import { SectionNav } from "@/core/chrome/SectionNav";
import { TaskDock } from "@/core/chrome/TaskDock";
import { ToastLayer } from "@/core/chrome/ToastLayer";
import { StatusCluster } from "@/core/chrome/StatusCluster";
import { ThemeSync } from "@/core/chrome/ThemeSync";
import { Backdrop } from "@/core/layers/Backdrop";
import { DecorLayer } from "@/core/layers/Decor";
import { SectionStack } from "@/core/sections/SectionStack";
import { getDeskSections } from "@/core/sections/registry";
import { isJarvisPerfMode, recordOrchestratorShellCommit } from "@/lib/pane/perf";
import { DeskController } from "./DeskController";
import { goToSection } from "./controller";

const CHROME_STAGGER_S = 0.08;
const CHROME_FADE_S = 0.35;
const CHROME_REDUCED_S = 0.2;

/**
 * The desk on `/`: L0 backdrop, L2 sections (L1 substrate is hoisted in
 * JarvisRoot), L3 decor and chrome, then the modal tier.
 */
export function Desk() {
  const perf = isJarvisPerfMode();
  const [landed, setLanded] = useState(false);
  const reduced = useReducedMotion();
  const sections = getDeskSections();

  const chromeFade = (index: number) => ({
    opacity: landed ? 1 : 0,
    transition: reduced
      ? { duration: CHROME_REDUCED_S, delay: 0 }
      : { duration: CHROME_FADE_S, delay: landed ? index * CHROME_STAGGER_S : 0 },
  });

  const tree = (
    <MotionConfig reducedMotion="user">
      <LayoutGroup id="hitl-park">
        <DeskController />
        <ThemeSync sections={sections} />
        <Backdrop sections={sections} />
        <SectionStack sections={sections} onUserNavigate={goToSection} />
        <DecorLayer sections={sections} />
        <div data-chrome-root>
          <motion.div
            animate={chromeFade(0)}
            style={{ pointerEvents: landed ? "auto" : "none" }}
            data-chrome="status"
          >
            <StatusCluster />
          </motion.div>
          <motion.div
            animate={chromeFade(1)}
            style={{ pointerEvents: landed ? "auto" : "none" }}
            data-chrome="nav"
          >
            <SectionNav sections={sections} onNavigate={goToSection} />
          </motion.div>
          <motion.div
            animate={chromeFade(2)}
            style={{ pointerEvents: landed ? "auto" : "none" }}
            data-chrome="dock"
          >
            <TaskDock />
          </motion.div>
          <div
            style={{ opacity: landed ? 1 : 0, pointerEvents: landed ? "auto" : "none" }}
            aria-hidden={!landed}
          >
            <ToastLayer />
          </div>
          <motion.div
            animate={chromeFade(3)}
            style={{ pointerEvents: landed ? "auto" : "none" }}
            data-chrome="baton"
          >
            <BatonDock sections={sections} />
          </motion.div>
        </div>
        <Modals />
        {landed ? null : <Landing onDone={() => setLanded(true)} />}
      </LayoutGroup>
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
