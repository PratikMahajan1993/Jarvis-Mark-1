import { describe, expect, it } from "vitest";
import { validateFeatureList } from "./featureRegistry";

describe("validateFeatureList", () => {
  it("accepts unique kebab ids", () => {
    expect(validateFeatureList(["weather", "tool-wear"])).toEqual({ ok: true });
  });

  it("rejects duplicates", () => {
    const r = validateFeatureList(["weather", "weather"]);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/duplicate/);
  });

  it("rejects invalid ids", () => {
    const r = validateFeatureList(["Weather"]);
    expect(r.ok).toBe(false);
  });
});
