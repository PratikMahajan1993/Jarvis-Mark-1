/** Real landing gates (X1). Hermes is display-only and never listed here. */
export const GATES = ["substrate", "fonts", "desk", "monitor", "casual", "engineering"] as const;
export type Gate = (typeof GATES)[number];

type DisplayStep =
  | { kind: "gate"; id: Gate; label: string }
  | { kind: "hermes"; label: string };

/** Status-line order: Hermes can be named while checking, but never blocks exit. */
export const DISPLAY_STEPS: readonly DisplayStep[] = [
  { kind: "gate", id: "substrate", label: "Waking substrate" },
  { kind: "gate", id: "fonts", label: "Loading fonts" },
  { kind: "gate", id: "desk", label: "Loading desk" },
  { kind: "gate", id: "monitor", label: "Loading desk" },
  { kind: "gate", id: "casual", label: "Loading desk" },
  { kind: "hermes", label: "Checking Hermes" },
  { kind: "gate", id: "engineering", label: "Warming engineering" },
];

export function gatesComplete(passed: ReadonlySet<Gate>): boolean {
  return GATES.every((g) => passed.has(g));
}

/** Mono status line under the orb. Hermes shows when prior gates are done and the check is still running. */
export function landingStatusLine(args: {
  passed: ReadonlySet<Gate>;
  hermesDone: boolean;
  exiting: boolean;
}): string {
  if (args.exiting) return "Ready";
  for (const step of DISPLAY_STEPS) {
    if (step.kind === "gate" && !args.passed.has(step.id)) return step.label;
    if (step.kind === "hermes" && !args.hermesDone) return step.label;
  }
  return "Ready";
}
