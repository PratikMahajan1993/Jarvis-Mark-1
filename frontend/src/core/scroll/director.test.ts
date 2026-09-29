import { describe, expect, it } from "vitest";
import { decideAuto, USER_QUIET_MS } from "./director";

const base = { pinned: false, modalOpen: false, sinceUserMs: 5000, pointerHeld: false };

describe("decideAuto", () => {
  it("runs when quiet", () => expect(decideAuto(base)).toEqual({ run: true }));
  it("drops when pinned or a modal is open", () => {
    expect(decideAuto({ ...base, pinned: true })).toEqual({ run: false, drop: true });
    expect(decideAuto({ ...base, modalOpen: true })).toEqual({ run: false, drop: true });
  });
  it("defers after recent user activity", () => {
    const d = decideAuto({ ...base, sinceUserMs: 200 });
    expect(d.run).toBe(false);
    expect(d.run === false && d.drop).toBe(false);
    expect(d.run === false && d.retryInMs).toBeGreaterThan(USER_QUIET_MS - 200);
  });
  it("defers while the pointer is held", () => {
    expect(decideAuto({ ...base, pointerHeld: true }).run).toBe(false);
  });
});
