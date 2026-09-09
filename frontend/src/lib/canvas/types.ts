export type CanvasCamera = {
  x: number;
  y: number;
  z: number;
};

export type Point = { x: number; y: number };

export type NoteColor = "amber" | "cyan" | "rose" | "slate";

export type StrokeColor = "cyan" | "amber" | "rose" | "slate" | "white";

export type ShapeKind = "rect" | "ellipse" | "diamond";

export type StrokeMode = "ink" | "line" | "arrow";

export type CanvasItemBase = {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  rotation: number;
  z: number;
  locked?: boolean;
  groupId?: string;
};

export type NoteItem = CanvasItemBase & {
  kind: "note";
  text: string;
  color: NoteColor;
};

export type ImageItem = CanvasItemBase & {
  kind: "image";
  fileId: string;
  name: string;
  naturalW: number;
  naturalH: number;
};

export type PdfItem = CanvasItemBase & {
  kind: "pdf";
  fileId: string;
  name: string;
  page: number;
  pageCount: number;
  naturalW: number;
  naturalH: number;
};

export type ShapeItem = CanvasItemBase & {
  kind: "shape";
  shape: ShapeKind;
  fill: StrokeColor | "none";
  stroke: StrokeColor;
  weight: number;
};

export type StrokeItem = CanvasItemBase & {
  kind: "stroke";
  mode: StrokeMode;
  points: Point[];
  color: StrokeColor;
  weight: number;
};

export type TextItem = CanvasItemBase & {
  kind: "text";
  text: string;
  color: StrokeColor;
  size: number;
};

/**
 * Adding an item type means adding a member here and a renderer in
 * components/canvas/items/index.ts. Nothing else in the pipeline changes:
 * geometry lives in CanvasItemBase and the backend keeps the rest as JSON.
 */
export type CanvasItem = NoteItem | ImageItem | PdfItem | ShapeItem | StrokeItem | TextItem;

export type CanvasItemKind = CanvasItem["kind"];

export type CanvasBoard = {
  id: string;
  name: string;
  camera: CanvasCamera;
  items: CanvasItem[];
};

export type CanvasFile = {
  file_id: string;
  name: string;
  mime: string;
  width: number;
  height: number;
  page_count: number;
};

/**
 * The seam between the board and its storage. CanvasProvider only ever calls
 * these three, so an in-memory transport and the HTTP one are interchangeable.
 */
export type CanvasTransport = {
  load: (boardId: string) => Promise<CanvasBoard>;
  save: (board: CanvasBoard) => Promise<void>;
  upload: (file: File) => Promise<CanvasFile>;
  fileUrl: (fileId: string) => string;
};

export const DEFAULT_BOARD_ID = "default";

export const NOTE_SIZE = { w: 220, h: 220 };

export const NOTE_COLORS: NoteColor[] = ["amber", "cyan", "rose", "slate"];

export const STROKE_COLORS: Record<StrokeColor, string> = {
  cyan: "#3ee0d4",
  amber: "#f5c16c",
  rose: "#f082a0",
  slate: "#94b2c4",
  white: "#d7eef2",
};

export const COLOR_KEYS = Object.keys(STROKE_COLORS) as StrokeColor[];

export const GRID_SIZE = 8;

/** Longest edge a dropped file gets on the board, in world units. */
export const DROPPED_MAX_EDGE = 520;

export type CanvasTool =
  | "select"
  | "pan"
  | "region"
  | "note"
  | "text"
  | "ink"
  | "rect"
  | "ellipse"
  | "diamond"
  | "line"
  | "arrow";

export type ItemLocalRect = { x: number; y: number; w: number; h: number };

export function emptyBoard(id: string = DEFAULT_BOARD_ID): CanvasBoard {
  return {
    id,
    name: "Canvas",
    camera: { x: 0, y: 0, z: 1 },
    items: [],
  };
}

export function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  }
  return Math.random().toString(16).slice(2, 14);
}

/** Scales a natural size down to fit DROPPED_MAX_EDGE, keeping aspect ratio. */
export function fitDroppedSize(naturalW: number, naturalH: number): { w: number; h: number } {
  const width = naturalW > 0 ? naturalW : DROPPED_MAX_EDGE;
  const height = naturalH > 0 ? naturalH : DROPPED_MAX_EDGE;
  const scale = Math.min(1, DROPPED_MAX_EDGE / Math.max(width, height));
  return { w: Math.round(width * scale), h: Math.round(height * scale) };
}

/** Keep the current longest edge and adopt a new aspect ratio (width / height). */
export function sizeForAspect(w: number, h: number, aspect: number): { w: number; h: number } {
  const ratio = aspect > 0 ? aspect : 1;
  const long = Math.max(w, h, 40);
  if (ratio >= 1) {
    return { w: Math.round(long), h: Math.max(40, Math.round(long / ratio)) };
  }
  return { w: Math.max(40, Math.round(long * ratio)), h: Math.round(long) };
}

export function cloneItem(item: CanvasItem, dx = 24, dy = 24): CanvasItem {
  return { ...item, id: createId(), x: item.x + dx, y: item.y + dy, groupId: undefined };
}
