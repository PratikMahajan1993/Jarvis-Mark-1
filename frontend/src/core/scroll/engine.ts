"use client";

import Lenis, { type VirtualScrollData } from "lenis";
import Snap from "lenis/snap";
import { cancelFrame, frame } from "motion/react";
import type { SectionDef } from "@/core/sections/defineSection";
import { postSubstrate } from "@/core/root/substrateBridge";
import {
  reportScroll,
  sectionStore,
  setScrolling,
  type SectionRequest,
} from "@/core/stores/sectionStore";
import { liveLog } from "@/lib/liveLog";
import {
  activeFromProgress,
  blendChanged,
  expoOut,
  resolveOrbBlend,
  sectionForKey,
  type Jump,
  type OrbBlend,
} from "./progress";
import { scrollProgress, scrollY, sectionHeight } from "./values";

const JUMP_BASE_S = 0.9;
const JUMP_PER_EXTRA_SECTION_S = 0.2;
const SNAP_S = 0.9;
const SCROLLING_VELOCITY = 0.8;
const SETTLE_MS = 400;
const ALIGN_EPS = 0.01;

/** Requests already executed, across engine instances (StrictMode remounts must not replay a jump). */
let executedRequestId = 0;

export type ScrollEngineOptions = {
  /** A user key press (PageUp/PageDown, Alt+n) asks for a section. */
  onUserNavigate: (sectionId: string, reason: string) => void;
};

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") return true;
  if (tag !== "INPUT") return false;
  // Section keys never edit a single-line text field, so the (always focused) baton does not swallow them.
  const type = (target as HTMLInputElement).type;
  return !(type === "text" || type === "search" || type === "");
}

function inPreventedArea(event: Event): boolean {
  for (const node of event.composedPath()) {
    if (!(node instanceof HTMLElement)) continue;
    if (node === document.body) return false;
    if (node.hasAttribute("data-lenis-prevent") || node.hasAttribute("data-lenis-prevent-wheel")) return true;
  }
  return false;
}

/**
 * The only page-scroll owner on `/` (X2, P5): Lenis on the document, ticked by
 * motion's frame loop, mandatory snap to section tops, section requests from
 * `sectionStore`, the active section and the substrate's orb blend.
 */
export function startScrollEngine(
  sections: readonly SectionDef[],
  stack: HTMLElement,
  opts: ScrollEngineOptions,
): () => void {
  const ids = sections.map((s) => s.id);
  const count = ids.length;
  const reduceMq = window.matchMedia("(prefers-reduced-motion: reduce)");
  let reduced = reduceMq.matches;

  const lenis = new Lenis({
    autoRaf: false,
    anchors: false,
    stopInertiaOnNavigate: true,
    allowNestedScroll: true,
    // Lenis emits `virtual-scroll` (which drives Snap) before its own prevent check.
    virtualScroll: (data: VirtualScrollData) => !inPreventedArea(data.event),
  });

  const frameEls = () => Array.from(stack.querySelectorAll<HTMLElement>(":scope > [data-section]"));
  const unitPx = () => frameEls()[0]?.offsetHeight || window.innerHeight;

  // "lock" is Lenis's directional mandatory snap: always rest on a section top, and one
  // gesture moves one section (plain "mandatory" snaps back unless you pass half a viewport).
  const snap = new Snap(lenis, {
    type: "lock",
    duration: SNAP_S,
    easing: expoOut,
    debounce: 120,
  });
  snap.addElements(frameEls(), { align: ["start"] });
  let activeIdx = Math.max(0, ids.indexOf(sectionStore.get().active));
  let jump: Jump | null = null;
  let lastBlend: OrbBlend | null = null;
  let settleTimer = 0;
  let pointerDown = false;

  postSubstrate({ type: "sections", specs: Object.fromEntries(sections.map((s) => [s.id, s.orb])) });

  const update = () => {
    const unit = unitPx();
    const px = lenis.scroll;
    const p = px / unit;
    scrollY.set(px);
    scrollProgress.set(p);
    sectionHeight.set(unit);

    activeIdx = activeFromProgress(p, activeIdx, count);
    const def = sections[activeIdx]!;
    reportScroll(p, def.id, def.workspace);

    const blend = resolveOrbBlend(p, ids, jump);
    if (blendChanged(lastBlend, blend)) {
      lastBlend = blend;
      postSubstrate({ type: "orb", ...blend });
    }
  };

  const realignIfNeeded = () => {
    if (jump || pointerDown || lenis.isLocked) return;
    const unit = unitPx();
    const p = lenis.scroll / unit;
    const nearest = Math.max(0, Math.min(count - 1, Math.round(p)));
    if (Math.abs(p - nearest) <= ALIGN_EPS) return;
    lenis.scrollTo(nearest * unit, { duration: reduced ? 0 : 0.6, easing: expoOut, immediate: reduced });
  };

  const settle = () => {
    window.clearTimeout(settleTimer);
    settleTimer = window.setTimeout(() => {
      if (jump) return settle();
      setScrolling(false);
      realignIfNeeded();
    }, SETTLE_MS);
  };

  const markMoving = () => {
    if (!sectionStore.get().scrolling) setScrolling(true);
    settle();
  };

  const offScroll = lenis.on("scroll", () => {
    update();
    if (jump || Math.abs(lenis.velocity) > SCROLLING_VELOCITY) markMoving();
    else settle();
  });

  const execute = (req: SectionRequest) => {
    executedRequestId = req.id;
    const idx = ids.indexOf(req.section);
    if (idx < 0) return;
    const unit = unitPx();
    const target = idx * unit;
    const start = lenis.scroll / unit;
    liveLog("scroll", { to: req.section, source: req.source, reason: req.reason, immediate: Boolean(req.immediate) });

    if (req.immediate || reduced) {
      jump = null;
      lenis.scrollTo(target, { immediate: true, force: true });
      update();
      return;
    }
    const from = Math.max(0, Math.min(count - 1, Math.round(start)));
    jump = from === idx ? null : { from, to: idx, start };
    const distance = Math.max(1, Math.abs(idx - start));
    markMoving();
    lenis.scrollTo(target, {
      duration: JUMP_BASE_S + JUMP_PER_EXTRA_SECTION_S * (distance - 1),
      easing: expoOut,
      lock: true,
      force: true,
      onComplete: () => {
        jump = null;
        update();
      },
    });
  };

  const onRequest = () => {
    const req = sectionStore.get().request;
    if (req && req.id > executedRequestId) execute(req);
  };
  const offRequest = sectionStore.subscribe(onRequest);

  const onKey = (event: KeyboardEvent) => {
    if (event.defaultPrevented || isEditableTarget(event.target)) return;
    const idx = sectionForKey(event, activeIdx, count);
    if (idx == null) return;
    event.preventDefault();
    if (idx !== activeIdx) opts.onUserNavigate(ids[idx]!, "key");
  };

  const onPointerDown = () => {
    pointerDown = true;
  };
  const onPointerUp = () => {
    pointerDown = false;
    settle();
  };

  let resizeTimer = 0;
  const onResize = () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      lenis.resize();
      snap.resize();
      if (!jump) lenis.scrollTo(activeIdx * unitPx(), { immediate: true, force: true });
      update();
    }, 120);
  };

  const onReduced = () => {
    reduced = reduceMq.matches;
  };

  const tick = ({ timestamp }: { timestamp: number }) => lenis.raf(timestamp);
  frame.update(tick, true);

  window.addEventListener("keydown", onKey);
  window.addEventListener("pointerdown", onPointerDown, { passive: true });
  window.addEventListener("pointerup", onPointerUp, { passive: true });
  window.addEventListener("pointercancel", onPointerUp, { passive: true });
  window.addEventListener("resize", onResize);
  reduceMq.addEventListener("change", onReduced);

  update();
  onRequest();

  return () => {
    cancelFrame(tick);
    offScroll();
    offRequest();
    window.clearTimeout(settleTimer);
    window.clearTimeout(resizeTimer);
    window.removeEventListener("keydown", onKey);
    window.removeEventListener("pointerdown", onPointerDown);
    window.removeEventListener("pointerup", onPointerUp);
    window.removeEventListener("pointercancel", onPointerUp);
    window.removeEventListener("resize", onResize);
    reduceMq.removeEventListener("change", onReduced);
    snap.destroy();
    lenis.destroy();
    setScrolling(false);
  };
}
