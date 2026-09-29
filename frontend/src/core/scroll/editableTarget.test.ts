/** @vitest-environment jsdom */
import { describe, expect, it } from "vitest";
import { isEditableTarget, isFieldTarget } from "./editableTarget";

function el(tag: string, attrs: Record<string, string> = {}): HTMLElement {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

describe("isFieldTarget (Space)", () => {
  it("treats the baton text input as a field so Space is not preventDefaulted", () => {
    expect(isFieldTarget(el("input", { type: "text" }))).toBe(true);
    expect(isFieldTarget(el("input", { type: "search" }))).toBe(true);
    expect(isFieldTarget(el("input"))).toBe(true);
  });

  it("treats textarea, select, and contenteditable as fields", () => {
    expect(isFieldTarget(el("textarea"))).toBe(true);
    expect(isFieldTarget(el("select"))).toBe(true);
    expect(isFieldTarget(el("div", { contenteditable: "true" }))).toBe(true);
  });

  it("does not treat plain elements as fields", () => {
    expect(isFieldTarget(el("div"))).toBe(false);
    expect(isFieldTarget(el("button"))).toBe(false);
    expect(isFieldTarget(null)).toBe(false);
  });
});

describe("isEditableTarget (section keys)", () => {
  it("does not treat the baton as editable so PageUp/Alt+n still navigate", () => {
    expect(isEditableTarget(el("input", { type: "text" }))).toBe(false);
    expect(isEditableTarget(el("input", { type: "search" }))).toBe(false);
    expect(isEditableTarget(el("input"))).toBe(false);
  });

  it("still blocks section keys in textarea/select/contenteditable", () => {
    expect(isEditableTarget(el("textarea"))).toBe(true);
    expect(isEditableTarget(el("select"))).toBe(true);
    expect(isEditableTarget(el("div", { contenteditable: "true" }))).toBe(true);
  });
});
