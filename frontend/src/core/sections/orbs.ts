import type { OrbSpec } from "@/substrate/protocol";

const AMBER: [number, number, number] = [1, 0.69, 0.125];

/** Monitor — ASCI System. Tall: 70% of the viewport, bottom edge above the baton. */
export const MONITOR_ORB: OrbSpec = {
  formula: "asci-system",
  placement: { center: [0.5, 0.46], height: 0.7 },
  dim: 1,
  states: {
    idle: {},
    listening: { controls: { flow: 0.45, chaos: 0.35 } },
    thinking: { controls: { flow: 1.6, chaos: 1.2 } },
    speaking: { controls: { flow: 0.7, chaos: { base: 0.5, level: 0.9 } } },
    hitl: { controls: { flow: 0.3, chaos: 0.3 }, tint: AMBER, tintMix: 0.65, pulseHz: 0.5 },
  },
};

/** Casual — Cortex Dinamico. Large and centred; outer shell ≈ 78% of content height. */
export const CASUAL_ORB: OrbSpec = {
  formula: "cortex-dinamico",
  placement: { center: [0.5, 0.47], height: 0.62 },
  dim: 1,
  states: {
    idle: {},
    listening: { controls: { chaosFactor: 0.3, pulseSpeed: 2.0 } },
    thinking: { controls: { chaosFactor: 1.4, pulseSpeed: 4.6 } },
    speaking: { controls: { chaosFactor: { base: 0.3, level: 0.9 }, pulseSpeed: 3.4 } },
    hitl: { controls: { chaosFactor: 0.2, pulseSpeed: 1.2, neuroActivity: 0.83 } },
  },
};

/** Engineering — CHAT GPT (Living Hyperfield). Dimmed side orb; generic modifiers. */
export const ENGINEERING_ORB: OrbSpec = {
  formula: "chat-gpt",
  placement: { center: [0.93, 0.18], height: 0.2 },
  dim: 0.35,
  states: {
    idle: { rate: 1 },
    listening: { rate: 0.7, brightness: 1.25 },
    thinking: { rate: 2, brightness: 1.1 },
    speaking: { rate: 1, brightness: { base: 1, level: 0.6 } },
    hitl: { rate: 0.5, pulseHz: 0.5, tint: AMBER, tintMix: 0.65 },
  },
};
