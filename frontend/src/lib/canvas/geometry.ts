import type { Bounds } from "./camera";
import { itemBounds } from "./camera";
import { GRID_SIZE, type CanvasItem, type Point } from "./types";

export type Rect = { x: number; y: number; w: number; h: number };

export function snap(value: number, size = GRID_SIZE): number {
  return Math.round(value / size) * size;
}

export function snapPoint(point: Point, size = GRID_SIZE): Point {
  return { x: snap(point.x, size), y: snap(point.y, size) };
}

export function rectsOverlap(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

export function rectFromPoints(a: Point, b: Point): Rect {
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  return { x, y, w: Math.abs(b.x - a.x), h: Math.abs(b.y - a.y) };
}

export function itemRect(item: CanvasItem): Rect {
  return { x: item.x, y: item.y, w: item.w, h: item.h };
}

export function itemsInRect(items: CanvasItem[], rect: Rect): CanvasItem[] {
  return items.filter((item) => rectsOverlap(itemRect(item), rect));
}

export function selectionBounds(items: CanvasItem[]): Bounds | null {
  return itemBounds(items);
}

export type AlignEdge = "left" | "center" | "right" | "top" | "middle" | "bottom";

export function alignItems(items: CanvasItem[], edge: AlignEdge): CanvasItem[] {
  if (items.length < 2) return items;
  const bounds = itemBounds(items);
  if (!bounds) return items;
  return items.map((item) => {
    if (item.locked) return item;
    if (edge === "left") return { ...item, x: bounds.minX };
    if (edge === "right") return { ...item, x: bounds.maxX - item.w };
    if (edge === "center") return { ...item, x: bounds.minX + (bounds.maxX - bounds.minX - item.w) / 2 };
    if (edge === "top") return { ...item, y: bounds.minY };
    if (edge === "bottom") return { ...item, y: bounds.maxY - item.h };
    return { ...item, y: bounds.minY + (bounds.maxY - bounds.minY - item.h) / 2 };
  });
}

export function distributeItems(items: CanvasItem[], axis: "x" | "y"): CanvasItem[] {
  if (items.length < 3) return items;
  const unlocked = items.filter((item) => !item.locked);
  const sorted = [...unlocked].sort((a, b) => (axis === "x" ? a.x - b.x : a.y - b.y));
  if (sorted.length < 3) return items;
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  const span =
    axis === "x" ? last.x + last.w - first.x : last.y + last.h - first.y;
  const size = sorted.reduce((sum, item) => sum + (axis === "x" ? item.w : item.h), 0);
  const gap = (span - size) / (sorted.length - 1);
  let cursor = axis === "x" ? first.x : first.y;
  const placed = new Map<string, CanvasItem>();
  sorted.forEach((item, index) => {
    if (index === 0) {
      placed.set(item.id, item);
      cursor += (axis === "x" ? item.w : item.h) + gap;
      return;
    }
    if (index === sorted.length - 1) {
      placed.set(item.id, item);
      return;
    }
    placed.set(item.id, axis === "x" ? { ...item, x: cursor } : { ...item, y: cursor });
    cursor += (axis === "x" ? item.w : item.h) + gap;
  });
  return items.map((item) => placed.get(item.id) ?? item);
}

export function nudgeItems(items: CanvasItem[], dx: number, dy: number): CanvasItem[] {
  return items.map((item) =>
    item.locked ? item : { ...item, x: item.x + dx, y: item.y + dy },
  );
}

/** Snap a moving rect to other item edges/centers when within `threshold`. */
export function snapToItems(rect: Rect, others: CanvasItem[], threshold = 6): Rect {
  let x = rect.x;
  let y = rect.y;
  const mx = rect.x + rect.w / 2;
  const my = rect.y + rect.h / 2;
  const right = rect.x + rect.w;
  const bottom = rect.y + rect.h;
  for (const item of others) {
    const ix = item.x;
    const iy = item.y;
    const ir = item.x + item.w;
    const ib = item.y + item.h;
    const imx = item.x + item.w / 2;
    const imy = item.y + item.h / 2;
    if (Math.abs(x - ix) < threshold) x = ix;
    else if (Math.abs(x - ir) < threshold) x = ir;
    else if (Math.abs(mx - imx) < threshold) x = imx - rect.w / 2;
    else if (Math.abs(right - ix) < threshold) x = ix - rect.w;
    else if (Math.abs(right - ir) < threshold) x = ir - rect.w;
    if (Math.abs(y - iy) < threshold) y = iy;
    else if (Math.abs(y - ib) < threshold) y = ib;
    else if (Math.abs(my - imy) < threshold) y = imy - rect.h / 2;
    else if (Math.abs(bottom - iy) < threshold) y = iy - rect.h;
    else if (Math.abs(bottom - ib) < threshold) y = ib - rect.h;
  }
  return { ...rect, x, y };
}

export function boundsFromPoints(points: Point[], pad = 8): Rect {
  if (!points.length) return { x: 0, y: 0, w: pad * 2, h: pad * 2 };
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const point of points) {
    minX = Math.min(minX, point.x);
    minY = Math.min(minY, point.y);
    maxX = Math.max(maxX, point.x);
    maxY = Math.max(maxY, point.y);
  }
  return {
    x: minX - pad,
    y: minY - pad,
    w: Math.max(8, maxX - minX + pad * 2),
    h: Math.max(8, maxY - minY + pad * 2),
  };
}

export function toLocal(points: Point[], origin: Point): Point[] {
  return points.map((point) => ({ x: point.x - origin.x, y: point.y - origin.y }));
}

export function groupMembers(items: CanvasItem[], item: CanvasItem): CanvasItem[] {
  if (!item.groupId) return [item];
  return items.filter((candidate) => candidate.groupId === item.groupId);
}
