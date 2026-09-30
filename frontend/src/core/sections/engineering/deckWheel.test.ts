import { describe, expect, it } from "vitest";
import { deckWheelAction } from "./deckWheel";

describe("deckWheelAction", () => {
  it("cycles when horizontal movement dominates", () => {
    expect(deckWheelAction(80, 10)).toBe("next");
    expect(deckWheelAction(-80, 10)).toBe("prev");
  });

  it("ignores vertical and small diagonal movement", () => {
    expect(deckWheelAction(10, 80)).toBe(null);
    expect(deckWheelAction(30, 0)).toBe(null);
    expect(deckWheelAction(50, 50)).toBe(null);
  });
});
