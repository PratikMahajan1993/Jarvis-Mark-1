import { describe, expect, it } from "vitest";
import { GATES, gatesComplete, landingStatusLine, type Gate } from "./landingStatus";

function set(...gates: Gate[]) {
  return new Set<Gate>(gates);
}

describe("landingStatusLine", () => {
  it("names the first unfinished gate", () => {
    expect(landingStatusLine({ passed: set(), hermesDone: false, exiting: false })).toBe("Waking substrate");
    expect(landingStatusLine({ passed: set("substrate"), hermesDone: false, exiting: false })).toBe(
      "Loading fonts",
    );
  });

  it("names Checking Hermes after desk gates while the check runs", () => {
    const passed = set("substrate", "fonts", "desk", "monitor", "casual");
    expect(landingStatusLine({ passed, hermesDone: false, exiting: false })).toBe("Checking Hermes");
    expect(landingStatusLine({ passed, hermesDone: true, exiting: false })).toBe("Warming engineering");
  });

  it("never waits on Hermes for Ready once gates pass", () => {
    const passed = set(...GATES);
    expect(landingStatusLine({ passed, hermesDone: false, exiting: false })).toBe("Checking Hermes");
    expect(landingStatusLine({ passed, hermesDone: false, exiting: true })).toBe("Ready");
    expect(landingStatusLine({ passed, hermesDone: true, exiting: false })).toBe("Ready");
  });
});

describe("gatesComplete", () => {
  it("ignores Hermes and requires every real gate", () => {
    expect(gatesComplete(set("substrate", "fonts", "desk", "monitor", "casual"))).toBe(false);
    expect(gatesComplete(set(...GATES))).toBe(true);
  });
});
