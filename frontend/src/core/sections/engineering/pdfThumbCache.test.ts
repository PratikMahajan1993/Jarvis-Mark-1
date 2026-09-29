import { describe, expect, it } from "vitest";
import { needsIdlePdfThumb, thumbnailCacheKey } from "./pdfThumbCache";

describe("thumbnailCacheKey", () => {
  it("keys a lowercase 64-char sha256", () => {
    const sha = "a".repeat(64);
    expect(thumbnailCacheKey(sha)).toBe(`pdf-thumb:v1:${sha}`);
    expect(thumbnailCacheKey(sha.toUpperCase())).toBe(`pdf-thumb:v1:${sha}`);
  });

  it("rejects non-sha256 input", () => {
    expect(thumbnailCacheKey("")).toBe("");
    expect(thumbnailCacheKey("not-a-hash")).toBe("");
    expect(thumbnailCacheKey("a".repeat(63))).toBe("");
  });
});

describe("needsIdlePdfThumb", () => {
  it("skips when a thumbnail URL already exists", () => {
    expect(needsIdlePdfThumb({ thumbnailUrl: "data:image/png;base64,xx", localName: "a.pdf" })).toBe(false);
  });

  it("true for local PDF without thumb", () => {
    expect(needsIdlePdfThumb({ localName: "part.pdf" })).toBe(true);
    expect(needsIdlePdfThumb({ mime: "application/pdf", filename: "x.bin" })).toBe(true);
  });

  it("false for images / missing file", () => {
    expect(needsIdlePdfThumb({ localName: "part.png", mime: "image/png" })).toBe(false);
    expect(needsIdlePdfThumb({})).toBe(false);
  });
});
