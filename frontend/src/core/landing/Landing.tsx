"use client";

import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { getSubstrateState, onSubstrateOut, postSubstrate } from "@/core/root/substrateBridge";
import { prefetchEngineering } from "@/core/sections/registry";
import { useDesk } from "@/core/stores/deskStore";
import { useSubstrateState } from "@/core/root/substrateBridge";

const LANDED_KEY = "jarvis.landed";
const MIN_MS = 1400;
const MIN_REFRESH_MS = 600;
const CAP_MS = 4000;
const GATES = ["substrate", "fonts", "desk", "monitor", "casual", "engineering"] as const;
type Gate = (typeof GATES)[number];

const LABELS: Record<Gate, string> = {
  substrate: "Waking substrate",
  fonts: "Loading fonts",
  desk: "Loading desk",
  monitor: "Loading desk",
  casual: "Loading desk",
  engineering: "Warming engineering",
};

/** L-landing (X1): gates run in parallel; the swarm gathers as they pass. Shown on every full load. */
export function Landing({ onDone }: { onDone: () => void }) {
  const booted = useDesk((s) => s.booted);
  const sub = useSubstrateState();
  const [passed, setPassed] = useState<Set<Gate>>(new Set());
  const [exiting, setExiting] = useState(false);
  const start = useRef(0);
  const done = useRef(false);

  const pass = (g: Gate) => setPassed((p) => (p.has(g) ? p : new Set(p).add(g)));

  useEffect(() => {
    start.current = performance.now();
    postSubstrate({ type: "gather", progress: 0 });
    void document.fonts.ready.then(() => pass("fonts"));
    void Promise.all([prefetchEngineering(), import("@/components/DrawingViewer"), import("pdfjs-dist")])
      .catch(() => undefined)
      .then(() => pass("engineering"));
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
      if ((count === GATES.length && elapsed >= min) || elapsed >= CAP_MS) {
        done.current = true;
        sessionStorage.setItem(LANDED_KEY, "1");
        postSubstrate({ type: "gather", progress: 1 });
        setExiting(true);
        window.setTimeout(onDone, 600);
      }
    }, 100);
    return () => window.clearInterval(tick);
  }, [count, onDone]);

  const current = GATES.find((g) => !passed.has(g));
  const line = exiting || !current ? "Ready" : LABELS[current];

  return (
        <motion.div
          className="fixed inset-0 z-landing flex flex-col items-center justify-end pb-[12vh]"
          style={{ background: "transparent", pointerEvents: exiting ? "none" : "auto" }}
          animate={exiting ? { opacity: 0, filter: "blur(8px)" } : { opacity: 1, filter: "blur(0px)" }}
          transition={{ duration: 0.6 }}
          data-landing
          role="status"
        >
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[color:var(--muted)]">{line}</p>
          <div className="mt-3 h-px w-56 bg-[color:var(--border)]">
            <div
              className="h-px bg-[color:var(--accent)] transition-[width] duration-300"
              style={{ width: `${(count / GATES.length) * 100}%` }}
            />
          </div>
        </motion.div>
  );
}
