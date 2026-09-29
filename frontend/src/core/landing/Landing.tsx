"use client";

import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { getSubstrateState, onSubstrateOut, postSubstrate } from "@/core/root/substrateBridge";
import { prefetchEngineering } from "@/core/sections/registry";
import { useDesk } from "@/core/stores/deskStore";
import { useSubstrateState } from "@/core/root/substrateBridge";
import { LandingReadout } from "./LandingFrame";
import { GATES, gatesComplete, landingStatusLine, type Gate } from "./landingStatus";

const LANDED_KEY = "jarvis.landed";
const MIN_MS = 1400;
const MIN_REFRESH_MS = 600;
const CAP_MS = 4000;

/** L-landing (X1): gates run in parallel; the swarm gathers as they pass. Shown on every full load. */
export function Landing({ onDone }: { onDone: () => void }) {
  const booted = useDesk((s) => s.booted);
  const sub = useSubstrateState();
  const [passed, setPassed] = useState<Set<Gate>>(new Set());
  const [hermesDone, setHermesDone] = useState(false);
  const [exiting, setExiting] = useState(false);
  const start = useRef(0);
  const done = useRef(false);

  const pass = (g: Gate) => setPassed((p) => (p.has(g) ? p : new Set(p).add(g)));

  useEffect(() => {
    document.querySelector("[data-landing-static]")?.remove();
    start.current = performance.now();
    postSubstrate({ type: "gather", progress: 0 });
    void document.fonts.ready.then(() => pass("fonts"));
    void Promise.all([prefetchEngineering(), import("@/components/DrawingViewer"), import("pdfjs-dist")])
      .catch(() => undefined)
      .then(() => pass("engineering"));
    // Display-only: status can say "Checking Hermes"; never added to GATES.
    void api
      .health()
      .catch(() => null)
      .finally(() => setHermesDone(true));
    return onSubstrateOut((m) => {
      if (m.type === "contextLost") pass("substrate");
    });
  }, []);

  useEffect(() => {
    if (sub.ready || getSubstrateState().contextLost) pass("substrate");
  }, [sub.ready, sub.contextLost]);
  useEffect(() => {
    if (booted) pass("desk");
  }, [booted]);
  useEffect(() => {
    // Monitor and Casual mount eagerly with the stack; each passes once its content is in the DOM.
    const seen = (id: string) =>
      document.querySelector(`[data-section="${id}"] [data-section-content]`) !== null;
    const poll = window.setInterval(() => {
      if (seen("monitor")) pass("monitor");
      if (seen("casual")) pass("casual");
    }, 50);
    return () => window.clearInterval(poll);
  }, []);

  const count = passed.size;
  useEffect(() => {
    postSubstrate({ type: "gather", progress: count / GATES.length });
  }, [count]);

  useEffect(() => {
    const refresh = sessionStorage.getItem(LANDED_KEY) === "1";
    const min = refresh ? MIN_REFRESH_MS : MIN_MS;
    const tick = window.setInterval(() => {
      if (done.current) return;
      const elapsed = performance.now() - start.current;
      if ((gatesComplete(passed) && elapsed >= min) || elapsed >= CAP_MS) {
        done.current = true;
        sessionStorage.setItem(LANDED_KEY, "1");
        postSubstrate({ type: "gather", progress: 1 });
        setExiting(true);
        window.setTimeout(onDone, 600);
      }
    }, 100);
    return () => window.clearInterval(tick);
  }, [passed, onDone]);

  const line = landingStatusLine({ passed, hermesDone, exiting });

  return (
    <motion.div
      className="fixed inset-0 z-landing flex flex-col items-center justify-end pb-[12vh]"
      style={{ background: "transparent", pointerEvents: exiting ? "none" : "auto" }}
      animate={exiting ? { opacity: 0, filter: "blur(8px)" } : { opacity: 1, filter: "blur(0px)" }}
      transition={{ duration: 0.6 }}
      data-landing
      role="status"
    >
      <LandingReadout line={line} progress={count / GATES.length} />
    </motion.div>
  );
}
