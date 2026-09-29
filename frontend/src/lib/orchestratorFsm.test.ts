import { describe, expect, it } from "vitest";
import {
  INITIAL_JARVIS_STATE,
  effectsFor,
  isBusy,
  listenAllowed,
  presenceFor,
  transition,
  type JarvisState,
} from "./orchestratorFsm";
import type { PendingAction } from "./types";

const action = (id = "a1", kind = "email_send"): PendingAction =>
  ({ id, kind, title: "Send", summary: "", payload: {}, status: "pending" }) as unknown as PendingAction;

const hitl = (id = "a1", extra: Partial<Extract<JarvisState, { mode: "AWAITING_HITL" }>> = {}): JarvisState => ({
  mode: "AWAITING_HITL",
  action: action(id),
  listening: false,
  resolving: false,
  ...extra,
});

describe("existing transitions", () => {
  it("refuses listening while speaking", () => {
    const speaking: JarvisState = { mode: "SPEAKING", text: "hi" };
    expect(transition(speaking, { type: "LISTEN_START" })).toBe(speaking);
  });

  it("SEND from IDLE enters THINKING synchronously", () => {
    expect(transition(INITIAL_JARVIS_STATE, { type: "SEND", text: "hello" })).toEqual({
      mode: "THINKING",
      message: "hello",
    });
  });

  it("late SPEAK_END is a no-op outside SPEAKING", () => {
    const s = hitl();
    expect(transition(s, { type: "SPEAK_END" })).toBe(s);
  });

  it("approve moves to EXECUTING, reject keeps the panel resolving", () => {
    expect(transition(hitl(), { type: "DECIDE_APPROVE", actionId: "a1" })).toEqual({
      mode: "EXECUTING",
      actionId: "a1",
    });
    const rejected = transition(hitl(), { type: "DECIDE_REJECT", actionId: "a1" });
    expect(rejected).toMatchObject({ mode: "AWAITING_HITL", resolving: true });
    expect(isBusy(rejected)).toBe(true);
  });
});

describe("HITL_PARK", () => {
  it("parks the open approval to IDLE so chat and mic work again", () => {
    const next = transition(hitl(), { type: "HITL_PARK", actionId: "a1" });
    expect(next).toEqual({ mode: "IDLE" });
    expect(listenAllowed(next)).toBe(true);
  });

  it("refuses a different id or a resolving panel", () => {
    const s = hitl();
    expect(transition(s, { type: "HITL_PARK", actionId: "other" })).toBe(s);
    const resolving = hitl("a1", { resolving: true });
    expect(transition(resolving, { type: "HITL_PARK", actionId: "a1" })).toBe(resolving);
  });

  it("refuses outside AWAITING_HITL", () => {
    const thinking: JarvisState = { mode: "THINKING", message: "x" };
    expect(transition(thinking, { type: "HITL_PARK", actionId: "a1" })).toBe(thinking);
  });
});

describe("HITL_RESUME", () => {
  it("reopens from IDLE and LISTENING", () => {
    expect(transition({ mode: "IDLE" }, { type: "HITL_RESUME", action: action("p1") })).toMatchObject({
      mode: "AWAITING_HITL",
      listening: false,
      resolving: false,
    });
    expect(transition({ mode: "LISTENING" }, { type: "HITL_RESUME", action: action("p1") }).mode).toBe(
      "AWAITING_HITL",
    );
  });

  it("refuses while busy, speaking or already awaiting", () => {
    for (const s of [
      { mode: "THINKING", message: "x" },
      { mode: "EXECUTING", actionId: "z" },
      { mode: "SPEAKING", text: "t" },
      hitl("other"),
    ] as JarvisState[]) {
      expect(transition(s, { type: "HITL_RESUME", action: action("p1") })).toBe(s);
    }
  });
});

describe("ROUTE_HINT", () => {
  it("never changes state", () => {
    for (const s of [INITIAL_JARVIS_STATE, hitl(), { mode: "THINKING", message: "m" }] as JarvisState[]) {
      expect(transition(s, { type: "ROUTE_HINT", section: "engineering", reason: "quote" })).toBe(s);
    }
  });
});

describe("RECONCILE with parked ids", () => {
  const turn = { id: "t1", state: "AWAITING_HITL", pending_action: action("p9"), pending_status: "pending" };

  it("keeps a parked pending row at IDLE", () => {
    expect(transition({ mode: "IDLE" }, { type: "RECONCILE", turn, parkedIds: ["p9"] })).toEqual({ mode: "IDLE" });
  });

  it("surfaces an unparked pending row", () => {
    expect(transition({ mode: "IDLE" }, { type: "RECONCILE", turn }).mode).toBe("AWAITING_HITL");
  });
});

describe("effectsFor", () => {
  it("emits orb-mode only when presence changes", () => {
    const idle: JarvisState = { mode: "IDLE" };
    const thinking = transition(idle, { type: "SEND", text: "x" });
    expect(effectsFor(idle, thinking, { type: "SEND", text: "x" })).toEqual([{ kind: "orb-mode", mode: "thinking" }]);
    const executing: JarvisState = { mode: "EXECUTING", actionId: "a" };
    expect(effectsFor(thinking, executing, { type: "RESUME_THINKING" })).toEqual([]);
  });

  it("maps every mode to a presence", () => {
    expect(presenceFor({ mode: "EXECUTING", actionId: "a" })).toBe("thinking");
    expect(presenceFor(hitl())).toBe("hitl");
    expect(presenceFor({ mode: "SPEAKING", text: "" })).toBe("speaking");
  });

  it("parking drops the orb out of hitl", () => {
    const prev = hitl();
    const event = { type: "HITL_PARK", actionId: "a1" } as const;
    expect(effectsFor(prev, transition(prev, event), event)).toEqual([{ kind: "orb-mode", mode: "idle" }]);
  });

  it("ROUTE_HINT scrolls, and autosaves first when leaving Engineering", () => {
    const s: JarvisState = { mode: "IDLE" };
    expect(
      effectsFor(s, s, { type: "ROUTE_HINT", section: "casual", reason: "back-to-chat", from: "engineering" }),
    ).toEqual([
      { kind: "autosave", reason: "leave-engineering" },
      { kind: "scroll", section: "casual", reason: "back-to-chat", source: "auto" },
    ]);
    expect(effectsFor(s, s, { type: "ROUTE_HINT", section: "engineering", reason: "quote", from: "monitor" })).toEqual(
      [{ kind: "scroll", section: "engineering", reason: "quote", source: "auto" }],
    );
    expect(effectsFor(s, s, { type: "ROUTE_HINT", section: "casual", reason: "x", from: "casual" })).toEqual([]);
  });
});
