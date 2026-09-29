import { describe, expect, it } from "vitest";
import type { PendingAction } from "@/lib/types";
import { pendingMatchesConversation } from "./deckCardMeta";

function action(partial: Partial<PendingAction> & Pick<PendingAction, "id" | "kind">): PendingAction {
  return {
    title: partial.id,
    summary: "",
    payload: {},
    status: "pending",
    ...partial,
  };
}

const conv = { id: "c-draw-1", sessionId: "sess-eng" };

describe("pendingMatchesConversation", () => {
  it("matches conversation_id first", () => {
    const a = action({
      id: "p1",
      kind: "email_send",
      session_id: "sess-eng",
      payload: { conversation_id: "c-draw-1" },
    });
    expect(pendingMatchesConversation(a, conv)).toBe(true);
    expect(pendingMatchesConversation(a, { id: "other", sessionId: "sess-eng" })).toBe(false);
  });

  it("does not badge every task from a session-only mail approval", () => {
    const mail = action({
      id: "p2",
      kind: "email_send",
      session_id: "sess-eng",
      payload: {},
    });
    expect(pendingMatchesConversation(mail, conv)).toBe(false);
    expect(pendingMatchesConversation(mail, { id: "c-note", sessionId: "sess-eng" })).toBe(false);
  });

  it("allows session-only match for engineering kinds with no conversation id", () => {
    const drawing = action({
      id: "p3",
      kind: "drawing",
      session_id: "sess-eng",
      payload: {},
    });
    expect(pendingMatchesConversation(drawing, conv)).toBe(true);
    expect(pendingMatchesConversation(drawing, { id: "c2", sessionId: "other" })).toBe(false);

    const viaPayload = action({
      id: "p4",
      kind: "quote_send",
      session_id: "sess-eng",
      payload: { category: "workflow" },
    });
    expect(pendingMatchesConversation(viaPayload, conv)).toBe(true);
  });

  it("ignores session match when conversation_id is present but wrong", () => {
    const a = action({
      id: "p5",
      kind: "drawing",
      session_id: "sess-eng",
      payload: { conversation_id: "someone-else" },
    });
    expect(pendingMatchesConversation(a, conv)).toBe(false);
  });
});
