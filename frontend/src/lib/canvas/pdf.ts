"use client";

import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";

const docs = new Map<string, Promise<PDFDocumentProxy>>();

const RASTER_BUCKETS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8];

type PdfJs = typeof import("pdfjs-dist");

let pdfjsModule: Promise<PdfJs> | null = null;

/**
 * Next 15 + Turbopack will not bundle pdf.worker as a Worker unless the src is
 * a real URL. postinstall copies the worker to /pdf.worker.min.mjs; set that
 * before getDocument so pdf.js does not silently fall back to a fake worker.
 */
export async function loadPdfJs(): Promise<PdfJs> {
  if (!pdfjsModule) {
    pdfjsModule = (async () => {
      const pdfjs = await import("pdfjs-dist");
      if (typeof window !== "undefined") {
        const workerSrc = `${window.location.origin}/pdf.worker.min.mjs`;
        pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;
        if (!pdfjs.GlobalWorkerOptions.workerSrc) {
          throw new Error("PDF worker is not configured.");
        }
      }
      return pdfjs;
    })();
  }
  return pdfjsModule;
}

export function rasterBucket(zoom: number, dpr = 1): number {
  const needed = Math.max(0.25, zoom * (dpr || 1));
  for (const bucket of RASTER_BUCKETS) {
    if (bucket + 1e-6 >= needed) return bucket;
  }
  return RASTER_BUCKETS[RASTER_BUCKETS.length - 1];
}

export function isPdfCancel(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const name = "name" in err ? String(err.name) : "";
  return name === "RenderingCancelledException" || name === "AbortException";
}

export function getPdfDocument(fileId: string, url: string): Promise<PDFDocumentProxy> {
  let pending = docs.get(fileId);
  if (!pending) {
    pending = loadPdfDocument(url);
    docs.set(fileId, pending);
    pending.catch(() => {
      if (docs.get(fileId) === pending) docs.delete(fileId);
    });
  }
  return pending;
}

async function loadPdfDocument(url: string): Promise<PDFDocumentProxy> {
  const pdfjs = await loadPdfJs();
  if (!pdfjs.GlobalWorkerOptions.workerSrc) {
    throw new Error("PDF worker is not configured.");
  }
  const response = await fetch(url);
  if (!response.ok) throw new Error("PDF missing");
  const data = new Uint8Array(await response.arrayBuffer());
  return pdfjs.getDocument({ data }).promise;
}

export async function pdfPageSize(
  fileId: string,
  url: string,
  pageNumber: number,
): Promise<{ width: number; height: number; pageCount: number }> {
  const doc = await getPdfDocument(fileId, url);
  const page = await doc.getPage(clampPage(pageNumber, doc.numPages));
  const viewport = page.getViewport({ scale: 1 });
  return { width: viewport.width, height: viewport.height, pageCount: doc.numPages };
}

export function clampPage(page: number, pageCount: number): number {
  const last = Math.max(1, pageCount || 1);
  return Math.min(last, Math.max(1, Math.round(page) || 1));
}

export function renderPdfPage(options: {
  fileId: string;
  url: string;
  page: number;
  canvas: HTMLCanvasElement;
  width: number;
  height: number;
  outputScale: number;
}): { promise: Promise<void>; cancel: () => void } {
  let cancelled = false;
  let task: RenderTask | null = null;

  const promise = (async () => {
    const doc = await getPdfDocument(options.fileId, options.url);
    if (cancelled) return;
    const page = await doc.getPage(clampPage(options.page, doc.numPages));
    if (cancelled) return;
    const base = page.getViewport({ scale: 1 });
    const fit = Math.min(options.width / base.width, options.height / base.height);
    const scale = Math.max(0.25, fit * options.outputScale);
    const viewport = page.getViewport({ scale });
    const canvas = options.canvas;
    canvas.width = Math.max(1, Math.round(viewport.width));
    canvas.height = Math.max(1, Math.round(viewport.height));
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) throw new Error("Canvas unavailable");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    task = page.render({ canvasContext: ctx, viewport, canvas });
    await task.promise;
  })();

  return {
    promise,
    cancel: () => {
      cancelled = true;
      try {
        task?.cancel();
      } catch {
        /* already finished */
      }
    },
  };
}
