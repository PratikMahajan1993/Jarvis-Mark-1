/**
 * Casberry-compatible formula contract. Bodies are pasted verbatim between
 * USER CODE START / USER CODE END and run in the substrate worker for every
 * particle on every frame. See docs/overhaul/ORB_FORMULAS.md.
 */

export type FormulaTarget = { set(x: number, y: number, z: number): void };

export type FormulaColor = {
  set(r: number | string, g?: number, b?: number): void;
  setRGB(r: number, g: number, b: number): void;
  setHSL(h: number, s: number, l: number): void;
};

export type AddControl = (id: string, label: string, min: number, max: number, initial: number) => number;
export type SetInfo = (title: string, description: string) => void;
export type Annotate = (id: string, position: unknown, label: string) => void;

export type ThreeStub = {
  Vector3: new (x?: number, y?: number, z?: number) => { x: number; y: number; z: number };
};

export type FormulaBody = (
  i: number,
  count: number,
  target: FormulaTarget,
  color: FormulaColor,
  time: number,
  addControl: AddControl,
  setInfo: SetInfo,
  annotate: Annotate,
  THREE: ThreeStub,
) => void;

export type OrbFormula = {
  id: string;
  name: string;
  /** Owner-exported PARAMS: the idle control values. */
  params: Record<string, number>;
  /**
   * Controls that only multiply `time` in the body. They stay pinned at idle;
   * a state value changes this formula's clock rate instead (phase continuity).
   */
  speedControls: string[];
  body: FormulaBody;
};

export function defineOrbFormula(formula: OrbFormula): OrbFormula {
  return formula;
}
