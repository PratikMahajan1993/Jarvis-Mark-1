export const SHEET_KINDS = ["text", "number", "date", "formula"] as const;
export const SHEET_FILLED_BY = ["", "owner", "staff", "jarvis"] as const;
export const SHEET_BLANK_ROWS = 6;

export type SheetKind = (typeof SHEET_KINDS)[number];
export type SheetFilledBy = (typeof SHEET_FILLED_BY)[number];

export type SheetColumn = {
  name: string;
  kind: SheetKind;
  filled_by: SheetFilledBy;
  formula: string;
};

export type SheetDraft = {
  workbook_title: string;
  tab_title: string;
  columns: SheetColumn[];
};

export const EMPTY_SHEET_DRAFT: SheetDraft = {
  workbook_title: "",
  tab_title: "",
  columns: [],
};

export function kindLabel(kind: SheetKind): string {
  if (kind === "text") return "Text";
  if (kind === "number") return "Number";
  if (kind === "date") return "Date";
  return "Formula";
}

export function filledByLabel(filled: SheetFilledBy): string {
  if (filled === "owner") return "Owner";
  if (filled === "staff") return "Staff";
  if (filled === "jarvis") return "Jarvis";
  return "";
}
