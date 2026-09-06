import type { CanvasCamera, CanvasItem } from "./types";

export const MIN_ZOOM = 0.05;
export const MAX_ZOOM = 8;

export type Point = { x: number; y: number };

export function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/**
 * The board is one CSS transform: translate(camera.x, camera.y) scale(camera.z).
 * These two functions are the only place that relationship is encoded.
 */
export function worldToScreen(point: Point, camera: CanvasCamera): Point {
  return {
    x: point.x * camera.z + camera.x,
    y: point.y * camera.z + camera.y,
  };
}

export function screenToWorld(point: Point, camera: CanvasCamera): Point {
  return {
    x: (point.x - camera.x) / camera.z,
    y: (point.y - camera.y) / camera.z,
  };
}

/** Zooms so the world point under `anchor` (screen coords) stays put. */
export function zoomAt(camera: CanvasCamera, anchor: Point, nextZoom: number): CanvasCamera {
  const z = clampZoom(nextZoom);
  const world = screenToWorld(anchor, camera);
  return {
    z,
    x: anchor.x - world.x * z,
    y: anchor.y - world.y * z,
  };
}

export function panBy(camera: CanvasCamera, dx: number, dy: number): CanvasCamera {
  return { ...camera, x: camera.x + dx, y: camera.y + dy };
}

export type Bounds = { minX: number; minY: number; maxX: number; maxY: number };

export function itemBounds(items: CanvasItem[]): Bounds | null {
  if (!items.length) return null;
  return items.reduce<Bounds>(
    (acc, item) => ({
      minX: Math.min(acc.minX, item.x),
      minY: Math.min(acc.minY, item.y),
      maxX: Math.max(acc.maxX, item.x + item.w),
      maxY: Math.max(acc.maxY, item.y + item.h),
    }),
    { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity },
  );
}

/** Camera that frames every item inside a viewport, or a reset camera if the board is empty. */
export function fitToItems(
  items: CanvasItem[],
  viewportW: number,
  viewportH: number,
  padding = 96,
): CanvasCamera {
  const bounds = itemBounds(items);
  if (!bounds || viewportW <= 0 || viewportH <= 0) {
    return { x: viewportW / 2, y: viewportH / 2, z: 1 };
  }
  const width = Math.max(1, bounds.maxX - bounds.minX);
  const height = Math.max(1, bounds.maxY - bounds.minY);
  const z = clampZoom(
    Math.min((viewportW - padding * 2) / width, (viewportH - padding * 2) / height, MAX_ZOOM),
  );
  const centerX = bounds.minX + width / 2;
  const centerY = bounds.minY + height / 2;
  return {
    z,
    x: viewportW / 2 - centerX * z,
    y: viewportH / 2 - centerY * z,
  };
}

/**
 * Wheel deltas differ wildly across devices (lines vs pixels vs pinch), so
 * normalize to a multiplier before touching the camera.
 */
export function wheelZoomFactor(deltaY: number, deltaMode: number): number {
  const pixels = deltaMode === 1 ? deltaY * 16 : deltaMode === 2 ? deltaY * 400 : deltaY;
  return Math.exp(-Math.max(-120, Math.min(120, pixels)) / 320);
}
