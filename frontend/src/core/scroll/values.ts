"use client";

import { motionValue } from "motion/react";

/** Page scroll in px, written by the scroll engine inside motion's frame loop (no lag vs. native scroll events). */
export const scrollY = motionValue(0);

/** Page scroll in section units (0 = first section top). */
export const scrollProgress = motionValue(0);

/** Viewport height in px, the section unit. */
export const sectionHeight = motionValue(typeof window === "undefined" ? 800 : window.innerHeight);
