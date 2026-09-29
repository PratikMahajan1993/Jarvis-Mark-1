import { describe, expect, it } from "vitest";
import { batonSectionChangePlan } from "./batonSection";

describe("batonSectionChangePlan", () => {
  it("flushes the previous section then loads the next stored text", () => {
    expect(batonSectionChangePlan("monitor", "casual", "hello baton", "saved casual")).toEqual({
      save: { section: "monitor", text: "hello baton" },
      nextCompose: "saved casual",
    });
  });

  it("flushes empty compose so a send still clears the previous section key", () => {
    expect(batonSectionChangePlan("engineering", "monitor", "", "")).toEqual({
      save: { section: "engineering", text: "" },
      nextCompose: "",
    });
  });

  it("returns null when the section did not change", () => {
    expect(batonSectionChangePlan("casual", "casual", "stay", "ignored")).toBeNull();
  });
});
