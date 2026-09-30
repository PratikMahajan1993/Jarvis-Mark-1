const WHEEL_DOMINANCE = 40;

/** Horizontal trackpad flick that should cycle the deck. Vertical and diagonals do not. */
export function deckWheelAction(deltaX: number, deltaY: number): "next" | "prev" | null {
  if (Math.abs(deltaX) < WHEEL_DOMINANCE || Math.abs(deltaX) <= Math.abs(deltaY)) return null;
  return deltaX > 0 ? "next" : "prev";
}
