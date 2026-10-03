import { describe, expect, it } from "vitest";
import { validateFeatureList } from "@/sdk";

describe("sheets feature id", () => {
  it("is a valid kebab id", () => {
    expect(validateFeatureList(["sheets"]).ok).toBe(true);
  });
});
