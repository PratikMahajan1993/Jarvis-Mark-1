"use client";

import { Suspense, useEffect, useRef, useState, type CSSProperties } from "react";
import { FeatureBoundary } from "@/core/boundary/FeatureBoundary";
import { startScrollEngine } from "@/core/scroll/engine";
import { nextMounted } from "@/core/scroll/progress";
import { sectionStore } from "@/core/stores/sectionStore";
import type { SectionDef } from "./defineSection";
import { themeVars } from "./themes";

function sameFlags(a: readonly boolean[], b: readonly boolean[]) {
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

function whenIdle(fn: () => void): () => void {
  if (typeof window.requestIdleCallback === "function") {
    const id = window.requestIdleCallback(fn, { timeout: 4000 });
    return () => window.cancelIdleCallback(id);
  }
  const id = window.setTimeout(fn, 1500);
  return () => window.clearTimeout(id);
}

function SectionFrame({ def, index, mounted }: { def: SectionDef; index: number; mounted: boolean }) {
  const Component = def.component;
  return (
    <section
      data-section={def.id}
      data-section-index={index}
      aria-label={def.label}
      className="relative h-[100dvh] w-full overflow-hidden"
      style={themeVars(def.theme) as CSSProperties}
    >
      <div
        className="absolute px-3 pb-2 pt-2"
        style={{
          top: "var(--chrome-top)",
          bottom: "var(--chrome-bottom)",
          left: "var(--nav-w)",
          right: "var(--dock-w)",
        }}
        data-section-content
      >
        <FeatureBoundary id={def.label}>
          <Suspense fallback={null}>{mounted ? <Component id={def.id} index={index} /> : null}</Suspense>
        </FeatureBoundary>
      </div>
    </section>
  );
}

/**
 * L2: every section, top to bottom by `order`, each exactly one viewport tall.
 * Owns the scroll engine because it owns the section elements.
 */
export function SectionStack({
  sections,
  onUserNavigate,
}: {
  sections: readonly SectionDef[];
  onUserNavigate: (sectionId: string, reason: string) => void;
}) {
  const stackRef = useRef<HTMLElement>(null);
  const navigateRef = useRef(onUserNavigate);
  navigateRef.current = onUserNavigate;
  const lazies = sections.map((s) => s.lazy);
  const [mounted, setMounted] = useState(() => nextMounted([], sectionStore.get().progress, lazies));

  useEffect(() => {
    const lazyDefs = sections.map((s) => s.lazy);
    const sync = () =>
      setMounted((prev) => {
        const next = nextMounted(prev, sectionStore.get().progress, lazyDefs);
        return sameFlags(prev, next) ? prev : next;
      });
    sync();
    return sectionStore.subscribe(sync);
  }, [sections]);

  useEffect(() => {
    const stack = stackRef.current;
    if (!stack) return;
    return startScrollEngine(sections, stack, {
      onUserNavigate: (id, reason) => navigateRef.current(id, reason),
    });
  }, [sections]);

  useEffect(() => whenIdle(() => sections.forEach((s) => void s.preload?.())), [sections]);

  return (
    <main ref={stackRef} className="relative z-content" data-section-stack>
      {sections.map((def, i) => (
        <SectionFrame key={def.id} def={def} index={i} mounted={mounted[i] ?? true} />
      ))}
    </main>
  );
}
