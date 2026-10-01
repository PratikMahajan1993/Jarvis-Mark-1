export const QUOTE_BENCH_STEPS = [
  { id: "confirm", label: "Confirm" },
  { id: "scope", label: "Labour / material" },
  { id: "supplier", label: "Supplier" },
  { id: "strategy", label: "Strategy" },
  { id: "hours", label: "Hours" },
  { id: "price", label: "Owner price" },
  { id: "assumptions", label: "Assumptions" },
  { id: "pdf", label: "PDF" },
  { id: "send", label: "Send" },
] as const;

export type QuoteBenchStepId = (typeof QUOTE_BENCH_STEPS)[number]["id"];

export type DrawingCellState = "empty" | "proposed" | "confirmed" | "assumption";

export type DrawingCellsMap = Record<string, { state: DrawingCellState; value: string }>;

const HARD = new Set(["revision", "quantity", "material"]);
const SOFT = new Set(["heat_treat", "finish", "gdt"]);

export function benchStepTab(step: QuoteBenchStepId): "sheet" | "strategy" | "vision" | "knowledge" | "shop" {
  switch (step) {
    case "confirm":
    case "assumptions":
      return "vision";
    case "supplier":
    case "strategy":
    case "hours":
      return "strategy";
    default:
      return "sheet";
  }
}

export function canShowMoveToWhatsApp(cells: DrawingCellsMap | null | undefined): boolean {
  if (!cells) return false;
  for (const key of HARD) {
    const cell = cells[key];
    if (!cell || cell.state !== "confirmed" || !cell.value.trim()) return false;
  }
  for (const key of SOFT) {
    const cell = cells[key];
    if (!cell) return false;
    if (cell.state !== "confirmed" && cell.state !== "assumption") return false;
  }
  return true;
}

export function quoteBlockerFromVerify(
  checks: Array<{ id: string; pass: boolean; evidence?: string; severity?: string }> | undefined,
): { id: string; evidence: string } | null {
  if (!checks?.length) return null;
  for (const check of checks) {
    if (check.pass) continue;
    const sev = (check.severity || "BLOCKER").toUpperCase();
    if (sev !== "BLOCKER") continue;
    if (!check.id.startsWith("drawing_cell_") && !check.id.startsWith("assumption_") && check.id !== "pdf_assumptions_disclosed") {
      continue;
    }
    return { id: check.id, evidence: (check.evidence || check.id).trim() };
  }
  for (const check of checks) {
    if (check.pass) continue;
    const sev = (check.severity || "BLOCKER").toUpperCase();
    if (sev !== "BLOCKER") continue;
    return { id: check.id, evidence: (check.evidence || check.id).trim() };
  }
  return null;
}
