import asciSystem from "./asci-system";
import chatGpt from "./chat-gpt";
import cortexDinamico from "./cortex-dinamico";
import type { OrbFormula } from "./types";

/** Register a pasted formula here. Ids are referenced by section orb declarations. */
export const FORMULAS: Record<string, OrbFormula> = {
  [cortexDinamico.id]: cortexDinamico,
  [asciSystem.id]: asciSystem,
  [chatGpt.id]: chatGpt,
};

export function formulaById(id: string): OrbFormula | null {
  return FORMULAS[id] ?? null;
}

export { defineOrbFormula } from "./types";
export type { OrbFormula } from "./types";
