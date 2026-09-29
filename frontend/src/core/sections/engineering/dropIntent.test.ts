import { describe, expect, it } from "vitest";
import { dropIntentChoice, QUOTE_START_FROM_DROP } from "./dropIntent";

describe("dropIntentChoice", () => {
  it("maps quote phrasing", () => {
    expect(dropIntentChoice("Start quote")).toBe("quote");
    expect(dropIntentChoice("quote this drawing")).toBe("quote");
    expect(dropIntentChoice("I want a quote")).toBe("quote");
  });

  it("maps view / discuss phrasing", () => {
    expect(dropIntentChoice("View and discuss")).toBe("discuss");
    expect(dropIntentChoice("only view")).toBe("discuss");
    expect(dropIntentChoice("just talk")).toBe("discuss");
    expect(dropIntentChoice("discuss the drawing")).toBe("discuss");
  });

  it("returns null for empty or ambiguous text", () => {
    expect(dropIntentChoice("")).toBe(null);
    expect(dropIntentChoice("  ")).toBe(null);
    expect(dropIntentChoice("maybe later")).toBe(null);
  });
});

describe("QUOTE_START_FROM_DROP", () => {
  it("is a shop-quote start phrase", () => {
    expect(QUOTE_START_FROM_DROP.toLowerCase()).toContain("quote");
    expect(QUOTE_START_FROM_DROP.toLowerCase()).toContain("drawing");
  });
});
