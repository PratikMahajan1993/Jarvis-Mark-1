/** Pure scroll maths: orb blend, active section, lazy mount window. No DOM. */

export type OrbBlend = { from: string; to: string; blend: number };

/** A director jump across sections: the morph runs origin → destination on the jump's own progress. */
export type Jump = { from: number; to: number; start: number };

export type LazyMount = { mountWithin: number; unmountBeyond: number };

const EDGE_EPS = 1e-4;

export const ACTIVE_THRESHOLD = 0.4;

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

/** Scroll position (section units) → the substrate's `orb` message. */
export function resolveOrbBlend(progress: number, ids: readonly string[], jump?: Jump | null): OrbBlend {
  const n = ids.length;
  if (n === 0) throw new Error("resolveOrbBlend: no sections");
  const p = clamp(Number.isFinite(progress) ? progress : 0, 0, n - 1);

  if (jump && jump.from !== jump.to) {
    const from = clamp(jump.from, 0, n - 1);
    const to = clamp(jump.to, 0, n - 1);
    const span = to - jump.start;
    const t = Math.abs(span) < EDGE_EPS ? 1 : clamp((p - jump.start) / span, 0, 1);
    if (t >= 1 - EDGE_EPS) return { from: ids[to]!, to: ids[to]!, blend: 0 };
    if (t <= EDGE_EPS) return { from: ids[from]!, to: ids[from]!, blend: 0 };
    return { from: ids[from]!, to: ids[to]!, blend: t };
  }

  const i = Math.floor(p);
  const f = p - i;
  if (i >= n - 1 || f < EDGE_EPS) return { from: ids[i]!, to: ids[i]!, blend: 0 };
  if (f > 1 - EDGE_EPS) return { from: ids[i + 1]!, to: ids[i + 1]!, blend: 0 };
  return { from: ids[i]!, to: ids[i + 1]!, blend: f };
}

export function blendChanged(a: OrbBlend | null, b: OrbBlend, eps = 1e-3): boolean {
  if (!a) return true;
  return a.from !== b.from || a.to !== b.to || Math.abs(a.blend - b.blend) > eps;
}

/**
 * Active section (X3): the one more than 60% in view, i.e. |pos − i| ≤ 0.4.
 * Between thresholds the previous section stays active.
 */
export function activeFromProgress(progress: number, prevIndex: number, count: number): number {
  if (count <= 0) return 0;
  const p = clamp(progress, 0, count - 1);
  const nearest = Math.round(p);
  if (Math.abs(p - nearest) <= ACTIVE_THRESHOLD) return nearest;
  return clamp(prevIndex, 0, count - 1);
}

/** Lazy mounting (X11) with hysteresis: mount within `mountWithin`, keep until beyond `unmountBeyond`. */
export function nextMounted(
  prev: readonly boolean[],
  progress: number,
  lazies: readonly (LazyMount | undefined)[],
): boolean[] {
  return lazies.map((lazy, i) => {
    if (!lazy) return true;
    const d = Math.abs(progress - i);
    return prev[i] ? d <= lazy.unmountBeyond : d <= lazy.mountWithin;
  });
}

/** Section index for a key press, or null. PageUp/PageDown step; Alt+1…9 jumps. */
export function sectionForKey(
  key: { code: string; key: string; altKey: boolean; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean },
  current: number,
  count: number,
): number | null {
  if (key.ctrlKey || key.metaKey) return null;
  if (key.altKey) {
    if (key.shiftKey) return null;
    const m = /^Digit([1-9])$/.exec(key.code);
    if (!m) return null;
    const idx = Number(m[1]) - 1;
    return idx < count ? idx : null;
  }
  if (key.key === "PageDown") return Math.min(count - 1, current + 1);
  if (key.key === "PageUp") return Math.max(0, current - 1);
  return null;
}

/** Expo-out, the snap and jump easing. */
export function expoOut(t: number): number {
  return t >= 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

/**
 * Section index to align to when scroll rests between section tops.
 * Uses gesture direction when misaligned; `direction === 0` falls back to nearest.
 */
export function realignSectionIndex(
  progress: number,
  count: number,
  direction: -1 | 0 | 1,
  eps = 1e-2,
): number {
  if (count <= 0) return 0;
  const p = clamp(progress, 0, count - 1);
  const nearest = Math.round(p);
  if (Math.abs(p - nearest) <= eps) return nearest;
  if (direction > 0) return Math.min(count - 1, Math.ceil(p - eps));
  if (direction < 0) return Math.max(0, Math.floor(p + eps));
  return nearest;
}
