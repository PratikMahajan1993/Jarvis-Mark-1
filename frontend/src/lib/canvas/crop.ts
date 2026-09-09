import type { ImageItem, ItemLocalRect, PdfItem } from "./types";
import { getPdfDocument, clampPage } from "./pdf";

export type CropSource =
  | {
      kind: "pdf";
      fileId: string;
      fileUrl: string;
      page: number;
      itemSize: { w: number; h: number };
    }
  | {
      kind: "image";
      fileUrl: string;
      itemSize: { w: number; h: number };
    };

export type CropResult = {
  blob: Blob;
  width: number;
  height: number;
};

const MAX_EDGE = 4096;
const PDF_PT_SCALE = 2;

export function worldMarqueeToLocal(
  item: { x: number; y: number; w: number; h: number },
  a: { x: number; y: number },
  b: { x: number; y: number },
): ItemLocalRect | null {
  const left = Math.max(item.x, Math.min(a.x, b.x));
  const top = Math.max(item.y, Math.min(a.y, b.y));
  const right = Math.min(item.x + item.w, Math.max(a.x, b.x));
  const bottom = Math.min(item.y + item.h, Math.max(a.y, b.y));
  const w = right - left;
  const h = bottom - top;
  if (w < 1 || h < 1) return null;
  return { x: left - item.x, y: top - item.y, w, h };
}

export function cropSourceForItem(
  item: PdfItem | ImageItem,
  fileUrl: string,
): CropSource {
  if (item.kind === "pdf") {
    return {
      kind: "pdf",
      fileId: item.fileId,
      fileUrl,
      page: item.page,
      itemSize: { w: item.w, h: item.h },
    };
  }
  return { kind: "image", fileUrl, itemSize: { w: item.w, h: item.h } };
}

/**
 * Rasterize `region` (item-local world units) to a PNG.
 * PDF pages are re-rendered at high scale rather than sampling the display bitmap.
 */
export async function cropCanvasRegion(source: CropSource, region: ItemLocalRect): Promise<CropResult> {
  const box = sanitizeRegion(region, source.itemSize);
  if (source.kind === "pdf") return cropPdf(source, box);
  return cropImage(source, box);
}

function sanitizeRegion(region: ItemLocalRect, itemSize: { w: number; h: number }): ItemLocalRect {
  const x = Math.max(0, region.x);
  const y = Math.max(0, region.y);
  const w = Math.min(itemSize.w - x, region.w);
  const h = Math.min(itemSize.h - y, region.h);
  return { x, y, w: Math.max(1, w), h: Math.max(1, h) };
}

async function cropPdf(
  source: Extract<CropSource, { kind: "pdf" }>,
  region: ItemLocalRect,
): Promise<CropResult> {
  const doc = await getPdfDocument(source.fileId, source.fileUrl);
  const page = await doc.getPage(clampPage(source.page, doc.numPages));
  const base = page.getViewport({ scale: 1 });
  const sx = (region.x / source.itemSize.w) * base.width;
  const sy = (region.y / source.itemSize.h) * base.height;
  const sw = (region.w / source.itemSize.w) * base.width;
  const sh = (region.h / source.itemSize.h) * base.height;
  let scale = PDF_PT_SCALE;
  const maxDim = Math.max(sw, sh) * scale;
  if (maxDim > MAX_EDGE) scale *= MAX_EDGE / maxDim;
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(sw * scale));
  canvas.height = Math.max(1, Math.round(sh * scale));
  const ctx = canvas.getContext("2d", { alpha: false });
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  ctx.translate(-sx * scale, -sy * scale);
  await page.render({ canvasContext: ctx, viewport, canvas }).promise;
  ctx.restore();
  return canvasPng(canvas);
}

async function cropImage(source: Extract<CropSource, { kind: "image" }>, region: ItemLocalRect): Promise<CropResult> {
  const response = await fetch(source.fileUrl);
  if (!response.ok) throw new Error("Image missing");
  const blob = await response.blob();
  const bitmap = await createImageBitmap(blob);
  try {
    const sx = (region.x / source.itemSize.w) * bitmap.width;
    const sy = (region.y / source.itemSize.h) * bitmap.height;
    const sw = Math.max(1, (region.w / source.itemSize.w) * bitmap.width);
    const sh = Math.max(1, (region.h / source.itemSize.h) * bitmap.height);
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(sw));
    canvas.height = Math.max(1, Math.round(sh));
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas unavailable");
    ctx.drawImage(bitmap, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
    return canvasPng(canvas);
  } finally {
    bitmap.close();
  }
}

function canvasPng(canvas: HTMLCanvasElement): Promise<CropResult> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("PNG encode failed"));
        return;
      }
      resolve({ blob, width: canvas.width, height: canvas.height });
    }, "image/png");
  });
}
