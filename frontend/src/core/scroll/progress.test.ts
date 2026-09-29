import { describe, expect, it } from "vitest";
import {
  activeFromProgress,
  blendChanged,
  expoOut,
  nextMounted,
  realignSectionIndex,
  resolveOrbBlend,
  sectionForKey,
} from "./progress";
import { validateSections, type SectionDef } from "@/core/sections/defineSection";
import { CASUAL_ORB, ENGINEERING_ORB, MONITOR_ORB } from "@/core/sections/orbs";
import { CASUAL_THEME } from "@/core/sections/themes";

const IDS = ["monitor", "casual", "engineering"];

describe("resolveOrbBlend", () => {
  it("rests on one section at integer positions", () => {
    expect(resolveOrbBlend(0, IDS)).toEqual({ from: "monitor", to: "monitor", blend: 0 });
    expect(resolveOrbBlend(1, IDS)).toEqual({ from: "casual", to: "casual", blend: 0 });
    expect(resolveOrbBlend(2, IDS)).toEqual({ from: "engineering", to: "engineering", blend: 0 });
  });

  it("blends the two neighbours by the fraction", () => {
    const b = resolveOrbBlend(1.25, IDS);
    expect(b.from).toBe("casual");
    expect(b.to).toBe("engineering");
    expect(b.blend).toBeCloseTo(0.25, 6);
  });

  it("clamps overscroll and garbage", () => {
    expect(resolveOrbBlend(-0.4, IDS)).toEqual({ from: "monitor", to: "monitor", blend: 0 });
    expect(resolveOrbBlend(9, IDS)).toEqual({ from: "engineering", to: "engineering", blend: 0 });
    expect(resolveOrbBlend(Number.NaN, IDS)).toEqual({ from: "monitor", to: "monitor", blend: 0 });
  });

  it("is continuous across integer boundaries", () => {
    for (let i = 0; i < IDS.length - 1; i += 1) {
      const below = resolveOrbBlend(i + 1 - 1e-6, IDS);
      const above = resolveOrbBlend(i + 1 + 1e-6, IDS);
      const shapeOf = (b: typeof below) => (b.blend > 0.5 ? b.to : b.from);
      expect(shapeOf(below)).toBe(IDS[i + 1]);
      expect(shapeOf(above)).toBe(IDS[i + 1]);
    }
  });

  it("morphs a direct jump origin → destination without the section in between", () => {
    const jump = { from: 0, to: 2, start: 0 };
    for (let p = 0; p <= 2; p += 0.05) {
      const b = resolveOrbBlend(p, IDS, jump);
      expect(b.from === "casual" || b.to === "casual").toBe(false);
    }
    expect(resolveOrbBlend(1, IDS, jump).blend).toBeCloseTo(0.5, 6);
    expect(resolveOrbBlend(2, IDS, jump)).toEqual({ from: "engineering", to: "engineering", blend: 0 });
  });

  it("runs a reverse jump on its own progress", () => {
    const jump = { from: 2, to: 0, start: 2 };
    const b = resolveOrbBlend(1.5, IDS, jump);
    expect(b).toEqual({ from: "engineering", to: "monitor", blend: 0.25 });
  });
});

describe("blendChanged", () => {
  it("ignores sub-epsilon moves", () => {
    const a = { from: "monitor", to: "casual", blend: 0.5 };
    expect(blendChanged(null, a)).toBe(true);
    expect(blendChanged(a, { ...a, blend: 0.5004 })).toBe(false);
    expect(blendChanged(a, { ...a, blend: 0.51 })).toBe(true);
    expect(blendChanged(a, { ...a, to: "engineering" })).toBe(true);
  });
});

describe("activeFromProgress", () => {
  it("switches only inside the 0.4 window", () => {
    expect(activeFromProgress(0.39, 0, 3)).toBe(0);
    expect(activeFromProgress(0.5, 0, 3)).toBe(0);
    expect(activeFromProgress(0.59, 0, 3)).toBe(0);
    expect(activeFromProgress(0.6, 0, 3)).toBe(1);
    expect(activeFromProgress(0.5, 1, 3)).toBe(1);
    expect(activeFromProgress(0.41, 1, 3)).toBe(1);
    expect(activeFromProgress(0.4, 1, 3)).toBe(0);
  });
});

describe("nextMounted", () => {
  const lazies = [undefined, undefined, { mountWithin: 1, unmountBeyond: 2 }];

  it("mounts eager sections always and lazy ones within range", () => {
    expect(nextMounted([false, false, false], 0, lazies)).toEqual([true, true, false]);
    expect(nextMounted([true, true, false], 1, lazies)).toEqual([true, true, true]);
  });

  it("keeps a lazy section until beyond unmountBeyond", () => {
    expect(nextMounted([true, true, true], 0.5, lazies)).toEqual([true, true, true]);
    expect(nextMounted([true, true, true], 0, lazies)).toEqual([true, true, true]);
    expect(nextMounted([true, true, false], 0.5, lazies)).toEqual([true, true, false]);
  });
});

describe("realignSectionIndex", () => {
  it("keeps integer positions", () => {
    expect(realignSectionIndex(0, 3, 0)).toBe(0);
    expect(realignSectionIndex(1, 3, 1)).toBe(1);
    expect(realignSectionIndex(2, 3, -1)).toBe(2);
  });

  it("steps forward or back by gesture direction between sections", () => {
    expect(realignSectionIndex(0.11, 3, 1)).toBe(1);
    expect(realignSectionIndex(0.89, 3, -1)).toBe(0);
    expect(realignSectionIndex(1.12, 3, 1)).toBe(2);
  });

  it("falls back to nearest when direction is neutral", () => {
    expect(realignSectionIndex(0.11, 3, 0)).toBe(0);
    expect(realignSectionIndex(0.6, 3, 0)).toBe(1);
  });
});

describe("sectionForKey", () => {
  const k = (over: Partial<Parameters<typeof sectionForKey>[0]>) => ({
    code: "",
    key: "",
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    ...over,
  });

  it("steps with PageUp / PageDown and clamps", () => {
    expect(sectionForKey(k({ key: "PageDown" }), 0, 3)).toBe(1);
    expect(sectionForKey(k({ key: "PageDown" }), 2, 3)).toBe(2);
    expect(sectionForKey(k({ key: "PageUp" }), 0, 3)).toBe(0);
  });

  it("jumps with Alt+digit by physical key", () => {
    expect(sectionForKey(k({ altKey: true, code: "Digit3", key: "£" }), 0, 3)).toBe(2);
    expect(sectionForKey(k({ altKey: true, code: "Digit4" }), 0, 3)).toBeNull();
    expect(sectionForKey(k({ altKey: true, ctrlKey: true, code: "Digit1" }), 0, 3)).toBeNull();
  });

  it("leaves other keys alone", () => {
    expect(sectionForKey(k({ key: " ", code: "Space" }), 0, 3)).toBeNull();
    expect(sectionForKey(k({ key: "ArrowDown" }), 0, 3)).toBeNull();
  });
});

describe("expoOut", () => {
  it("is monotone from 0 to 1", () => {
    expect(expoOut(0)).toBe(0);
    expect(expoOut(1)).toBe(1);
    let prev = 0;
    for (let t = 0.05; t < 1; t += 0.05) {
      expect(expoOut(t)).toBeGreaterThan(prev);
      prev = expoOut(t);
    }
  });
});

describe("validateSections", () => {
  const Stub = () => null;
  const base = (over: Partial<SectionDef>): SectionDef => ({
    id: "monitor",
    order: 100,
    label: "Monitor",
    orb: MONITOR_ORB,
    theme: CASUAL_THEME,
    slots: [],
    component: Stub,
    ...over,
  });

  it("sorts by order", () => {
    const sorted = validateSections([
      base({ id: "engineering", order: 300, orb: ENGINEERING_ORB }),
      base({ id: "monitor", order: 100 }),
      base({ id: "casual", order: 200, orb: CASUAL_ORB }),
    ]);
    expect(sorted.map((s) => s.id)).toEqual(IDS);
  });

  it("rejects duplicate ids and orders", () => {
    expect(() => validateSections([base({}), base({ order: 200 })])).toThrow(/duplicate id/);
    expect(() => validateSections([base({}), base({ id: "casual" })])).toThrow(/duplicate order/);
  });

  it("rejects out-of-range orbs, decor and lazy windows", () => {
    expect(() => validateSections([base({ orb: { ...MONITOR_ORB, dim: 1.5 } })])).toThrow(/dim/);
    expect(() =>
      validateSections([base({ orb: { ...MONITOR_ORB, placement: { center: [1.2, 0.5], height: 0.5 } } })]),
    ).toThrow(/center/);
    const piece = { kind: "reticle" as const, x: 0.5, y: 0.5, size: 0.2 };
    expect(() => validateSections([base({ decor: [piece, piece, piece, piece, piece] })])).toThrow(/at most 4/);
    expect(() => validateSections([base({ decor: [{ ...piece, opacity: 0.6 }] })])).toThrow(/opacity/);
    expect(() => validateSections([base({ decor: [{ ...piece, depth: 2 }] })])).toThrow(/depth/);
    expect(() => validateSections([base({ lazy: { mountWithin: 2, unmountBeyond: 1 } })])).toThrow(/lazy/);
  });
});
