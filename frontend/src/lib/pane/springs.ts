export const SPRING = {
  pane: { type: "spring" as const, stiffness: 170, damping: 26, mass: 1 },
  hero: { type: "spring" as const, stiffness: 120, damping: 20, mass: 1.2 },
  recess: { type: "spring" as const, stiffness: 200, damping: 28, mass: 1 },
  drawer: { type: "spring" as const, stiffness: 260, damping: 30, mass: 0.9 },
  chip: { type: "spring" as const, stiffness: 400, damping: 30, mass: 0.6 },
};

export const EASE = {
  out: [0.22, 1, 0.36, 1] as const,
  gsapOut: "expo.out" as const,
};

export const DURATION = { theme: 0.7, field: 0.6, chrome: 0.35, staggerDepth: 0.04 };

export const DEPTH_VARIANTS = {
  "0": {
    scale: 1,
    opacity: 1,
    z: 0,
    visibility: "visible" as const,
    pointerEvents: "auto" as const,
    transition: SPRING.pane,
  },
  "1": {
    scale: 1,
    opacity: 1,
    z: -12,
    visibility: "visible" as const,
    pointerEvents: "auto" as const,
    transition: SPRING.pane,
  },
  "2": {
    scale: 0.97,
    opacity: 0.55,
    z: -36,
    visibility: "visible" as const,
    pointerEvents: "auto" as const,
    transition: SPRING.recess,
  },
  "3": {
    scale: 0.94,
    opacity: 0,
    z: -60,
    visibility: "hidden" as const,
    contentVisibility: "hidden" as const,
    pointerEvents: "none" as const,
    transition: SPRING.recess,
  },
} as const;
