import { describe, expect, it } from "vitest";
import { isDeskNoticeVoice, sectionVoiceLine } from "./sectionVoice";

describe("sectionVoiceLine", () => {
  it("keeps Drawing closed off Monitor and Casual captions", () => {
    expect(isDeskNoticeVoice("Drawing closed.")).toBe(true);
    expect(isDeskNoticeVoice("  Drawing closed  ")).toBe(true);
    expect(sectionVoiceLine("Drawing closed.", "Everyday desk")).toBe("Everyday desk");
    expect(sectionVoiceLine("Drawing closed.", "")).toBe("");
    expect(sectionVoiceLine("Starting the quote workflow.", "Awaiting instruction.")).toBe(
      "Starting the quote workflow.",
    );
  });
});
