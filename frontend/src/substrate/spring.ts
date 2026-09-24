/** Critically-ish damped spring for substrate uniforms (hero: k=120, c=20, m=1.2). */

export type SpringState = {
  x: number;
  v: number;
  target: number;
};

export const HERO_SPRING = { k: 120, c: 20, m: 1.2 } as const;

const DT = 1 / 120;
const REST_EPS = 1e-3;

export function createSpring(x = 0, target = x): SpringState {
  return { x, v: 0, target };
}

export function setSpringTarget(s: SpringState, target: number, snap = false) {
  s.target = target;
  if (snap) {
    s.x = target;
    s.v = 0;
  }
}

/** Fixed sub-steps for stability. Returns current x. */
export function stepSpring(
  s: SpringState,
  dtSec: number,
  params: { k: number; c: number; m: number } = HERO_SPRING,
): number {
  let remaining = Math.min(Math.max(dtSec, 0), 0.05);
  const { k, c, m } = params;
  while (remaining > 0) {
    const h = Math.min(DT, remaining);
    const force = -k * (s.x - s.target) - c * s.v;
    const a = force / m;
    s.v += a * h;
    s.x += s.v * h;
    remaining -= h;
  }
  return s.x;
}

export function springAtRest(s: SpringState): boolean {
  return Math.abs(s.x - s.target) < REST_EPS && Math.abs(s.v) < REST_EPS;
}
