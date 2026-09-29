/** Scroll director rules (P5): when an automatic section request may run. Pure except the activity clock. */

export const USER_QUIET_MS = 1200;

export type AutoContext = {
  pinned: boolean;
  modalOpen: boolean;
  /** ms since the user last scrolled, pressed a key or held the pointer. */
  sinceUserMs: number;
  pointerHeld: boolean;
};

export type AutoDecision = { run: true } | { run: false; drop: boolean; retryInMs?: number };

/** A pin or an open modal drops the request; recent user activity defers it (a newer request replaces it). */
export function decideAuto(ctx: AutoContext): AutoDecision {
  if (ctx.pinned || ctx.modalOpen) return { run: false, drop: true };
  if (ctx.pointerHeld) return { run: false, drop: false, retryInMs: USER_QUIET_MS };
  if (ctx.sinceUserMs < USER_QUIET_MS) {
    return { run: false, drop: false, retryInMs: USER_QUIET_MS - ctx.sinceUserMs + 20 };
  }
  return { run: true };
}

let lastUserAt = -Infinity;
let pointerHeld = false;
let modalProbe: () => boolean = () => false;

export function markUserActivity(now = performance.now()) {
  lastUserAt = now;
}
export function setPointerHeld(held: boolean) {
  pointerHeld = held;
  if (!held) markUserActivity();
}
export function setModalProbe(probe: () => boolean) {
  modalProbe = probe;
}
export function autoContext(pinned: boolean, now = performance.now()): AutoContext {
  return { pinned, modalOpen: modalProbe(), sinceUserMs: now - lastUserAt, pointerHeld };
}
