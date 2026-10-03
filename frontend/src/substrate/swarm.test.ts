import { describe, expect, it } from "vitest";
import { CASUAL_ORB, ENGINEERING_ORB, MONITOR_ORB } from "@/core/sections/orbs";
import { FORMULAS } from "./formulas";
import { FormulaRuntime, SwarmSim, VISIBLE_HALF_HEIGHT } from "./swarm";

const SPECS = { monitor: MONITOR_ORB, casual: CASUAL_ORB, engineering: ENGINEERING_ORB };
const DT = 1 / 60;
const MAX_STEP_WORLD = 3;

function worldScale(sim: SwarmSim) {
  return sim.uniforms.height * 2 * VISIBLE_HALF_HEIGHT;
}

function maxStep(prev: Float32Array, next: Float32Array, scale: number) {
  let worst = 0;
  for (let j = 0; j < prev.length; j += 3) {
    const dx = next[j]! - prev[j]!;
    const dy = next[j + 1]! - prev[j + 1]!;
    const dz = next[j + 2]! - prev[j + 2]!;
    const d = Math.sqrt(dx * dx + dy * dy + dz * dz) * scale;
    if (d > worst) worst = d;
  }
  return worst;
}

function settledSim(count: number, section: keyof typeof SPECS) {
  const sim = new SwarmSim(count);
  sim.setSpecs(SPECS);
  sim.setOrb(section, section, 0);
  for (let f = 0; f < 240; f++) sim.step(DT);
  return sim;
}

describe("motion split", () => {
  it("stepMotion leaves particles put and still advances the formula clock", () => {
    const sim = new SwarmSim(64);
    sim.setSpecs(SPECS);
    sim.setOrb("casual", "casual", 0);
    const before = Array.from(sim.positions);
    sim.stepMotion(DT);
    expect(Array.from(sim.positions)).toEqual(before);
    expect(sim.runtime("cortex-dinamico")!.clock).toBeGreaterThan(0);
    expect(sim.gpuFrame().easeK).toBeGreaterThan(0);
    expect(sim.gpuFrame().easeK).toBeLessThanOrEqual(1);
  });
});

describe("orb formulas", () => {
  it.each(Object.values(FORMULAS).map((f) => [f.id, f] as const))(
    "%s produces finite targets and colours for every particle",
    (_id, formula) => {
      const count = 20000;
      const rt = new FormulaRuntime(formula);
      const pos = new Float32Array(count * 3);
      const col = new Float32Array(count * 3);
      for (let s = 0; s < 10; s++) {
        rt.evaluateRaw(count, s * 13.7 + 0.25, pos, col);
        for (let j = 0; j < pos.length; j++) {
          expect(Number.isFinite(pos[j]!)).toBe(true);
          expect(Number.isFinite(col[j]!)).toBe(true);
        }
      }
    },
  );

  it("fits every formula to a unit-tall, y-centred shape", () => {
    const count = 20000;
    for (const formula of Object.values(FORMULAS)) {
      const rt = new FormulaRuntime(formula);
      const pos = new Float32Array(count * 3);
      const col = new Float32Array(count * 3);
      rt.fit(count, pos, col);
      rt.evaluate(count, pos, col);
      let min = Infinity;
      let max = -Infinity;
      for (let j = 1; j < pos.length; j += 3) {
        min = Math.min(min, pos[j]!);
        max = Math.max(max, pos[j]!);
      }
      expect(max - min).toBeGreaterThan(0.8);
      expect(max - min).toBeLessThan(1.25);
      expect(Math.abs((max + min) / 2)).toBeLessThan(0.1);
    }
  });
});

describe("state controls stay phase-continuous", () => {
  it.each(["monitor", "casual", "engineering"] as const)("%s: idle → thinking → hitl → idle", (section) => {
    const sim = settledSim(5000, section);
    let prev = sim.positions.slice();
    let worst = 0;
    for (const mode of ["thinking", "hitl", "speaking", "listening", "idle"] as const) {
      sim.setMode(mode);
      sim.setLevel(mode === "speaking" ? 0.8 : 0);
      for (let f = 0; f < 90; f++) {
        sim.step(DT);
        worst = Math.max(worst, maxStep(prev, sim.positions, worldScale(sim)));
        prev = sim.positions.slice();
      }
    }
    expect(worst).toBeLessThan(MAX_STEP_WORLD);
  });

  it("changing a speed control never jumps the clock", () => {
    const sim = settledSim(2000, "casual");
    const rt = sim.runtime("cortex-dinamico")!;
    const before = rt.clock;
    sim.setMode("thinking");
    sim.step(DT);
    expect(rt.clock - before).toBeLessThan(DT * 2);
    expect(rt.values.pulseSpeed).toBe(3.4);
  });
});

describe("section morphs are smooth", () => {
  const pairs = [
    ["monitor", "casual"],
    ["casual", "engineering"],
    ["monitor", "engineering"],
    ["engineering", "monitor"],
  ] as const;

  it.each(pairs)("%s → %s over 60 frames", (from, to) => {
    const sim = settledSim(5000, from);
    let prev = sim.positions.slice();
    let worst = 0;
    for (let f = 1; f <= 60; f++) {
      sim.setOrb(from, to, f / 60);
      sim.step(DT);
      worst = Math.max(worst, maxStep(prev, sim.positions, worldScale(sim)));
      prev = sim.positions.slice();
    }
    expect(worst).toBeLessThan(MAX_STEP_WORLD);
  });

  it("blend 0 and 1 match the single-section shapes", () => {
    const a = settledSim(3000, "monitor");
    const b = settledSim(3000, "monitor");
    b.setOrb("monitor", "casual", 0);
    a.step(DT);
    b.step(DT);
    expect(maxStep(a.positions, b.positions, 1)).toBeLessThan(1e-6);

    const c = settledSim(3000, "casual");
    const d = settledSim(3000, "casual");
    d.setOrb("monitor", "casual", 1);
    c.step(DT);
    d.step(DT);
    expect(maxStep(c.positions, d.positions, 1)).toBeLessThan(1e-3);
  });
});
